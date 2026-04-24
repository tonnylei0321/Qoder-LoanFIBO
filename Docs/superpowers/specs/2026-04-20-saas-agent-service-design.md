# SaaS 代理服务设计文档

> 版本: 1.1 | 日期: 2026-04-20 | 状态: 评审后修复完成

## 1. 概述

基于 ERP 代理服务需求规格说明书 v1.2，实现 SaaS 端三大模块：

- **模块 8**: WebSocket Server（P2）— ERP 代理接入与心跳管理
- **模块 9**: 任务队列与结果路由（P2）— 任务分发、超时判定、全链追踪
- **模块 10**: 管理后台（P3）— 企业管理、凭证、审计、版本

### 架构选型

| 组件 | 选型 | 理由 |
|------|------|------|
| WebSocket | FastAPI 原生 WebSocket | 与现有项目无缝集成，零额外依赖 |
| 任务队列 | asyncio.Queue + Redis 备份 | 轻量，无需 Celery Worker 进程 |
| 路由表 | 内存 dict + Redis 持久 | 热路径走内存，Redis 做持久备份 |
| 全链追踪 | Redis List + PG 异步刷盘 | 实时查询走 Redis，持久化走 PG |

## 2. 数据模型

### 2.1 核心关联链路

```
fi_applicant_org(融资企业) → agent_credential(凭证) → WebSocket 连接 → 任务路由
```

### 2.2 PostgreSQL 新增表

#### agent_credential — 代理凭证表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| client_id | VARCHAR(64) | PK | 凭证 ID |
| client_secret_hash | VARCHAR(128) | NOT NULL | bcrypt 哈希 |
| org_id | UUID | FK → fi_applicant_org | 关联融资企业 |
| datasource | VARCHAR(64) | NOT NULL | 数据源标识（如 NCC、HR） |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |
| revoked_at | TIMESTAMPTZ | NULLABLE | 吊销时间，NULL=有效 |

UNIQUE(org_id, datasource)  -- 每个企业每个数据源只有一个有效凭证

#### agent_version — 代理版本表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| version | VARCHAR(32) | NOT NULL | 版本号（如 1.0.0） |
| platform | VARCHAR(16) | NOT NULL | 平台：win / linux |
| download_url | VARCHAR(512) | NOT NULL | 下载链接 |
| min_version | VARCHAR(32) | DEFAULT '1.0.0' | 最低兼容版本 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |

#### agent_audit_log — 审计日志表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| org_id | UUID | FK → fi_applicant_org | 关联企业 |
| action | VARCHAR(64) | NOT NULL | 操作类型（credential_create / credential_revoke / version_update / agent_offline_alert） |
| operator | VARCHAR(128) | | 操作人 |
| ip | VARCHAR(64) | | 操作 IP |
| detail | JSONB | | 扩展详情 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 操作时间 |

#### agent_trace — 全链追踪表（PG 持久化）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| trace_id | VARCHAR(64) | PK | 追踪 ID |
| org_id | UUID | FK → fi_applicant_org | 关联企业 |
| datasource | VARCHAR(64) | | 数据源 |
| action | VARCHAR(64) | | 任务动作 |
| status | VARCHAR(32) | | 整体状态 |
| spans | JSONB | | Span 列表 |
| duration_ms | INTEGER | | 总耗时 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |

### 2.3 Redis 数据结构

| Key 模式 | 类型 | 用途 | TTL |
|----------|------|------|-----|
| `agent:route:{org_id}` | Hash | 路由表：`{datasource: conn_meta_json}` | 无，连接断开时清理 |
| `agent:task:{msg_id}` | Hash | 任务状态：`{status, org_id, datasource, ...}` | 10min |
| `agent:trace:{org_id}` | Stream | Trace 数据（消费者组确认，防丢失） | 24h |
| `agent:offline:{org_id}:{datasource}` | String | OFFLINE 时间戳，用于 5 分钟告警判定 | 10min |

## 3. WebSocket Server（需求 8.1–8.5）

### 3.1 连接端点（8.1）

- 端点：`ws://<host>/agent/connect`
- 认证方式：连接建立后，代理必须在首条消息中发送 `auth` 消息（而非 query param，避免 token 出现在访问日志/Referer 中泄露）
- auth 消息：`{"type": "auth", "client_id": "xxx", "client_secret": "yyy"}`
- 服务端收到 auth 后：查 `agent_credential` 表校验 client_id 存在 + revoked_at IS NULL + bcrypt 校验 client_secret
- 认证失败返回 `{"type": "auth_error", "message": "invalid credentials"}` 并关闭连接
- 连接速率限制：每 IP 每分钟最多 10 次连接尝试，超限返回 429
- bcrypt 前先查 client_id 是否存在（避免对不存在的 client_id 执行慢哈希消耗 CPU）
- 认证成功后从凭证中提取 org_id 和 datasource，存入连接上下文，后续 register 中的 org_id 必须与凭证一致

### 3.2 Register 消息处理（8.2）

- 收到 `register` 消息后：**服务端强制覆盖 org_id 为认证凭证中的 org_id**（防止代理冒充其他企业）→ 版本比较（若 < min_version 则回复 upgrade_notice）→ 写入路由表 → 回复 `register_ack`
- 5 秒超时：`asyncio.wait_for(register_wait, timeout=5)`，超时断开连接
- 同 `(org_id, datasource)` 新连接覆盖旧连接：踢掉旧 ws，关闭旧连接

### 3.3 路由表（8.3）

- 内存热路径：`dict[tuple(org_id, datasource), AgentConn]`（运行时权威源）
- Redis 持久备份：`agent:route:{org_id}` → `{datasource: conn_meta_json}`（仅做启动恢复和状态查询用）
- 启动时从 Redis 恢复路由元数据（不含 ws_conn），若 Redis 与内存不一致以内存为准
- AgentConn 包含：ws_conn, version, ip, last_seen, status(ONLINE/DEGRADED/OFFLINE)

### 3.4 心跳检测（8.4）

- 后台 `asyncio.Task` 每秒扫描所有连接
- 90 秒未收到 heartbeat → 标记 DEGRADED
- 再 15 秒宽限期后 → 标记 OFFLINE，清理路由表，关闭 ws
- OFFLINE 时记录 `agent:offline:{org_id}:{datasource}` 时间戳

### 3.5 代理状态查询（8.5）

- `GET /api/agent/status?org_id={id}` 从 Redis 读取该企业所有 datasource 的代理状态
- 返回：每个 datasource 的 status / version / ip / last_heartbeat

### 3.6 消息协议

```json
// Agent → Server
{"type": "auth", "client_id": "xxx", "client_secret": "yyy"}
{"type": "register", "datasource": "NCC", "version": "1.0.0"}
{"type": "heartbeat"}
{"type": "ack", "msg_id": "xxx"}
{"type": "result", "msg_id": "xxx", "data": {...}}
{"type": "error", "msg_id": "xxx", "code": "ERR_XXX", "message": "..."}

// Server → Agent
{"type": "auth_ack", "status": "ok"}
{"type": "auth_error", "message": "invalid credentials"}
{"type": "register_ack", "status": "ok"}
{"type": "heartbeat_ack"}
{"type": "task", "msg_id": "xxx", "action": "query_indicator", "params": {...}, "timeout_ms": 5000}
{"type": "upgrade_notice", "min_version": "1.1.0", "download_url": "..."}
```

## 4. 任务队列与结果路由（需求 9.1–9.5）

### 4.1 任务生成与推送（9.1）

- 前端/内部服务调用任务接口 → 查路由表
- 路由表有记录 → 通过 ws_conn 推送 `task` 消息
- 路由表无记录 → 立即返回 `DATASOURCE_OFFLINE`

### 4.2 ACK 超时判定（9.2）

- 推送 task 后启动 `asyncio.wait_for(ack_wait, timeout=0.5)`
- 500ms 内未收到 ack → 状态变更 `AGENT_UNREACHABLE`，追加 Trace Span

### 4.3 执行超时判定（9.3）

- 收到 ack 后启动 `asyncio.wait_for(result_wait, timeout=timeout_ms + 5)`
- 超时 → 状态变更 `TASK_TIMEOUT`，追加 Trace Span

### 4.4 msg_id 结果匹配（9.4）

- 内存 `dict[str, asyncio.Future]`：`pending_tasks[msg_id] = Future`
- 最大容量限制：pending_tasks 不超过 10000 条，超限拒绝新任务并返回 `SERVICE_OVERLOAD`
- 收到 result/error 后 `future.set_result(data)` 推送至前端
- 前端通过 SSE（Server-Sent Events）实时获取结果
- SSE 端点：`GET /api/agent/events?org_id={id}`，通过 `Last-Event-ID` 头支持断连重连
- SSE 事件格式：`event: task_result\ndata: {"msg_id": "xxx", "status": "COMPLETED", "data": {...}}`

### 4.5 任务状态机（9.5）

```
PENDING → DISPATCHED → EXECUTING → COMPLETED
                                ├→ ERROR
                                ├→ AGENT_UNREACHABLE
                                └→ TASK_TIMEOUT
```

- 状态存储：Redis Hash `agent:task:{msg_id}`
- 每次状态转换：更新 Redis + 追加 Trace Span

## 5. 全链追踪

### 5.1 数据流

```
前端(点击指标) → SaaS Server → GraphDB(SPARQL) → WS Server → ERP Agent → NCC RDBMS
     ↓               ↓               ↓               ↓            ↓          ↓
   [1]发起       [2]路由查询    [3]本体校验(可选) [4]推送Task   [5]执行SQL  [6]返回数据
```

### 5.2 Trace 结构

```json
{
  "trace_id": "tr_abc123",
  "org_id": "uuid",
  "datasource": "NCC",
  "action": "query_indicator",
  "status": "COMPLETED",
  "created_at": "2026-04-22T08:30:00Z",
  "duration_ms": 1250,
  "spans": [
    {"span_id": "s1", "node": "saas_server", "event": "task_created", "timestamp": "08:30:00.000", "detail": {"indicator": "CurrentRatio"}},
    {"span_id": "s2", "node": "graphdb", "event": "ontology_verified", "timestamp": "08:30:00.050", "detail": {"fibo_path": "...", "match": true}},
    {"span_id": "s3", "node": "ws_server", "event": "task_dispatched", "timestamp": "08:30:00.080", "detail": {"agent_version": "1.0.0"}},
    {"span_id": "s4", "node": "erp_agent", "event": "ack_received", "timestamp": "08:30:00.120", "detail": {}},
    {"span_id": "s5", "node": "erp_agent", "event": "sql_executed", "timestamp": "08:30:01.100", "detail": {"sql": "SELECT ...", "rows": 1}},
    {"span_id": "s6", "node": "saas_server", "event": "result_returned", "timestamp": "08:30:01.250", "detail": {"value": 1.85}}
  ]
}
```

### 5.3 存储策略

- 实时写入 Redis Stream `agent:trace:{org_id}`（消费者组确认，防崩溃丢失）
- 异步消费后批量写入 PG `agent_trace` 表（每 10 秒或 100 条）
- PG 表补充 GIN 索引：`CREATE INDEX idx_trace_spans ON agent_trace USING GIN (spans)`
- 查询：`GET /api/agent/traces?org_id={id}&limit=20`、`GET /api/agent/traces/{trace_id}`
- Trace 中 SQL 做脱敏处理（只保留表名，去掉 WHERE 条件值），防止数据库结构泄露

## 6. 管理后台（需求 10.1–10.8）

### 6.1 API 设计

| 需求 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 10.1 企业注册 | `/api/v1/agent/orgs` | POST | 创建企业 + 分配 org_id + 生成首组凭证 |
| 10.2 凭证生成 | `/api/v1/agent/orgs/{org_id}/credentials` | POST | 生成 client_id + client_secret，明文仅返回一次 |
| 10.2 凭证吊销 | `/api/v1/agent/credentials/{client_id}/revoke` | PUT | 设置 revoked_at，写审计日志 |
| 10.3 安装包下载 | `/api/v1/agent/downloads?platform={win/linux}` | GET | 返回最新版本下载链接 |
| 10.4 连接状态 | `/api/v1/agent/status?org_id={id}` | GET | ONLINE/DEGRADED/OFFLINE + datasource 列表 + IP + 版本 + 最后心跳 |
| 10.5 审计日志 | `/api/v1/agent/audit-logs?org_id={id}&start={}&end={}` | GET | 时间范围过滤，>1000 条标注 AUDIT_OVERFLOW |
| 10.6 版本上传 | `/api/v1/agent/versions` | POST | 上传代理包 + 设置 min_version |
| 10.6 版本列表 | `/api/v1/agent/versions` | GET | 列出所有版本 |
| — | `/api/v1/agent/traces?org_id={id}&limit=20` | GET | 最近 N 条全链追踪 |
| — | `/api/v1/agent/traces/{trace_id}` | GET | Trace 详情含完整 Span |

### 6.2 凭证安全

- client_secret 使用 bcrypt 哈希存储
- 生成时明文仅返回一次，后续不可查看
- 吊销时设置 `revoked_at`，认证时检查 `revoked_at IS NULL`

### 6.3 管理后台认证

- 所有管理后台 API 需 JWT 认证（复用现有 auth 模块或新增 admin token）
- 角色权限：admin（凭证管理、版本上传）、viewer（状态查看、审计只读）
- 审计日志 operator 字段从 JWT token 中提取，不允许为空

### 6.4 OFFLINE 告警（10.8）

- 心跳检测标记 OFFLINE → 记录 `agent:offline:{org_id}:{datasource}` 时间戳到 Redis
- 后台 `asyncio.Task` 每 30 秒扫描，OFFLINE > 5 分钟 → 触发告警
- 初期实现：日志告警 + 前端轮询展示 + 写入 agent_audit_log
- 后续可接入邮件/短信网关

### 6.5 审计日志（10.7）

- 凭证生成/吊销、版本变更时自动写入 `agent_audit_log`
- 记录：操作人、时间、IP、操作类型、详情（JSONB）
- 查询时超过 1000 条结果标注 `AUDIT_OVERFLOW` 告警

## 7. 前端页面

复用现有 Vue3 前端项目，新增 3 个页面：

1. **企业管理页** `/agent/orgs`：企业列表 + 注册 + 凭证管理
2. **代理状态页** `/agent/status`：卡片式展示各企业代理状态，实时状态 + 最后心跳
3. **审计与版本页** `/agent/audit`：审计日志时间线 + 版本管理

## 8. 文件组织

```
backend/app/
├── api/v1/
│   └── agent.py                  # WS 端点 + 管理 REST API
├── models/
│   ├── agent_credential.py       # 凭证表
│   ├── agent_version.py          # 版本表
│   ├── agent_audit_log.py        # 审计日志表
│   └── agent_trace.py            # 全链追踪表
├── services/
│   └── agent/
│       ├── __init__.py
│       ├── ws_handler.py         # WebSocket 连接处理
│       ├── router.py             # 路由表管理（内存+Redis）
│       ├── task_queue.py         # 任务队列 + 状态机
│       ├── heartbeat.py          # 心跳检测 + OFFLINE 告警
│       ├── tracer.py             # 全链追踪
│       └── credential.py         # 凭证生成/校验/吊销
frontend/src/
├── views/agent/
│   ├── OrgManage.vue             # 企业管理
│   ├── AgentStatus.vue           # 代理状态
│   └── AuditVersion.vue          # 审计与版本
├── api/agent.ts                  # Agent API 调用
```

## 9. 依赖变更

```
# requirements.txt 新增
bcrypt==4.2.0          # 凭证哈希
python-multipart       # 已有，文件上传
```

## 10. 非功能性要求

- 单进程部署，水平扩展后续支持
- Redis 做热数据存储，PG 做持久化
- 全链追踪 24h TTL，超过后从 PG 查询
- 心跳间隔 90s，宽限期 15s，OFFLINE 告警阈值 5min

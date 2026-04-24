# SaaS 代理服务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 SaaS 端 WebSocket Server + 任务队列 + 管理后台，支持 ERP 代理接入、任务路由、全链追踪

**Architecture:** FastAPI 原生 WebSocket + 内存路由表 + Redis 备份 + asyncio 任务队列 + SSE 推送。凭证 bcrypt 哈希存储，管理后台 JWT 认证，全链追踪 Redis Stream → PG 异步刷盘。

**Tech Stack:** FastAPI, SQLAlchemy(async), PostgreSQL, Redis, bcrypt, Vue3, SSE

**Design Spec:** `docs/superpowers/specs/2026-04-20-saas-agent-service-design.md`

---

## File Structure

```
backend/app/
├── models/
│   ├── agent_credential.py       # 凭证 ORM 模型
│   ├── agent_version.py          # 版本 ORM 模型
│   ├── agent_audit_log.py        # 审计日志 ORM 模型
│   └── agent_trace.py            # 全链追踪 ORM 模型
├── services/agent/
│   ├── __init__.py
│   ├── credential.py             # 凭证生成/校验/吊销
│   ├── router.py                 # 内存+Redis路由表
│   ├── heartbeat.py              # 心跳检测+OFFLINE告警
│   ├── tracer.py                 # 全链追踪 Redis Stream→PG
│   ├── ws_handler.py             # WebSocket 连接生命周期
│   └── task_queue.py             # 任务队列+状态机+SSE推送
├── api/v1/
│   └── agent.py                  # WS端点+管理REST API+SSE
├── middleware/
│   └── rate_limit.py             # IP级连接速率限制
tests/
├── unit/services/agent/
│   ├── test_credential.py
│   ├── test_router.py
│   ├── test_heartbeat.py
│   ├── test_tracer.py
│   ├── test_ws_handler.py
│   └── test_task_queue.py
├── unit/api/
│   └── test_agent_api.py
└── integration/
    └── test_agent_ws_lifecycle.py
data/ddl/
│   └── agent_tables.sql
frontend/src/
├── api/agent.ts
├── views/agent/
│   ├── OrgManage.vue
│   ├── AgentStatus.vue
│   └── AuditVersion.vue
```

---

### Task 1: 依赖安装 + 数据库模型 + DDL

**Files:**
- Modify: `requirements.txt` — 添加 bcrypt
- Create: `backend/app/models/agent_credential.py`
- Create: `backend/app/models/agent_version.py`
- Create: `backend/app/models/agent_audit_log.py`
- Create: `backend/app/models/agent_trace.py`
- Create: `data/ddl/agent_tables.sql`
- Test: `tests/unit/models/test_agent_models.py`

- [ ] **Step 1:** 安装 bcrypt：`pip install bcrypt==4.2.0`，并在 `requirements.txt` 末尾添加 `bcrypt==4.2.0`

- [ ] **Step 2:** 创建 `backend/app/models/agent_credential.py` — AgentCredential ORM 模型，字段：client_id(PK), client_secret_hash, org_id(FK→fi_applicant_org), datasource, created_at, revoked_at

- [ ] **Step 3:** 创建 `backend/app/models/agent_version.py` — AgentVersion ORM 模型，字段：id(UUID PK), version, platform, download_url, min_version, created_at

- [ ] **Step 4:** 创建 `backend/app/models/agent_audit_log.py` — AgentAuditLog ORM 模型，字段：id(UUID PK), org_id(FK), action, operator(NOT NULL), ip, detail(JSONB), created_at

- [ ] **Step 5:** 创建 `backend/app/models/agent_trace.py` — AgentTrace ORM 模型，字段：trace_id(PK), org_id(FK), datasource, action, status, spans(JSONB+GIN索引), duration_ms, created_at

- [ ] **Step 6:** 创建 `data/ddl/agent_tables.sql` — 4张表的 DDL（含索引：idx_trace_org_created, idx_trace_spans GIN, idx_audit_org_created, idx_credential_org_datasource）

- [ ] **Step 7:** 执行 DDL：`psql -h localhost -p 5433 -U loanfibo -d loanfibo -f data/ddl/agent_tables.sql`

- [ ] **Step 8:** 创建 `tests/unit/models/test_agent_models.py` — 验证模型字段定义正确、AgentTrace 有 GIN 索引

- [ ] **Step 9:** 运行测试：`python -m pytest tests/unit/models/test_agent_models.py -v` → 4 passed

- [ ] **Step 10:** Commit: `git commit -m "feat(agent): add agent service DB models and DDL migration"`

---

### Task 2: 凭证服务

**Files:**
- Create: `backend/app/services/agent/__init__.py`
- Create: `backend/app/services/agent/credential.py`
- Test: `tests/unit/services/agent/test_credential.py`

- [ ] **Step 1:** 编写测试 `test_credential.py` — 5个用例：generate返回client_id+client_secret、verify成功、verify_revoked失败、verify_not_found失败（不执行bcrypt）、revoke设置revoked_at

- [ ] **Step 2:** 运行测试验证失败：`python -m pytest tests/unit/services/agent/test_credential.py -v`

- [ ] **Step 3:** 实现 `credential.py` — CredentialService 类：generate()用secrets生成client_id和sk_前缀secret+bcrypt哈希存储、verify()先查client_id是否存在再bcrypt校验+检查revoked_at、revoke()设置revoked_at时间戳

- [ ] **Step 4:** 运行测试验证通过：`python -m pytest tests/unit/services/agent/test_credential.py -v` → 5 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add credential service with bcrypt hash"`

---

### Task 3: 路由表服务

**Files:**
- Create: `backend/app/services/agent/router.py`
- Test: `tests/unit/services/agent/test_router.py`

- [ ] **Step 1:** 编写测试 — 6个用例：add_connection、overwrite_old（旧ws.close）、remove_connection、get_all_for_org、update_last_seen、get_status_from_redis

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `router.py` — AgentConn dataclass（ws, org_id, datasource, version, ip, last_seen, status）、AgentRouter 类：_routes dict[(org_id,datasource)→AgentConn]、add_connection（覆盖旧连接+关闭旧ws）、remove_connection、get_connection、get_all_for_org、update_last_seen、_sync_to_redis（异步HSET）、get_status_from_redis

- [ ] **Step 4:** 运行测试验证通过：6 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add router service with in-memory + Redis"`

---

### Task 4: 心跳检测 + OFFLINE 告警服务

**Files:**
- Create: `backend/app/services/agent/heartbeat.py`
- Test: `tests/unit/services/agent/test_heartbeat.py`

- [ ] **Step 1:** 编写测试 — 3个用例：91s→DEGRADED、105s→OFFLINE+清理路由+关闭ws、OFFLINE>5min→告警

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `heartbeat.py` — HeartbeatService：check_connections()扫描所有连接返回(degraded_keys, offline_keys)、_record_offline()写Redis agent:offline:{org_id}:{datasource}、check_offline_alerts()扫描Redis中OFFLINE>5分钟的代理

- [ ] **Step 4:** 运行测试验证通过：3 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add heartbeat service with DEGRADED/OFFLINE detection"`

---

### Task 5: 全链追踪服务

**Files:**
- Create: `backend/app/services/agent/tracer.py`
- Test: `tests/unit/services/agent/test_tracer.py`

- [ ] **Step 1:** 编写测试 — 4个用例：create_trace生成trace_id+首span、add_span追加span、SQL脱敏（保留表名去掉WHERE值）、save_to_redis调用xadd

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `tracer.py` — TracerService：create_trace(org_id, datasource, action)→trace dict、add_span(trace, node, event, detail)、update_status(trace, status)计算duration_ms、_desensitize_sql用正则替换单引号值为'***'、save_to_redis调用xadd、flush_to_pg批量写入AgentTrace

- [ ] **Step 4:** 运行测试验证通过：4 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add tracer service with SQL desensitization"`

---

### Task 6: 任务队列 + 状态机

**Files:**
- Create: `backend/app/services/agent/task_queue.py`
- Test: `tests/unit/services/agent/test_task_queue.py`

- [ ] **Step 1:** 编写测试 — 4个用例：TaskStatus枚举值、submit_offline返回DATASOURCE_OFFLINE、pending_tasks容量检查、handle_result resolve Future

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `task_queue.py` — TaskStatus枚举(PENDING/DISPATCHED/EXECUTING/COMPLETED/ERROR/AGENT_UNREACHABLE/TASK_TIMEOUT/DATASOURCE_OFFLINE/SERVICE_OVERLOAD)、MAX_PENDING_TASKS=10000、TaskQueue：submit()查路由→推task消息或返OFFLINE、handle_ack()更新EXECUTING、handle_result() resolve Future+更新trace+通知SSE、handle_error()、_monitor_timeout()超时判定、register_sse_client/unregister_sse_client

- [ ] **Step 4:** 运行测试验证通过：4 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add task queue with state machine and SSE push"`

---

### Task 7: WebSocket 连接处理器

**Files:**
- Create: `backend/app/services/agent/ws_handler.py`
- Test: `tests/unit/services/agent/test_ws_handler.py`

- [ ] **Step 1:** 编写测试 — 2个用例：auth成功返回auth_ack+凭证对象、auth失败返回auth_error+关闭连接

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `ws_handler.py` — AgentWSHandler：handle_auth()从首条消息读auth→verify→auth_ack/auth_error、handle_connection()完整生命周期：auth→register(5s超时+强制覆盖org_id)→消息循环(heartbeat/ack/result/error)→finally清理路由表

- [ ] **Step 4:** 运行测试验证通过：2 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add WS handler with auth+register+message loop"`

---

### Task 8: IP 速率限制中间件

**Files:**
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/rate_limit.py`
- Test: `tests/unit/middleware/test_rate_limit.py`

- [ ] **Step 1:** 编写测试 — 3个用例：限额内允许、超限拒绝、不同IP独立计数

- [ ] **Step 2:** 运行测试验证失败

- [ ] **Step 3:** 实现 `rate_limit.py` — RateLimiter类：滑动窗口算法(max_requests=10, window_seconds=60)、is_allowed(ip)方法、get_ws_rate_limiter()全局单例

- [ ] **Step 4:** 运行测试验证通过：3 passed

- [ ] **Step 5:** Commit: `git commit -m "feat(agent): add IP rate limiter middleware"`

---

### Task 9: 管理 REST API + WS 端点 + SSE 端点

**Files:**
- Create: `backend/app/api/v1/agent.py`
- Modify: `backend/app/main.py` — 注册 agent router
- Test: `tests/unit/api/test_agent_api.py`

- [ ] **Step 1:** 编写基础 API 测试 — 健康检查通过

- [ ] **Step 2:** 实现管理后台 JWT 认证依赖 — 创建 `get_current_admin` 依赖函数，从 Authorization Bearer token 提取用户身份和角色(admin/viewer)，所有管理 API 端点添加 `Depends(get_current_admin)` 保护

- [ ] **Step 3:** 实现 `agent.py` 路由（所有管理端点加 JWT 认证）：
  - WS端点: `@router.websocket("/connect")` — IP速率限制→accept→handle_connection（WS用auth消息认证，不走JWT）
  - SSE端点: `@router.get("/events")` — 注册asyncio.Queue→event_generator→StreamingResponse
  - 企业注册: `POST /agent/orgs` — 创建FiApplicantOrg + 生成首组凭证
  - 凭证生成: `POST /agent/orgs/{org_id}/credentials`
  - 凭证吊销: `PUT /agent/credentials/{client_id}/revoke` + 审计日志（operator从JWT提取）
  - 状态查询: `GET /agent/status?org_id={id}`
  - 安装包下载: `GET /agent/downloads?platform={win/linux}`
  - 审计日志: `GET /agent/audit-logs?org_id={id}&start={}&end={}` 含AUDIT_OVERFLOW
  - 版本上传: `POST /agent/versions` + 审计日志（operator从JWT提取）
  - 版本列表: `GET /agent/versions`
  - 追踪列表: `GET /agent/traces?org_id={id}&limit=20`
  - 追踪详情: `GET /agent/traces/{trace_id}`

- [ ] **Step 4:** 修改 `main.py` — 添加 `from backend.app.api.v1 import agent` 和 `app.include_router(agent.router, prefix=settings.API_V1_STR, tags=["agent"])`

- [ ] **Step 5:** 添加全局服务初始化 — 在 lifespan 中初始化 AgentRouter/HeartbeatService/TracerService/TaskQueue/AgentWSHandler 单例，通过 get_router()/get_task_queue()/get_ws_handler() 获取

- [ ] **Step 6:** 启动心跳后台任务 — 在 lifespan 中 `asyncio.create_task(heartbeat_loop())` 每秒调用 check_connections + 每30秒调用 check_offline_alerts

- [ ] **Step 7:** 运行测试验证通过

- [ ] **Step 8:** Commit: `git commit -m "feat(agent): add management REST API + WS/SSE endpoints with JWT auth"`

---

### Task 10: 前端 API 客户端 + 路由

**Files:**
- Create: `frontend/src/api/agent.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1:** 创建 `frontend/src/api/agent.ts` — 封装所有 agent API 调用：registerOrg, createCredential, revokeCredential, getAgentStatus, getDownloadUrl, getAuditLogs, uploadVersion, getVersions, getTraces, getTraceDetail

- [ ] **Step 2:** 修改 `frontend/src/router/index.ts` — 添加 /agent 子路由：/agent/orgs, /agent/status, /agent/audit

- [ ] **Step 3:** Commit: `git commit -m "feat(agent): add frontend API client and routes"`

---

### Task 11: 前端 — 企业管理页

**Files:**
- Create: `frontend/src/views/agent/OrgManage.vue`

- [ ] **Step 1:** 实现 OrgManage.vue — 企业列表（调用 GET /agent/orgs）、注册对话框（名称+行业+数据源）、凭证管理（生成→显示一次secret的弹窗、吊销→确认对话框）

- [ ] **Step 2:** 验证页面可正常加载

- [ ] **Step 3:** Commit: `git commit -m "feat(agent): add OrgManage page with credential management"`

---

### Task 12: 前端 — 代理状态页

**Files:**
- Create: `frontend/src/views/agent/AgentStatus.vue`

- [ ] **Step 1:** 实现 AgentStatus.vue — 卡片式展示各企业代理状态（ONLINE绿/DEGRADED黄/OFFLINE红）、datasource列表、IP、版本号、最后心跳时间、10秒轮询刷新

- [ ] **Step 2:** 验证页面可正常加载

- [ ] **Step 3:** Commit: `git commit -m "feat(agent): add AgentStatus page with live status display"`

---

### Task 13: 前端 — 审计与版本页

**Files:**
- Create: `frontend/src/views/agent/AuditVersion.vue`

- [ ] **Step 1:** 实现 AuditVersion.vue — 审计日志时间线（时间范围过滤、AUDIT_OVERFLOW标红）+ 版本管理（上传表单：version+platform+download_url+min_version、版本列表）

- [ ] **Step 2:** 验证页面可正常加载

- [ ] **Step 3:** Commit: `git commit -m "feat(agent): add AuditVersion page with logs and version mgmt"`

---

### Task 14: 集成测试

**Files:**
- Create: `tests/integration/test_agent_ws_lifecycle.py`

- [ ] **Step 1:** 编写集成测试 — 完整WS生命周期：创建企业+凭证→WS连接+auth→register→heartbeat→提交task→收到result→断开连接→OFFLINE检测

- [ ] **Step 2:** 运行集成测试验证通过

- [ ] **Step 3:** Commit: `git commit -m "test(agent): add WS lifecycle integration test"`

---

### Task 15: 全链追踪集成 + Seed 数据

**Files:**
- Create: `scripts/seed_agent_data.py`
- Modify: `backend/app/services/agent/tracer.py` — 添加 PG 刷盘定时任务

- [ ] **Step 1:** 实现 PG 刷盘定时任务 — 在 lifespan 中 `asyncio.create_task(flush_traces_loop())` 每10秒消费Redis Stream + 批量写入PG

- [ ] **Step 2:** 创建 `scripts/seed_agent_data.py` — 种子数据：创建测试企业 + 生成凭证 + 插入版本记录

- [ ] **Step 3:** 运行 seed：`python scripts/seed_agent_data.py`

- [ ] **Step 4:** Commit: `git commit -m "feat(agent): add trace PG flush and seed data"`

# LoanFIBO - DDL to FIBO Ontology Mapping Pipeline

基于 LangGraph 的自动化 DDL 到 FIBO 本体映射 Pipeline。

## 项目简介

本项目实现从 BIPV5 源系统 DDL 文件到 SASAC_GOV_v4.4 FIBO 本体的自动化映射 Pipeline，核心特点：

- **LangGraph 工作流编排**：作为项目底座，编排整个映射流程
- **三大 Agent 协同**：Mapping Agent (qwen-long)、Critic Agent (qwen-max)、Revision Agent (qwen-max)
- **断点续跑**：支持中断后从断点恢复
- **修订闭环**：最多 3 轮自动修订
- **批量并发**：默认 5 并发处理

## 技术栈

- **Web 框架**: FastAPI + Python 3.11
- **工作流引擎**: LangGraph 0.2.x
- **数据库**: PostgreSQL 15 + Redis 7
- **ORM**: SQLAlchemy 2.0 async
- **TTL 解析**: rdflib 7.x
- **DDL 解析**: sqlglot 23.x
- **LLM**: 阿里云 DashScope (qwen-long / qwen-max)
- **数据校验**: Pydantic v2

## 快速开始

### 1. 启动基础设施

```bash
docker-compose up -d
```

这将启动：
- PostgreSQL (端口 5434)
- Redis (端口 6380)

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install --trusted-host pypi.tuna.tsinghua.edu.cn -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 3. 启动应用

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 API 文档：http://localhost:8000/docs

## 项目结构

```
backend/app/
├── api/v1/
│   └── pipeline.py          # Pipeline REST API 路由
├── models/
│   ├── table_registry.py    # DDL 解析结果模型
│   ├── ontology_index.py    # TTL 本体索引模型
│   ├── mapping_job.py       # 任务管理模型
│   ├── table_mapping.py     # 映射结果模型
│   └── mapping_review.py    # 检核与修订模型
├── schemas/
│   └── pipeline.py          # Pydantic 请求/响应 Schema
├── services/
│   ├── pipeline_state.py    # LangGraph 状态定义
│   ├── pipeline_orchestrator.py  # LangGraph 工作流编排器
│   ├── ddl_parser.py        # DDL 解析器
│   ├── ttl_indexer.py       # TTL 索引构建器
│   ├── candidate_retriever.py  # FIBO 候选检索器
│   ├── mapping_llm.py       # LLM 映射执行器
│   └── critic_agent.py      # Critic 检核 Agent
├── prompts/                  # LLM Prompt 模板（待实现）
├── config.py                # 应用配置
├── database.py              # 数据库连接
└── main.py                  # FastAPI 应用入口
```

## LangGraph 工作流

### 状态定义

```python
class PipelineState(TypedDict):
    job_id: int
    current_table_id: Optional[int]
    current_batch: List[int]
    revision_round: int
    phase: str
    error: Optional[str]
```

### 工作流图

```
parse_ddl → index_ttl → fetch_batch → retrieve_candidates → mapping_llm → fetch_batch (循环)
                                            ↓
                                        critic → check_revision → revision (最多3轮)
                                                    ↓
                                                 report → END
```

### 节点说明

| 节点 | 功能 | LLM 模型 |
|------|------|---------|
| parse_ddl_node | 解析 DDL 文件 | - |
| index_ttl_node | 构建 TTL 索引 | - |
| fetch_batch_node | 获取待处理表批次 | - |
| retrieve_candidates_node | 检索 FIBO 候选类 | - |
| mapping_llm_node | 执行表→FIBO 映射 | qwen-long |
| critic_node | 多维度检核 | qwen-max |
| check_revision_node | 判断是否需修订 | - |
| revision_node | 修订映射 | qwen-max |
| report_node | 生成执行报告 | - |

## API 接口

### 任务管理
- `POST /api/v1/pipeline/jobs` - 创建映射任务
- `GET /api/v1/pipeline/jobs/{job_id}` - 查询任务状态
- `POST /api/v1/pipeline/jobs/{job_id}/pause` - 暂停任务
- `POST /api/v1/pipeline/jobs/{job_id}/resume` - 恢复任务

### 映射查询
- `GET /api/v1/pipeline/mappings` - 分页查询映射结果
- `GET /api/v1/pipeline/mappings/{id}` - 查询单表映射详情
- `PATCH /api/v1/pipeline/mappings/{id}` - 人工修正映射
- `POST /api/v1/pipeline/mappings/{id}/remap` - 触发重新映射

### 统计与导出
- `GET /api/v1/pipeline/stats` - 映射统计概览
- `GET /api/v1/pipeline/export` - 导出映射结果

### TTL 索引
- `POST /api/v1/pipeline/ttl/index` - 触发 TTL 索引构建
- `GET /api/v1/pipeline/ttl/index/status` - 查询索引状态

## 配置

所有配置在 `.env` 文件中：

```env
# 数据库
POSTGRES_PORT=5434
DATABASE_URL=postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo

# LLM
DASHSCOPE_API_KEY=sk-5c9ce8c702db4f6094805bceb5a21ad0
MAPPING_MODEL=qwen-long
CRITIC_MODEL=qwen-max
REVISION_MODEL=qwen-max

# Pipeline
BATCH_SIZE=5
MAX_CONCURRENCY=5
MAX_REVISION_ROUNDS=3
```

## 下一步

当前已搭建完整的项目框架和 LangGraph 工作流底座，各组件骨架已就位。后续需要实现：

1. **DDL_Parser**: 完整实现 sqlglot 解析逻辑
2. **TTL_Indexer**: 实现 rdflib 解析和 SPARQL 查询
3. **Mapping_LLM**: 实现 Prompt 模板和 LLM 调用
4. **Critic_Agent**: 实现多维度检核逻辑
5. **Revision_LLM**: 实现修订闭环
6. **数据库操作**: 实现所有 CRUD 操作
7. **测试**: 编写单元测试和集成测试

## 许可证

MIT

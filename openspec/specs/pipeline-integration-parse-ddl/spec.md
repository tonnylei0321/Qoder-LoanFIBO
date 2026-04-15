## Why

单元测试已覆盖各节点的纯逻辑（mock DB），但无法验证：

1. SQLAlchemy ORM 与真实 PostgreSQL 的实际写入行为
2. `table_registry` UNIQUE 约束的幂等性（重复调用不报错）
3. `ontology_class_index` 的 `search_vector` 更新和全文索引写入

集成测试连接真实 Docker Compose PostgreSQL，填补这一空白。

## What Changes

- 新增 `tests/integration/conftest.py`：提供 `pg_session`（事务隔离 + 自动回滚）、`ddl_tmp_dir`、`ttl_tmp_dir` fixture
- 新增 `tests/integration/test_parse_ddl_node.py`：验证 `parse_ddl_node` 的 DB 写入行为（2 个测试）
- 新增 `tests/integration/test_index_ttl_node.py`：验证 `index_ttl_node` 的 DB 写入行为（2 个测试）
- 新增 `pytest.ini`：配置 `integration` marker 和 `asyncio_mode`

## Capabilities

### New Capabilities

- `pipeline-integration-parse-ddl`: parse_ddl_node 集成测试覆盖
- `pipeline-integration-index-ttl`: index_ttl_node 集成测试覆盖

## Impact

- 新增文件：`tests/integration/conftest.py`
- 新增文件：`tests/integration/test_parse_ddl_node.py`
- 新增文件：`tests/integration/test_index_ttl_node.py`
- 新增文件：`pytest.ini`
- 行为要求：运行前需 `docker-compose up -d postgres`（port 5434）

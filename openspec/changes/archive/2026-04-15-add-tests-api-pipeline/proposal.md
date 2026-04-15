## Why

`backend/app/api/v1/pipeline.py` 包含 11 个路由，目前没有任何测试覆盖。
API 层测试可验证：

1. 路由是否可达（404 问题）
2. Pydantic Schema 校验是否生效（422 边界）
3. 响应结构是否符合约定（`code`, `data` 字段）
4. 路由参数（path param、query param）是否正确传递

## What Changes

- 新增 `tests/unit/api/__init__.py`
- 新增 `tests/unit/api/test_pipeline.py`：13 个测试，覆盖全部路由
- 使用 `FastAPI.dependency_overrides` mock `get_db`，patch `init_db`/`close_db`
- 不依赖真实数据库

## Capabilities

### New Capabilities

- `api-pipeline-route-coverage`: pipeline API 全路由测试覆盖

## Impact

- 新增文件：`tests/unit/api/__init__.py`
- 新增文件：`tests/unit/api/test_pipeline.py`
- 无生产代码修改

## Design: API Layer Tests

### Approach

使用 `fastapi.testclient.TestClient`（基于 httpx 的同步封装）对 pipeline.py 的全部路由进行单元级测试。

### Architecture

```
tests/unit/api/
├── __init__.py
└── test_pipeline.py    ← 18 个测试，覆盖全部 11 个 pipeline 路由 + 2 个根路由
```

### Key Design Decisions

#### 1. DB 依赖 Override

通过 `app.dependency_overrides[get_db]` 将真实 DB session 替换为 `AsyncMock`，测试期间不需要数据库连接：

```python
async def _override_get_db():
    yield AsyncMock()

app.dependency_overrides[get_db] = _override_get_db
```

#### 2. Lifespan Patch

`main.py` 的 `lifespan` 在 `TestClient` 启动/关闭时执行 `init_db` / `close_db`，会尝试连接真实 DB。
在模块顶部使用 `unittest.mock.patch` 提前 patch，避免测试依赖数据库：

```python
_init_patch = patch("backend.app.main.init_db", new_callable=AsyncMock)
_close_patch = patch("backend.app.main.close_db", new_callable=AsyncMock)
_init_patch.start()
_close_patch.start()
```

#### 3. 模块级 Client

所有测试共享一个 `TestClient(app)` 实例，避免重复启动 lifespan，加快执行速度。

#### 4. 测试分层策略

| 测试类型 | 覆盖点 |
|---------|--------|
| Happy path (2xx) | 路由可达性、响应结构、path/query param 传递 |
| Validation error (422) | Pydantic Schema 约束（`ge=1`, `le=20`, path param 类型） |

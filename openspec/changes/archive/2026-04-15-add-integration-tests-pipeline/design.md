## Design

### 连接策略

集成测试直接使用 `.env` 中的 DATABASE_URL（`postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo`），不创建独立测试库。

**事务隔离**：每个测试在独立事务中运行，测试结束后 `ROLLBACK`，不污染 DB 数据。

### Fixture 架构

```
pg_session (function scope)
  └── 创建独立 AsyncSession，begin() → yield → rollback()
  └── 被 test 通过 patch 注入到节点函数（替换 async_session_factory）

ddl_tmp_dir (function scope)
  └── tmp_path 下写入 test.sql（1 张测试表）
  └── 通过 os.environ["DDL_DIR"] = str(ddl_tmp_dir) 注入

ttl_tmp_dir (function scope)
  └── tmp_path 下复制 data/ttl/sasac_gov_sample.ttl
  └── 通过 os.environ["TTL_DIR"] = str(ttl_tmp_dir) 注入
```

### session_factory mock 策略

`parse_ddl_node` 和 `index_ttl_node` 内部调用 `async_session_factory()`。
集成测试中不能简单 yield pg_session（因为节点内部使用 `async with async_session_factory() as db:`）。

方案：**提供 mock factory 返回绑定到同一事务的 session**，使节点写入的数据在事务提交前可被同一 session 查询验证，事务结束后 rollback。

```python
@contextlib.asynccontextmanager
async def scoped_factory():
    yield pg_session  # 节点使用同一 session，不自动 commit
```

但节点内部会调用 `db.commit()`，这会提交事务——为避免此问题，**改用 savepoint 策略**：

1. `pg_session` 开启外层事务（`BEGIN`）
2. 节点调用 `db.commit()` → 实际只是 `SAVEPOINT RELEASE`（不真正提交）
3. 测试断言后 `ROLLBACK` 回滚全部写入

实现：使用 SQLAlchemy 的 `Session.begin_nested()` 创建 savepoint，节点的 commit 实际 release savepoint，外层 rollback 回滚所有变更。

### DB 连通性检查

测试文件顶部声明 `pytestmark = pytest.mark.integration`，conftest 在 session scope 检查 DB 连通性，不可达则 `pytest.skip`。

### 测试覆盖矩阵

| 测试 | 节点 | 验证点 |
|------|------|--------|
| `test_parse_ddl_inserts_table_registry` | parse_ddl_node | `table_registry` 有记录，`parsed_fields` 非空，`is_primary_key` 正确 |
| `test_parse_ddl_idempotent` | parse_ddl_node | 调用两次，`table_registry` 记录数 = 1 |
| `test_index_ttl_inserts_classes` | index_ttl_node | `ontology_class_index` 有记录，`class_uri` 包含预期值 |
| `test_index_ttl_idempotent` | index_ttl_node | 调用两次，第二次无异常 |

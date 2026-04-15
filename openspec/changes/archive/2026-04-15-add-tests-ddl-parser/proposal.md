## Why

`ddl_parser.py` 是 Pipeline 第一个节点，负责将 DDL 文件解析为 `TableRegistry` 记录，但目前零测试覆盖。任何对解析逻辑的改动都可能无声引入回归，且 sqlglot 主解析与 regex 兜底两条路径均未经自动化验证。

## What Changes

- 新增 `tests/unit/services/test_ddl_parser.py`，覆盖 4 条关键路径
- 使用 `unit/conftest.py` 中的模块级 mock 隔离 SQLAlchemy 和文件系统
- 不改动任何生产代码（纯测试补充）

## Capabilities

### New Capabilities

- `ddl-parser-tests`: 为 `ddl_parser.py` 的核心纯函数和 DB 幂等逻辑提供单元测试覆盖

### Modified Capabilities

（无）

## Impact

- 影响文件：`tests/unit/services/test_ddl_parser.py`（新建）
- 依赖：`pytest`, `pytest-asyncio`, `pytest-mock`（已安装）
- 不影响生产代码，不改变 API 行为

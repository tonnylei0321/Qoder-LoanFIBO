## Why

`ttl_indexer.py` 是 Pipeline 的第二个节点，负责将 FIBO TTL 本体文件解析并构建向量检索索引，供 Mapping 阶段使用。目前零测试覆盖，`parse_ttl_file`、`calculate_file_md5`、`extract_namespace` 等核心函数均未经自动化验证。

## What Changes

- 新增 `tests/unit/services/test_ttl_indexer.py`，覆盖 5 条关键路径
- 不改动任何生产代码（纯测试补充）

## Capabilities

### New Capabilities

- `ttl-indexer-tests`: 为 `ttl_indexer.py` 的纯函数和节点级 IO 逻辑提供单元测试覆盖

### Modified Capabilities

（无）

## Impact

- 影响文件：`tests/unit/services/test_ttl_indexer.py`（新建）
- 依赖：`pytest`, `pytest-asyncio`, `rdflib`（已安装）
- 不影响生产代码，不改变 API 行为

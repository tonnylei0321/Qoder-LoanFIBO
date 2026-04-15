## Context

`ttl_indexer.py` 包含两类逻辑：
1. **纯函数**：`calculate_file_md5`、`extract_namespace` — 无副作用，直接可测
2. **rdflib 依赖函数**：`parse_ttl_file` — 依赖真实 rdflib Graph.parse()，可用最小 TTL 字符串测试
3. **异步 DB 函数**：`index_ttl_node`、`search_candidates` — 需 mock `async_session_factory`

**关键挑战**：`tests/conftest.py` 将 rdflib 整体 mock，而 `parse_ttl_file` 需要真实 rdflib。  
解决方案：在 `test_ttl_indexer.py` 中测试 `parse_ttl_file` 前，临时从 `sys.modules` 移除 mock 的 rdflib 并 import 真实模块（使用 `importlib.reload`）。或更简单：直接在本测试文件顶部、被 conftest 执行之前，不做任何操作 — 因为 conftest 用 `setdefault`，真实 rdflib 若已导入则不会覆盖。实际上 conftest 用 `sys.modules.setdefault` — 只在 key 不存在时设置。若在 conftest 之前已经 import 了真实 rdflib 则没问题，但 conftest 总是先执行。

实际可行方案：利用临时 TTL 文件 + 在测试函数中先移除 mock 再调用。

## Goals / Non-Goals

**Goals:**
- 覆盖 `calculate_file_md5` 纯函数（文件 hash 正确性）
- 覆盖 `extract_namespace` 纯函数（URI 切分逻辑）
- 覆盖 `parse_ttl_file`（最小 TTL 图：2 个 Class + 1 个 Property）
- 覆盖 `index_ttl_node` 目录不存在时返回 error state
- 覆盖 `index_ttl_node` 幂等（文件已索引时跳过）

**Non-Goals:**
- 不测试真实 DB 写入（集成测试范畴）
- 不测试 PostgreSQL 全文搜索（`search_candidates` 依赖 DB，mock 验证调用即可）

## Decisions

**决策 1：parse_ttl_file 使用真实 rdflib + 临时 TTL 文件**
conftest.py 用 `setdefault` mock rdflib，若在 test 函数中先 `del sys.modules['rdflib']` 然后 reload ttl_indexer 的 rdflib 引用，可恢复真实模块。
更简单：直接在 test 文件最顶部（conftest 之后）patch 回真实 rdflib：`import importlib; import rdflib as _real_rdflib; sys.modules['rdflib'] = _real_rdflib`。但因为 conftest 先执行，rdflib 的 mock 已经注入。
**最简可行方案**：不测试 parse_ttl_file 的真实 rdflib 调用，而是 mock `Graph()` 的返回值并验证调用链。这样不需要真实 rdflib，完全可控。

**决策 2：纯函数直接测试，无 mock**
`calculate_file_md5` 和 `extract_namespace` 只依赖标准库，直接调用即可。

**决策 3：async 节点测试使用 tmp_path + mock DB**
同 ddl_parser 策略。

## Risks / Trade-offs

- [风险] `parse_ttl_file` 测试选择 mock Graph 而非真实解析，可能遗漏 rdflib API 变化 → 接受，集成测试可覆盖
- [权衡] 避免在单元测试中移除/重新注入 sys.modules（脆弱），改用 mock 保持测试稳定性

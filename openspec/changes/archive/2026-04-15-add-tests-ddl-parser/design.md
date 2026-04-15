## Context

`ddl_parser.py` 包含两类逻辑：
1. **纯函数**：`parse_ddl_content`、`parse_create_table_sqlglot`、`parse_column_def`、`parse_ddl_regex`、`extract_table_comment`、`extract_table_ddl` — 可直接调用，无副作用
2. **异步 DB 函数**：`parse_ddl_node`（含文件读取 + DB 写入）— 需 mock 文件系统和 `async_session_factory`

现有 `tests/unit/conftest.py` 已 mock SQLAlchemy 层，可复用。

## Goals / Non-Goals

**Goals:**
- 覆盖 sqlglot 主路径、regex 兜底路径、DB 幂等、目录不存在四个路径
- 纯函数直接调用（无 mock），异步节点函数 mock DB + 文件系统

**Non-Goals:**
- 不测试真实 DB 写入（集成测试范畴）
- 不测试 `parse_create_table`（legacy 函数，已有 parse_ddl_content 覆盖）

## Decisions

**决策 1：纯函数优先直接测试**
`parse_ddl_content`、`parse_column_def` 等纯函数不依赖任何 IO，直接传入字符串即可验证，无需 mock。

**决策 2：async 节点测试使用 tmp_path + mock DB**
`parse_ddl_node` 依赖：(a) 文件系统目录，(b) `async_session_factory`。
用 `pytest` 的 `tmp_path` fixture 创建真实临时目录+SQL 文件（避免复杂 mock），
用 `AsyncMock` mock DB session（`scalar_one_or_none` 返回 None 或真实 mock 对象模拟幂等）。

**决策 3：不修改生产代码**
本次变更为纯测试补充，GREEN 阶段确认现有代码已正确实现四个路径即可。

## Risks / Trade-offs

- [风险] `sqlglot` 版本升级可能导致测试 brittle → 仅断言输出的结构字段，不断言内部 AST 细节
- [权衡] 使用真实 `sqlglot` 和 `re` 调用（不 mock），可保证解析逻辑本身被真正执行

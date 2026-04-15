## Context

`critic_agent.py` 包含两类逻辑：
1. **纯函数**：`parse_critic_response` — JSON 解析 + 字段验证，直接可测
2. **异步节点**：`critic_node` — DB 查询 + asyncio.gather，需要 mock DB

额外复杂性：`critic_agent.py` 同时依赖 `backend.app.services.ttl_indexer`（`get_properties_for_class`）、`backend.app.prompts.critic_prompt` 等，均已在 conftest.py 中被 mock。

## Goals / Non-Goals

**Goals:**
- 覆盖 `parse_critic_response`：valid JSON → approved/needs_revision、无效 JSON → None
- 覆盖 `critic_node`：无 pending mappings 时节点直接返回 state
- 覆盖 `review_single_mapping`：LLM 返回 approved 路径、needs_revision 路径

**Non-Goals:**
- 不测试真实 LLM 调用（集成测试范畴）
- 不测试 `check_revision_node`（逻辑简单，优先级低）

## Decisions

**决策 1：parse_critic_response 直接调用，不 mock**
该函数只依赖 `json.loads`，传入不同 JSON 字符串即可验证所有路径。

**决策 2：critic_node no-pending 路径**
mock `db.execute` 返回一个 `scalars().all()` = [] 的结果，验证节点直接返回 state 不报错。

**决策 3：review_single_mapping 全路径 mock**
函数需要 db、TableMapping、LLM 等多个依赖，全部用 AsyncMock/MagicMock 构建，
验证 `save_review_results` 被调用且返回值正确。

## Risks / Trade-offs

- [权衡] `review_single_mapping` 依赖链较深（db 多次 execute），mock 设置稍复杂
- [接受] 保持纯单元测试，不引入真实 DB

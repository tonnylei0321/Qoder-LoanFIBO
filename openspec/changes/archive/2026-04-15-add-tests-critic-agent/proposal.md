## Why

`critic_agent.py` 实现了映射质量三维度评审（语义/Domain-Range/泛化），是 Pipeline 的质量守门节点，但目前零测试覆盖。`parse_critic_response` 的 JSON 解析逻辑、`critic_node` 的 no-pending 路径均未经验证。

## What Changes

- 新增 `tests/unit/services/test_critic_agent.py`，覆盖 4 条关键路径
- 不改动任何生产代码（纯测试补充）

## Capabilities

### New Capabilities

- `critic-agent-tests`: 为 `critic_agent.py` 的 JSON 解析逻辑和节点级行为提供单元测试覆盖

### Modified Capabilities

（无）

## Impact

- 影响文件：`tests/unit/services/test_critic_agent.py`（新建）
- 不影响生产代码

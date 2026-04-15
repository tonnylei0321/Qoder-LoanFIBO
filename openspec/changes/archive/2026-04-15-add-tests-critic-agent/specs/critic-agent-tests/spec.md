## ADDED Requirements

### Requirement: parse_critic_response 解析合法 JSON
`parse_critic_response` SHALL 解析包含 `issues` 和 `overall_status` 字段的 JSON 字符串，返回字典。

#### Scenario: 合法 JSON 返回包含 overall_status 的字典
- **WHEN** 传入包含 `issues` 和 `overall_status` 的合法 JSON 字符串
- **THEN** 返回非 None 字典，且 `result['overall_status']` 等于输入中的值

#### Scenario: Markdown 代码块中的 JSON 被正确提取
- **WHEN** 传入以 ```json ... ``` 包裹的 JSON 字符串
- **THEN** 返回正确解析的字典

### Requirement: parse_critic_response 处理无效 JSON 返回 None
`parse_critic_response` SHALL 在输入不可解析为 JSON 或缺少必要字段时返回 None，不抛出异常。

#### Scenario: 无效 JSON 字符串返回 None
- **WHEN** 传入非 JSON 字符串（如 "not json"）
- **THEN** 返回 None，不抛出异常

#### Scenario: 缺少 overall_status 字段返回 None
- **WHEN** 传入合法 JSON 但缺少 `overall_status` 字段
- **THEN** 返回 None

### Requirement: critic_node 无 pending 映射时直接返回 state
`critic_node` SHALL 在 DB 中无 `review_status='pending'` 的映射时，不调用 LLM，直接返回原始 state。

#### Scenario: 无 pending 映射时 state 原样返回
- **WHEN** mock DB 的 `scalars().all()` 返回空列表，调用 `critic_node`
- **THEN** 返回的 state 与输入相同，且无异常

### Requirement: review_single_mapping 正确处理 approved 路径
`review_single_mapping` SHALL 在 LLM 返回 overall_status='approved' 时，调用 save_review_results 并返回 'approved'。

#### Scenario: LLM 返回 approved 时函数返回 'approved'
- **WHEN** mock LLM 返回包含 `overall_status: 'approved'` 的 JSON，调用 `review_single_mapping`
- **THEN** 函数返回字符串 'approved'，且 `save_review_results` 被调用一次

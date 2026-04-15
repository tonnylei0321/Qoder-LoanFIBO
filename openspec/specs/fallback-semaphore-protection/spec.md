## Capability: fallback-semaphore-protection

### Summary

`try_fallback_mapping` 的 LLM 调用必须受 `mapping_semaphore` 保护，与主模型共享并发预算。

### Behavior

- `try_fallback_mapping` 内的 `llm.ainvoke(messages)` 必须在 `async with mapping_semaphore:` 内执行
- semaphore 使用模块级 `mapping_semaphore`（已由 `settings.MAX_CONCURRENCY` 初始化）
- 不额外创建新的 semaphore，确保 fallback 与主调用共享同一并发限制

### Verification

| Test | Assertion |
|------|-----------|
| `test_fallback_also_acquires_semaphore` | 调用 `try_fallback_mapping` 时，`mapping_semaphore.__aenter__` 被触发 |

### Non-Goals

- 不修改 semaphore 大小或 `MAX_CONCURRENCY` 配置
- 不对 DB 操作加 semaphore 保护（仅限 LLM 调用）

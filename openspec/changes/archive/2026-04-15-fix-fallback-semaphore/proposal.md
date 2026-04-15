## Why

`try_fallback_mapping` 在主模型失败时被调用，但其内部的 fallback LLM 调用（`llm.ainvoke`）没有被 `mapping_semaphore` 包裹。当大量表同时触发 fallback 时，并发 fallback 调用会突破 QPS 限制，与主模型信号量的设计初衷相悖。

## What Changes

- 在 `try_fallback_mapping` 中为 `llm.ainvoke` 调用加上 `mapping_semaphore` 保护
- 新增对应单元测试验证 fallback 也受信号量限制

## Capabilities

### New Capabilities

- `fallback-semaphore-protection`: fallback LLM 调用受 mapping_semaphore 保护

### Modified Capabilities

（无）

## Impact

- 影响文件：`backend/app/services/mapping_llm.py`（修改 try_fallback_mapping）
- 影响文件：`tests/unit/services/test_mapping_llm.py`（新增测试）
- 行为变化：fallback 调用现在也受 MAX_CONCURRENCY 限制

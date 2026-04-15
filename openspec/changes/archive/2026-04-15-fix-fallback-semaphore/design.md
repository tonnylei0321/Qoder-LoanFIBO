## Design

### Root Cause

`mapping_semaphore` 保护主 LLM 调用（`process_single_table` Stage 3），但 `try_fallback_mapping`
中的 fallback `llm.ainvoke` 完全在信号量之外执行。

当主模型批量失败（网络抖动、限流）时，所有表同时进入 fallback，导致并发 fallback 调用数等于
批量大小，突破了 `MAX_CONCURRENCY` 的 QPS 设计上限。

### Solution

在 `try_fallback_mapping` 函数中，用 `async with mapping_semaphore:` 包裹 `llm.ainvoke` 调用。

复用同一个 `mapping_semaphore`（模块级单例），使 fallback 与主模型共享并发预算：

```python
# Before
response = await llm.ainvoke(messages)

# After
async with mapping_semaphore:
    response = await llm.ainvoke(messages)
```

### Constraints

- `mapping_semaphore` 是 `asyncio.Semaphore`，已在模块顶层初始化，直接引用即可
- fallback 已在 `process_single_table` 的 `except` 分支中，此时主 semaphore 已释放，不存在嵌套死锁

### Test Strategy

新增测试 `test_fallback_also_acquires_semaphore`：

1. 用受控 semaphore 替换 `mapping_semaphore`
2. 跟踪 semaphore `__aenter__` 调用顺序
3. 验证 `try_fallback_mapping` 中 `llm.ainvoke` 也经过 semaphore

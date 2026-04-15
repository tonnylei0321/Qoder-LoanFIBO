## Why

`mapping_llm.py` 中的 `asyncio.Semaphore` 包裹了整个 `process_single_table` 函数，
导致数据库查询、向量检索等非 LLM 操作也受到限流，并发性能下降 80%。
同时核心函数缺少单元测试和 LLM 调用规范遵循，存在质量隐患。

## What Changes

- **修复**：将 `mapping_semaphore` 从包裹整个函数改为只包裹 LLM 调用片段
- **新增**：为 `process_single_table` 添加单元测试（遵循 TDD 规范）
- **新增**：在 LLM 响应解析后添加 `uncertainty_exit` 检查（遵循 llm-caller 规范原则 6）
- **修复**：将 `settings.CRITIC_MODEL` 降级配置替换为语义清晰的 `settings.MAPPING_FALLBACK_MODEL`

## Capabilities

### New Capabilities

- `mapping-service-concurrency`: 信号量正确作用于 LLM 调用，保证并发控制精确可控
- `mapping-service-tests`: process_single_table 单元测试覆盖，保证核心逻辑可回归验证

### Modified Capabilities

<!-- 无现有规范文件需要变更 -->

## Impact

- **文件**: `backend/app/services/mapping_llm.py`
- **新增文件**: `tests/unit/services/test_mapping_llm.py`
- **配置**: `backend/app/core/config.py` 新增 `MAPPING_FALLBACK_MODEL` 字段
- **依赖**: 无新增外部依赖
- **API**: 无接口变更（纯内部实现修复）
- **风险**: 低，所有修改均有测试覆盖

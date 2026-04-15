## Tasks

### T1: 新增单元测试（RED）
- 文件：`tests/unit/services/test_mapping_llm.py`
- 新增 `test_fallback_also_acquires_semaphore`
- 预期：首次运行 FAIL（因为 fallback 尚未加 semaphore）

### T2: 修改生产代码（GREEN）
- 文件：`backend/app/services/mapping_llm.py`
- 修改 `try_fallback_mapping`：为 `llm.ainvoke(messages)` 加 `async with mapping_semaphore:`

### T3: 归档
- 将 `openspec/changes/fix-fallback-semaphore/` 移至 `openspec/changes/archive/2026-04-15-fix-fallback-semaphore/`
- 同步 spec 至 `openspec/specs/fallback-semaphore-protection/spec.md`
- Git commit

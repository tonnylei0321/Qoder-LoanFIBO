## 1. RED — 编写失败的测试

- [x] 1.1 创建测试目录 `tests/unit/services/` 并添加 `__init__.py`
- [x] 1.2 创建 `tests/unit/services/test_mapping_llm.py`，编写 `test_semaphore_only_wraps_llm_call` 测试（验证信号量只包裹 LLM 调用）
- [x] 1.3 编写 `test_process_single_table_success` 测试（mock LLM 返回有效映射 JSON）
- [x] 1.4 编写 `test_process_single_table_uncertainty_exit` 测试（mock LLM 返回含 uncertainty_exit 的响应）
- [x] 1.5 编写 `test_process_single_table_no_candidates` 测试（mock search_candidates 返回空列表）
- [x] 1.6 编写 `test_process_single_table_llm_failure_triggers_fallback` 测试（mock llm.ainvoke 抛出异常）
- [x] 1.7 运行测试，确认全部失败（RED 状态确认）
- [x] 1.8 提交：`git commit -m "test: add failing tests for mapping_llm semaphore and paths"`

## 2. GREEN — 修复代码使测试通过

- [x] 2.1 在 `backend/app/config.py` 中新增 `MAPPING_FALLBACK_MODEL: str = "qwen-max"` 配置项
- [x] 2.2 重构 `process_single_table`：将 `mapping_semaphore` 移出函数顶层，只包裹 `llm.ainvoke(...)` 调用
- [x] 2.3 将数据库查询和向量检索移到信号量外（第一个独立 async with db）
- [x] 2.4 将保存结果移到信号量外（第二个独立 async with db）
- [x] 2.5 在 `parse_mapping_response` 调用后添加 `uncertainty_exit` 检查逻辑
- [x] 2.6 将 `try_fallback_mapping` 中的 `settings.CRITIC_MODEL` 替换为 `settings.MAPPING_FALLBACK_MODEL`
- [x] 2.7 运行测试，确认全部通过（GREEN 状态确认）
- [x] 2.8 提交：`git commit -m "feat: fix semaphore scope and add uncertainty_exit check in mapping_llm"`

## 3. REFACTOR — 重构优化

- [x] 3.1 提取魔法数字 `200`（DDL 截断长度）为常量 `DDL_KEYWORD_PREVIEW_LEN = 200`
- [x] 3.2 提取魔法数字 `100`（comment 截断长度）为常量 `DDL_COMMENT_PREVIEW_LEN = 100`
- [x] 3.3 将 `save_mapping_result` 的参数过长调用重构为关键字参数传递
- [x] 3.4 运行测试，确认重构后仍全部通过
- [x] 3.5 提交：`git commit -m "refactor: extract magic numbers and improve readability in mapping_llm"`

## 4. REVIEW — LLM 代码评审

- [x] 4.1 触发 code-reviewer Skill 对 `mapping_llm.py` 进行评审
- [x] 4.2 确认无 P0/P1 问题
- [x] 4.3 记录 P2/P3 问题：2个P2（2个死代码变量、fallback不受信号量控制），2个P3（semaphore mock实现、conftest全局mock）
- [x] 4.4 修复 P2 死代码变量，其余问题记录备查
- [x] 4.5 提交：`git commit -m "review: address code-reviewer feedback for mapping_llm"`

## 5. 归档

- [ ] 5.1 运行完整测试套件确认无回归
- [ ] 5.2 归档变更：`/opsx:archive fix-mapping-llm-semaphore`
- [ ] 5.3 推送到远程仓库：`git push`

<!-- 
评审元信息:
- 角色: positive
- 阶段: 系统设计
- 模型: glm-4.7
- Token用量: 输入=13914, 输出=4368, 总计=18282
- 耗时: 89546.6ms
- 时间: 2026-04-21 08:49:50
-->

### 问题清单

| 编号 | 优先级 | 问题描述 | 建议修复方案 |
|------|--------|----------|------------|
| 001 | P0 | **查询引擎状态处理逻辑缺失**<br>在 `QueryEngine.query` 中，仅检查了 `L0_CRITICAL` 和 `L0_HIGH_COMPILING` 状态。然而，`_force_compile_l0` 方法在编译失败时会设置 `L0_CRITICAL_FAILED` 状态。查询引擎未处理此状态，可能导致在关键规则更新失败后，系统仍继续使用旧规则（合规风险）或返回错误结果。 | 在 `QueryEngine.query` 的状态检查逻辑中增加对 `L0_CRITICAL_FAILED` 的处理。建议策略：直接阻断查询并返回明确的错误信息，提示管理员介入，严禁使用旧版本规则。 |
| 002 | P0 | **增量编译中的浅拷贝风险**<br>在 `IncrementalCompiler._compile_delta` 方法中，使用 `base_compile.copy()` 创建新配置。Python 默认的 `copy()` 是浅拷贝，如果 `CompiledConfig` 包含嵌套的可变对象（如 `rules` 字典），修改 `new_config` 会直接影响 `base_compile`，导致缓存数据被污染或并发错误。 | 使用 `copy.deepcopy(base_compile)` 确保完全隔离新旧配置对象。 |
| 003 | P1 | **Celery 任务名称不一致**<br>在 `IncrementalCompiler.batch_compile_l0` 中调用了 `compile_tenant_task.s`，但在 `CompileWorker` 类中定义的任务装饰器是 `@celery_app.task(bind=True)` 且方法名为 `compile_task`。代码中未定义 `compile_tenant_task`，导致批量编译任务无法提交。 | 统一任务名称。建议将 `CompileWorker.compile_task` 重命名为 `compile_tenant_task`，或者在调用处使用正确的任务引用 `self.worker.compile_task`。 |
| 004 | P1 | **维护窗口编译的死锁风险**<br>`_maintenance_window_compile` 将状态设置为 `L0_HIGH_COMPILING` 并提交异步任务。如果 Celery 任务执行失败、重试耗尽或 Worker 宕机，该状态将无法自动清除，导致该租户的查询服务永久不可用（状态为 `L0_HIGH_COMPILING` 时 `QueryEngine` 拒绝查询）。 | 为 `L0_HIGH_COMPILING` 状态设置 TTL（超时时间）。如果状态未在预期时间内更新为 `SUCCESS` 或 `FAILED`，自动回退到 `STALE` 状态并允许查询（附带告警），或者实现一个看门狗任务来监控并恢复卡住的编译状态。 |
| 005 | P2 | **SQLGenerator 缺少依赖初始化**<br>`SQLGenerator._get_readonly_connection` 方法引用了 `self.readonly_pool`，但在类的 `__init__` 方法中未初始化该属性。实例化时会报错。 | 在 `SQLGenerator.__init__` 中添加 `readonly_pool` 参数，并确保传入已配置好的数据库连接池实例。 |
| 006 | P2 | **RuleCompiler 方法未实现**<br>`RuleCompiler.compile_sync` 方法中调用了 `self._cache_result_sync(tenant_id, result)`，但在提供的代码片段中未定义该方法。 | 补充 `_cache_result_sync` 方法的实现，负责将编译结果写入 Redis。 |
| 007 | P3 | **GraphDBClient 错误处理缺失**<br>`_parse_results` 方法直接访问 `data.get('results')`，如果 GraphDB 返回错误（如 400/500 错误），JSON 结构可能不同，导致 `KeyError` 或后续逻辑崩溃。 | 在解析前检查 HTTP 状态码（虽然在 `query_rules` 中调用了 `raise_for_status`，但在 `_parse_results` 内部增加防御性检查更健壮），或捕获解析异常并记录详细的原始响应。 |
| 008 | P3 | **意图分类器单例模式的线程安全性**<br>`IntentClassifier` 使用了单例模式，虽然使用了 `_model_lock` 来防止重复加载，但在多进程环境（如 uWSGI/Gunicorn prefork 模式）下，每个进程都会加载一份模型到内存。文档中提到的内存评估（4 Worker 60MB）是基于此假设的，但未明确说明部署架构要求。 | 在部署文档中明确说明必须使用 Prefork 模式，或者建议将模型服务独立部署（如 TorchServe），以避免内存重复占用和 GIL 争抢。 |
| 009 | P4 | **SQL 安全黑名单校验局限性**<br>`_validate_sql_safety` 使用黑名单检查危险关键字（如 `DROP`）。虽然主要依赖白名单，但黑名单可以通过编码或大小写变种绕过（尽管代码中使用了 `upper_sql`）。 | 黑名单检查作为辅助手段是可接受的，但建议增加对 `;` 分号的严格检查（代码中已有），并确保所有 SQL 生成路径都经过参数化处理。 |

### 评审结论：有条件通过

**理由**：
该设计文档在整体架构、分层设计、安全性考虑（如 SQL 白名单、只读账号）以及编译策略（分级处理、防风暴）方面表现出较高的专业度，逻辑清晰且符合金融场景对合规性的高要求。

然而，代码实现层面存在几个**阻塞性问题（P0）**和**严重问题（P1）**：
1.  **关键状态处理缺失（P0）**：查询引擎未处理关键编译失败状态，存在合规风险。
2.  **浅拷贝数据污染（P0）**：增量编译逻辑可能导致缓存数据错误。
3.  **任务引用错误（P1）**：Celery 任务名称不一致导致核心编译流程无法运行。
4.  **服务死锁风险（P1）**：维护窗口编译缺乏超时恢复机制。

建议在进入开发/实施阶段前，必须修复上述 P0 和 P1 级别的问题，并补充缺失的代码实现细节。P2 及以下问题可以在编码过程中同步解决。
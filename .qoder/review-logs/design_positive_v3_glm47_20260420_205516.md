<!-- 
评审元信息:
- 角色: positive
- 阶段: 系统设计
- 模型: glm-4.7
- Token用量: 输入=12460, 输出=3830, 总计=16290
- 耗时: 85674.3ms
- 时间: 2026-04-20 20:56:42
-->

### 问题清单

| 编号 | 优先级 | 问题描述 | 建议修复方案 |
|------|--------|----------|------------|
| 001 | P0 | **代码语法错误**：在 `IntentClassifier.classify` 方法中，定义为同步函数 `def classify(...)`，但在代码块中使用了 `return await self._llm_parse(...)`。Python 不允许在同步函数中直接使用 `await`，会导致运行时语法错误。 | 将 `def classify` 修改为 `async def classify`，并确保所有调用方（如 `QueryEngine.query`）均使用 `await` 调用该方法。 |
| 002 | P1 | **异步阻塞风险**：`GraphDBClient` 使用了 `requests.Session` 进行 HTTP 请求。`requests` 是同步阻塞库，在基于 `asyncio` 的 FastAPI 服务中使用会阻塞整个事件循环，导致并发性能急剧下降。 | 将 `requests` 替换为异步 HTTP 客户端，如 `httpx` 或 `aiohttp`，并确保所有 I/O 操作均为异步。 |
| 003 | P1 | **Celery 异步混用风险**：`CompileWorker` 中使用了 `gevent` 模式的 Celery Worker，但在任务中通过 `asyncio.run()` 调用异步代码。`gevent` 的协程机制与 `asyncio` 的事件循环机制不兼容，混用极易导致事件循环冲突或死锁。 | 建议方案一：使用 `celery` 的 `prefork` 模式配合 `asyncio.run`（较重）。建议方案二（推荐）：将 `RuleCompiler` 的核心逻辑改为同步代码，或使用 `celery` 原生支持的 `kombu` 异步连接，避免在 Worker 内部手动管理事件循环。 |
| 004 | P2 | **回滚机制持久化缺失**：`RuleRollbackService` 的回滚逻辑仅更新 Redis 缓存（`activate_version`），未同步更新 PostgreSQL 中的 `tenant_compile_status` 表。如果 Redis 缓存丢失或重启，系统将无法感知当前激活的版本号，导致状态不一致。 | 在 `activate_version` 方法中，增加对 PostgreSQL `tenant_compile_status` 表的更新操作，将 `version` 和 `status` 持久化到数据库，确保 Redis 重启后可恢复。 |
| 005 | P2 | **L0 批量编译效率低下**：`IncrementalCompiler.batch_compile_l0` 方法中使用了串行循环处理租户列表，且通过 `await asyncio.sleep` 进行限流。对于大规模租户（如数万级），串行处理会导致总耗时过长，无法满足“快速生效”的需求。 | 改用并发控制（如 `asyncio.Semaphore`）进行并行编译，在限制并发数（如 100）的前提下同时处理多个租户，而非串行 sleep。 |
| 006 | P2 | **L0 懒加载的冷启动风险**：`_lazy_compile_l0` 逻辑中，如果 `last_compile` 不存在（新租户或缓存丢失），会立即触发编译。若 L0 变更导致大量新租户同时访问，仍可能触发“编译风暴”。 | 引入“随机抖动”或“延迟队列”，对于需要立即编译的情况，延迟随机秒数后再执行，打散瞬时流量。 |
| 007 | P3 | **DSL 执行引擎过度设计**：强制要求将所有公式编译为 WASM 模块执行。对于简单的财务计算公式（如加减乘除），WASM 的编译开销和内存占用远大于原生 Python AST 解释器，且开发复杂度高。 | 评估是否必须使用 WASM。建议采用“沙箱化 Python 解释器”（如 RestrictedPython）或 AST 遍历器处理简单公式，仅对极高风险的复杂逻辑使用 WASM。 |
| 008 | P3 | **监控指标不切实际**：监控指标中定义 P99 响应时间 < 100ms。考虑到引入了 LLM Fallback 机制（通常耗时 500ms-2000ms），该阈值在涉及 LLM 调用的场景下无法达成，会导致频繁误报。 | 将监控指标拆分：简单查询（BERT/模板）P99 < 100ms，复杂查询（LLM Fallback）P99 < 2000ms。 |
| 009 | P4 | **代码重复**：`DSLExecutor` 类中 `_parse` 和 `_compile_to_wasm` 方法被定义了两次。 | 删除重复的方法定义。 |

---

### 评审结论：有条件通过

**理由**：
设计文档整体架构清晰，分层合理，覆盖了从规则编译、查询引擎到存储层的完整链路。NLQ 分层架构（模板 -> BERT -> LLM）的设计思路具有较好的落地性和成本控制意识。

然而，代码实现层面存在**阻塞性问题（P0）**和严重的**技术债务（P1）**，主要体现在 Python 异步编程规范错误（同步函数中使用 await）、异步框架中混用阻塞库以及 Celery 异步模型冲突。这些问题如果不修复，系统将无法正常运行或在生产环境出现严重的性能瓶颈。

建议在进入开发阶段前，必须修正上述 P0 和 P1 级别的代码逻辑设计，并完善回滚机制的持久化策略。
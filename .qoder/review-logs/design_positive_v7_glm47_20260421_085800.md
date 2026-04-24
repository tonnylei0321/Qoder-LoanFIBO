<!-- 
评审元信息:
- 角色: positive
- 阶段: 系统设计
- 模型: glm-4.7
- Token用量: 输入=13976, 输出=4781, 总计=18757
- 耗时: 67286.7ms
- 时间: 2026-04-21 08:59:07
-->

### 问题清单

| 编号 | 优先级 | 问题描述 | 建议修复方案 |
|------|--------|----------|------------|
| 001 | P1 | **批量编译风暴风险**：`IncrementalCompiler.batch_compile_l0` 方法中，虽然代码注释声称“分块创建Celery任务（防编译风暴）”，但实际逻辑是将所有分块的任务合并到一个 `all_tasks` 列表中，最后通过 `chord(all_tasks)` 一次性提交。如果租户数量巨大（如10万+），这会瞬间向Broker发送海量消息，导致内存溢出或网络阻塞，并未真正实现分批流控。 | 修改 `batch_compile_l0` 逻辑，实现真正的分批提交。建议使用 `chain` 连接多个 `group`，或者使用 `replace` 策略逐步提交任务，避免一次性将所有任务ID加载到内存或发送到Broker。 |
| 002 | P1 | **L0变更严重程度传递缺失**：在 `IncrementalCompiler.incremental_compile` 方法中，当 `change_type == ChangeType.L0` 时，调用 `_compile_l0_strategy(tenant_id, last_compile)`，未传递 `l0_change` 参数。被调方法内部将 `l0_change` 默认为 `None` 并初始化为 `NORMAL` 级别。这意味着所有L0变更都会被默认视为“延迟1小时生效”，导致关键合规规则变更无法即时生效，存在严重的合规风险。 | 修改 `incremental_compile` 方法签名，增加 `l0_change` 参数，并在调用 `_compile_l0_strategy` 时传递该参数。确保上游调用者（如规则管理API）能正确识别并传递L0变更的严重程度。 |
| 003 | P2 | **SQL黑名单逻辑误杀合法查询**：`SQLGenerator._validate_sql_safety` 中的黑名单检查逻辑 `if ';' in sql.strip().rstrip(';')` 存在缺陷。如果用户查询的字符串字面量中包含分号（例如搜索文本 "Hello; World"），该逻辑会误判为非法SQL并拒绝执行，破坏了业务功能的完整性。 | 优化黑名单逻辑。建议移除对分号的简单黑名单检查，因为参数化查询已经防御了SQL注入。如果必须检查，应使用正则表达式确保分号不在字符串字面量或注释内部，或者完全依赖白名单机制和参数化查询，移除黑名单检查。 |
| 004 | P2 | **对 `psycopg2.quote_ident` 的误解**：文档中 `SQLGenerator._quote_identifier` 注释声称不使用 `psycopg2.quote_ident` 是为了避免“同步IO阻塞事件循环”。实际上 `psycopg2.extensions.quote_ident` 是一个纯Python函数，仅涉及字符串处理，不涉及网络IO。手动实现转义逻辑增加了维护成本和潜在的安全边界情况（如NULL字符）。 | 修正注释并重新评估技术选型。确认 `psycopg2.quote_ident` 为纯CPU操作后，建议直接使用该标准库函数以确保转义逻辑的准确性和安全性，或者使用 `sqlparse` 等库的标识符处理功能。 |
| 005 | P3 | **调度器状态丢失风险**：`CompileScheduler` 使用内存中的 `PriorityQueue` (`self.task_queue`) 来管理任务。如果服务重启或崩溃，内存中的待调度任务将全部丢失，导致L0变更无法被编译。 | 将待调度任务持久化到数据库或Redis中，在服务重启时恢复任务队列。或者依赖Celery自身的调度机制（如 `celery beat` 或 `apply_async` 的 `eta/countdown`）来管理延迟任务，而不是在应用层维护内存队列。 |
| 006 | P3 | **GraphDB连接池资源泄漏风险**：`GraphDBClient` 的 `_get_async_session` 和 `_get_sync_session` 使用了延迟初始化，但在 `close()` 方法中直接关闭。如果在FastAPI的 `lifespan` 上下文中管理，若发生异常导致初始化未完成但触发了关闭，逻辑尚可；但在普通使用中，若未显式调用 `close()`，连接池可能不会正确释放（特别是 `httpx.AsyncClient`）。 | 确保使用上下文管理器（`async with`）或在FastAPI的 startup/shutdown 事件中严格管理生命周期。建议将 `GraphDBClient` 实例化为单例，并确保应用退出时调用 `close`。 |
| 007 | P4 | **类型注解缺失**：代码中大量使用了 `List`、`Dict`、`Tuple` 等旧式类型注解，未使用 Python 3.9+ 推荐的 `list`、`dict`、`tuple` 或 `typing` 的现代特性（如 `|` 联合类型）。 | 更新类型注解以符合现代 Python 标准，提高代码可读性和 IDE 支持度。 |

### 评审结论：有条件通过

**理由**：
该设计文档整体架构清晰，分层合理，特别是对同步/异步编程模型的隔离处理（`RuleCompiler` 的双模式设计）非常专业，有效避免了事件循环阻塞问题。NLQ分层架构和意图分类器的设计也具备较好的可落地性。

然而，存在两个 **P1** 级别的严重问题必须修复：
1.  **批量编译逻辑存在重大缺陷**，可能导致生产环境Broker崩溃。
2.  **L0变更严重程度参数传递缺失**，导致关键合规规则变更被错误降级处理，存在合规风险。

此外，SQL安全校验的黑名单逻辑过于简单，可能误杀合法业务查询（P2）。

建议在修复上述问题后，进入开发阶段。
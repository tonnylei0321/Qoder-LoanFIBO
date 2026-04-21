# GraphDB 规则引擎设计文档 v2.0

> **版本**: v2.0  
> **日期**: 2026-04-20  
> **状态**: 开发中  
> **对应需求**: requirements-graphdb-rules-engine-v2.md

---

## 1. 系统架构设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              接入层 (API Gateway)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 自然语言查询 │  │ 规则管理API │  │ 租户配置API │  │ 管理后台API        │ │
│  │   (NLQ)     │  │             │  │             │  │                    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          └────────────────┴────────────────┴────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                           服务层 (Service Layer)                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   查询引擎       │  │   规则编译器     │  │      租户管理服务          │  │
│  │  (Query Engine) │  │ (Rule Compiler) │  │   (Tenant Management)       │  │
│  │                 │  │                 │  │                             │  │
│  │ • 意图分类器     │  │ • 规则合并      │  │ • 租户配置管理             │  │
│  │ • 规则匹配器     │  │ • DSL解析器     │  │ • L2规则管理               │  │
│  │ • SQL生成器      │  │ • SQL生成器     │  │ • 权限管理                 │  │
│  │ • 结果组装器     │  │ • 编译缓存      │  │                             │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────────────────┘  │
└───────────┼────────────────────┼────────────────────────────────────────────┘
            │                    │
            │         ┌──────────┴──────────┐
            │         │                     │
┌───────────▼─────────▼─────────┐  ┌────────▼────────┐
│        规则存储层              │  │    数据存储层    │
│  ┌─────────┐  ┌─────────────┐ │  │  ┌────────────┐ │
│  │GraphDB  │  │  PostgreSQL │ │  │  │  BIPV5业务库│ │
│  │(L0+L1)  │  │   (L2规则)  │ │  │  │(PostgreSQL)│ │
│  └─────────┘  └─────────────┘ │  │  └────────────┘ │
│                               │  └─────────────────┘
│  ┌─────────────────────────┐  │
│  │      Redis缓存          │  │
│  │  (编译后规则+查询缓存)   │  │
│  └─────────────────────────┘  │
└───────────────────────────────┘
```

### 1.2 核心组件职责

| 组件 | 职责 | 技术选型 |
|------|------|----------|
| **API Gateway** | 路由、鉴权、限流 | Kong / Nginx |
| **查询引擎** | NLQ解析、规则匹配、SQL生成 | Python + FastAPI |
| **规则编译器** | 规则合并、DSL编译、版本管理 | Python + Celery |
| **租户管理** | 租户配置、L2规则管理、权限控制 | Python + FastAPI |
| **意图分类器** | 轻量级BERT模型，查询分类 | BERT-base (本地部署) |
| **GraphDB** | L0+L1规则存储 | RDF4J / GraphDB |
| **PostgreSQL** | L2规则、租户配置、元数据 | PostgreSQL 15+ |
| **Redis** | 编译后规则缓存、查询结果缓存 | Redis Cluster |

---

## 2. 规则编译器设计

### 2.1 编译流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  触发条件    │────▶│  规则加载    │────▶│  规则合并    │
│             │     │             │     │             │
│ • L1变更    │     │ • L0 (GraphDB)│    │ • 冲突检测   │
│ • L2变更    │     │ • L1 (GraphDB)│    │ • 冲突解决   │
│ • 定时任务  │     │ • L2 (PG)    │     │ • 版本锁定   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐     ┌──────▼──────┐
│  缓存写入    │◀────│  编译输出    │◀────│  DSL编译    │
│             │     │             │     │             │
│ • Redis     │     │ • JSON配置   │     │ • 语法解析   │
│ • 版本记录  │     │ • SQL模板    │     │ • SQL生成   │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 2.2 编译服务架构

```python
# 编译服务核心类设计

class RuleCompiler:
    """
    规则编译器 - 统一入口
    
    架构说明：
    - 核心逻辑为同步实现（CPU密集型，适合多进程）
    - 提供异步包装器供FastAPI调用
    - Celery Worker直接使用同步接口
    """
    
    def __init__(self, graphdb_client, pg_client, redis_client):
        self.graphdb = graphdb_client
        self.pg = pg_client
        self.redis = redis_client
        self.dsl_parser = DSLParser()
        self.sql_generator = SQLGenerator()
    
    def compile_sync(self, tenant_id: str) -> CompileResult:
        """
        同步编译入口（供Celery Worker调用）
        
        实现方式：
        1. 使用同步IO操作（psycopg2, redis-py）
        2. 避免使用 async/await
        3. 适合CPU密集型编译任务
        """
        # 1. 同步加载规则
        l0_rules = self._load_l0_rules_sync()
        l1_rules = self._load_l1_rules_sync(tenant_id)
        l2_rules = self._load_l2_rules_sync(tenant_id)
        
        # 2. 合并规则（纯内存操作）
        merged_rules = self._merge_rules(l0_rules, l1_rules, l2_rules)
        
        # 3. 冲突检测
        conflicts = self._detect_conflicts(merged_rules)
        if conflicts.critical:
            return CompileResult(success=False, errors=conflicts.errors)
        
        # 4. DSL编译（CPU密集型）
        compiled_formulas = self._compile_formulas_sync(merged_rules.formulas)
        
        # 5. SQL生成
        sql_templates = self._generate_sql_templates(merged_rules, compiled_formulas)
        
        # 6. 输出结果
        result = CompiledConfig(
            version=self._generate_version(),
            tenant_id=tenant_id,
            rules=merged_rules,
            sql_templates=sql_templates,
            compiled_at=datetime.now()
        )
        
        # 7. 同步写入缓存
        self._cache_result_sync(tenant_id, result)
        
        return CompileResult(success=True, config=result)
    
    async def compile(self, tenant_id: str) -> CompileResult:
        """
        异步编译入口（供FastAPI服务调用）
        
        实现方式：
        1. 在同步方法外包裹 asyncio.to_thread
        2. 将CPU密集型任务放入线程池
        3. 不阻塞事件循环
        """
        import asyncio
        return await asyncio.to_thread(self.compile_sync, tenant_id)


class CompileWorker:
    """编译工作节点（Celery Worker）
    
    架构决策：统一使用同步模型
    - Celery Worker 使用默认的 prefork 模式（非 gevent）
    - RuleCompiler 核心逻辑改为同步实现
    - 避免 asyncio/gevent 事件循环冲突
    
    启动命令：celery -A tasks worker --concurrency=4 --loglevel=info
    """
    
    def __init__(self, compiler: RuleCompiler):
        self.compiler = compiler
    
    @celery_app.task(bind=True, max_retries=3, name='compile_tenant_task')
    def compile_task(self, tenant_id: str, priority: int = 0):
        """编译任务 - 纯同步实现"""
        try:
            # 同步调用编译器（避免 asyncio/gevent 冲突）
            result = self.compiler.compile_sync(tenant_id)
            if not result.success:
                # 记录失败，发送告警
                self._record_failure(tenant_id, result.errors)
                raise self.retry(countdown=60)
            return result
        except Exception as e:
            logger.error(f"Compile failed for {tenant_id}: {e}")
            raise self.retry(countdown=60)

# RuleCompiler 定义已合并到上方，此处删除重复定义


class CompileScheduler:
    """编译调度器"""
    
    def __init__(self, worker: CompileWorker):
        self.worker = worker
        self.task_queue = PriorityQueue()
    
    async def schedule_batch_compile(self, tenant_ids: List[str], priority: str = "normal"):
        """批量调度编译任务"""
        priority_map = {"high": 0, "normal": 5, "low": 10}
        p = priority_map.get(priority, 5)
        
        for tenant_id in tenant_ids:
            self.task_queue.put((p, tenant_id))
        
        # 批量提交到Celery
        tasks = []
        while not self.task_queue.empty():
            _, tenant_id = self.task_queue.get()
            task = compile_tenant_task.delay(tenant_id, priority=p)
            tasks.append(task)
        
        return tasks
```

### 2.3 增量编译策略

```python
class IncrementalCompiler:
    """增量编译器 - 支持L0编译风暴防护"""
    
    def __init__(self, compiler: RuleCompiler, cache: CompileCache, scheduler: CompileScheduler):
        self.compiler = compiler
        self.cache = cache
        self.scheduler = scheduler
        # 限流配置：L0变更批量编译控制
        self.l0_rate_limit = 100  # 每秒最大编译租户数
        self.l0_batch_size = 1000  # 每批最大租户数
    
    async def incremental_compile(
        self, 
        tenant_id: str, 
        change_type: ChangeType,
        changed_rules: List[Rule]
    ) -> CompileResult:
        """
        增量编译
        
        根据变更类型选择编译策略：
        - L0变更: 影响所有租户，分批同步编译（防风暴）
        - L1变更: 影响同行业租户，批量编译
        - L2变更: 仅影响当前租户，单租户编译
        """
        
        # 获取上次编译结果
        last_compile = await self.cache.get_last_compile(tenant_id)
        
        if change_type == ChangeType.L0:
            # L0变更：分批同步编译策略（防编译风暴）
            # 所有L0变更必须在有限时间内完成，不允许无限期懒加载
            return await self._compile_l0_strategy(tenant_id, last_compile)
        
        elif change_type == ChangeType.L1:
            # L1变更：检查是否影响当前租户
            if self._is_affected(tenant_id, changed_rules):
                return await self.compiler.compile(tenant_id)
            else:
                return CompileResult(success=True, cached=True)
        
        elif change_type == ChangeType.L2:
            # L2变更：仅编译变更的规则（支持删除检测）
            return await self._compile_delta(tenant_id, changed_rules, last_compile)
    
    def batch_compile_l0(
        self,
        tenant_ids: List[str],
        priority: str = "normal"
    ) -> BatchCompileJob:
        """
        L0变更批量编译（提交到Celery队列，分块流控）
        
        架构说明：
        - API层只负责任务提交，不执行实际编译
        - 通过Celery队列分发到Worker节点
        - 使用chunked提交防编译风暴
        - 利用Celery的rate_limit控制并发
        
        Args:
            tenant_ids: 待编译租户列表
            priority: 任务优先级（high/normal/low）
            
        Returns:
            BatchCompileJob: 批量编译任务句柄
        """
        from celery import chord, group
        from celery.result import GroupResult
        
        # 1. 创建批量编译任务组
        job_id = str(uuid.uuid4())
        
        # 2. 分块创建Celery任务（防编译风暴）
        # 每块1000租户，避免瞬间压垮消息broker
        chunk_size = 1000
        all_tasks = []
        
        for i in range(0, len(tenant_ids), chunk_size):
            chunk = tenant_ids[i:i + chunk_size]
            chunk_tasks = [
                compile_tenant_task.s(tenant_id, priority=priority)
                for tenant_id in chunk
            ]
            all_tasks.extend(chunk_tasks)
        
        
        # 3. 使用chord并行执行，完成后回调
        callback = batch_compile_complete.s(job_id=job_id)
        job = chord(all_tasks)(callback)
        
        # 4. 设置Celery任务速率限制（全局流控）
        # 每分钟最多处理100个编译任务
        compile_tenant_task.rate_limit = '100/m'
        
        # 5. 记录任务状态
        self._record_batch_job(
            job_id=job_id,
            tenant_count=len(tenant_ids),
            celery_group_id=job.id,
            priority=priority
        )
        
        return BatchCompileJob(
            job_id=job_id,
            celery_group_id=job.id,
            tenant_count=len(tenant_ids),
            status="submitted"
        )
    
    def get_batch_status(self, job_id: str) -> BatchCompileStatus:
        """查询批量编译任务状态"""
        result = GroupResult.restore(job_id)
        if not result:
            raise ValueError(f"Job {job_id} not found")
        
        return BatchCompileStatus(
            job_id=job_id,
            completed=result.completed_count(),
            total=len(result),
            failed=result.failed(),
            status="completed" if result.ready() else "running"
        )
    
    async def _compile_l0_strategy(
        self,
        tenant_id: str,
        last_compile: CompiledConfig,
        l0_change: L0ChangeInfo = None
    ) -> CompileResult:
        """
        L0变更编译策略（分级处理）
        
        架构决策：
        金融场景下，L0规则变更不允许无限期懒加载，
        必须在有限时间内完成全量编译。
        
        策略：
        1. CRITICAL: 强制同步编译，阻断查询（无延迟）
        2. HIGH: 维护窗口批量编译（分钟级延迟）
        3. NORMAL: 分批异步编译，最大延迟1小时
        
        L0变更分级：
        - CRITICAL: 监管合规、核心财务逻辑变更（如会计准则更新）
        - HIGH: 重要业务规则变更（如风控规则调整）
        - NORMAL: 描述性变更、非核心字段调整
        
        与旧“懒加载”策略的区别：
        - 旧策略：NORMAL级别可无限期使用旧版本 → 合规风险
        - 新策略：NORMAL级别最大延迟1小时，保证最终一致性
        """
        if not l0_change:
            l0_change = L0ChangeInfo(severity="NORMAL")
        
        severity = l0_change.severity
        
        if severity == "CRITICAL":
            # 强制同步编译：阻断查询直到编译完成
            return await self._force_compile_l0(tenant_id, l0_change)
        
        elif severity == "HIGH":
            # 维护窗口批量编译：分钟级延迟
            return await self._maintenance_window_compile(tenant_id, last_compile, l0_change)
        
        else:  # NORMAL
            # 分批异步编译：最大延迟1小时
            await self.cache.mark_stale(
                tenant_id, 
                reason="L0_UPDATED",
                max_staleness=3600  # 最大过期时间1小时
            )
            # 触发后台编译任务（确保最终一致性）
            self._schedule_background_compile(tenant_id)
            
            if last_compile:
                return CompileResult(
                    success=True,
                    config=last_compile,
                    message="L0已更新（NORMAL级别），继续使用当前版本，后台编译中（最长1小时）"
                )
            else:
                return await self.compiler.compile(tenant_id)
    
    def _schedule_background_compile(self, tenant_id: str):
        """调度后台编译任务（确保NORMAL级别最终一致性）"""
        compile_tenant_task.apply_async(
            args=[tenant_id],
            priority=3,  # 低优先级
            countdown=60  # 60秒后开始
        )
    
    async def _maintenance_window_compile(
        self,
        tenant_id: str,
        last_compile: CompiledConfig,
        l0_change: L0ChangeInfo
    ) -> CompileResult:
        """
        维护窗口批量编译（HIGH级别）
        
        策略：
        1. 设置编译中状态（带TTL），阻断查询
        2. 提交批量编译任务到Celery
        3. 设置看门狗任务，防死锁
        4. 编译完成后恢复正常
        """
        # 1. 标记编译中状态（带TTL，防死锁）
        compile_timeout = 300  # 5分钟超时
        await self.cache.set_status(
            tenant_id, 
            "L0_HIGH_COMPILING",
            ttl=compile_timeout  # 状态自动过期，防止永久阻断
        )
        
        # 2. 提交编译任务
        compile_tenant_task.apply_async(
            args=[tenant_id],
            priority=1  # 高优先级
        )
        
        # 3. 设置看门狗任务（5分钟后检查编译是否完成）
        compile_watchdog_task.apply_async(
            args=[tenant_id],
            countdown=compile_timeout  # 与TTL相同
        )
        
        return CompileResult(
            success=True,
            config=last_compile,
            message="L0 HIGH变更编译中，查询暂时不可用"
        )
    
    @celery_app.task(name='compile_watchdog_task')
    def compile_watchdog_task(self, tenant_id: str):
        """
        编译看门狗（防死锁）
        
        检查编译是否在TTL内完成，
        如果未完成则将状态回退到STALE，
        允许查询继续（附带告警）
        """
        status = self.cache.get_compile_status_sync(tenant_id)
        if status == "L0_HIGH_COMPILING":
            # 编译超时，回退到STALE状态（允许查询但附加警告）
            logger.error(
                f"Compile watchdog triggered for {tenant_id}, "
                f"reverting to STALE status"
            )
            self.cache.set_status_sync(tenant_id, "STALE")
            # 发送管理员告警
            self._send_admin_alert(
                tenant_id,
                "L0编译超时，已回退到STALE状态，请检查编译Worker"
            )
    
    async def _force_compile_l0(
        self,
        tenant_id: str,
        l0_change: L0ChangeInfo
    ) -> CompileResult:
        """
        强制同步编译（CRITICAL级别）
        
        特点：
        1. 立即触发编译
        2. 编译完成前，查询返回"规则更新中"提示
        3. 确保合规性，避免旧规则风险
        """
        logger.warning(f"CRITICAL L0 change for tenant {tenant_id}, forcing compile")
        
        # 标记为编译中（阻断查询）
        await self.cache.set_compiling_status(tenant_id, status="L0_CRITICAL")
        
        try:
            # 立即编译
            result = await self.compiler.compile(tenant_id)
            
            if result.success:
                await self.cache.clear_compiling_status(tenant_id)
                return CompileResult(
                    success=True,
                    config=result.config,
                    message=f"L0关键更新已生效: {l0_change.description}"
                )
            else:
                # 编译失败，回退到旧版本
                await self.cache.set_compiling_status(
                    tenant_id, 
                    status="L0_CRITICAL_FAILED",
                    error=result.errors
                )
                return CompileResult(
                    success=False,
                    errors=result.errors,
                    message="L0关键更新编译失败，请联系管理员"
                )
        except Exception as e:
            await self.cache.set_compiling_status(
                tenant_id,
                status="L0_CRITICAL_ERROR",
                error=str(e)
            )
            raise
    
    async def _canary_compile_l0(
        self,
        tenant_id: str,
        last_compile: CompiledConfig,
        l0_change: L0ChangeInfo
    ) -> CompileResult:
        """
        灰度发布编译（HIGH级别）
        
        特点：
        1. Tier1租户优先编译（高频使用）
        2. Tier2/Tier3租户延后编译
        3. 支持按租户ID哈希灰度
        """
        tenant_info = await self._get_tenant_info(tenant_id)
        
        # Tier1租户：立即编译
        if tenant_info.tier == "tier1":
            return await self.compiler.compile(tenant_id)
        
        # Tier2/Tier3租户：延迟编译（按租户ID哈希）
        canary_threshold = l0_change.canary_percentage or 10  # 默认10%灰度
        tenant_hash = hash(tenant_id) % 100
        
        if tenant_hash < canary_threshold:
            # 灰度范围内，立即编译
            logger.info(f"Tenant {tenant_id} in canary group, compiling now")
            return await self.compiler.compile(tenant_id)
        else:
            # 灰度范围外，懒加载
            await self.cache.mark_stale(tenant_id, reason="L0_HIGH_CANARY")
            return CompileResult(
                success=True,
                config=last_compile,
                message=f"L0重要更新灰度发布中（{canary_threshold}%），当前租户延后生效"
            )
    
    async def _compile_delta(
        self, 
        tenant_id: str, 
        changed_rules: List[Rule],
        base_compile: CompiledConfig
    ) -> CompileResult:
        """
        编译变更的规则片段（支持新增、修改、删除）
        
        变更检测逻辑：
        1. 加载当前全量L2规则
        2. 对比上次编译的规则集合
        3. 识别新增、修改、删除的规则
        4. 更新编译配置
        """
        # 1. 加载当前全量L2规则
        current_rules = await self.compiler._load_l2_rules(tenant_id)
        current_rule_ids = {r.id for r in current_rules}
        
        # 2. 基于上次编译结果创建新配置（深拷贝，防止缓存污染）
        import copy
        new_config = copy.deepcopy(base_compile)
        
        # 3. 处理规则变更
        for rule in changed_rules:
            if rule.is_deleted:
                # 删除规则
                if rule.id in new_config.rules:
                    del new_config.rules[rule.id]
                    logger.info(f"Rule {rule.id} deleted for tenant {tenant_id}")
            elif rule.id in current_rule_ids:
                # 修改规则：重新编译
                compiled = await self.compiler.dsl_parser.parse(rule)
                new_config.rules[rule.id] = compiled
                logger.info(f"Rule {rule.id} updated for tenant {tenant_id}")
            else:
                # 新增规则
                compiled = await self.compiler.dsl_parser.parse(rule)
                new_config.rules[rule.id] = compiled
                logger.info(f"Rule {rule.id} added for tenant {tenant_id}")
        
        # 4. 清理已删除的规则（软删除标记）
        base_rule_ids = set(new_config.rules.keys())
        deleted_ids = base_rule_ids - current_rule_ids
        for deleted_id in deleted_ids:
            if deleted_id not in {r.id for r in changed_rules}:
                # 规则被物理删除但未通过changed_rules传递
                del new_config.rules[deleted_id]
                logger.warning(f"Orphan rule {deleted_id} cleaned for tenant {tenant_id}")
        
        # 5. 更新版本号和时间戳
        new_config.version = self._bump_version(base_compile.version)
        new_config.compiled_at = datetime.now()
        
        return CompileResult(success=True, config=new_config)
```

---

## 3. 查询引擎设计

### 3.1 NLQ分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        查询请求                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  第一层：意图分类器 (IntentClassifier)                           │
│  ├── 模型: TinyBERT/DistilBERT (量化版)                          │
│  ├── 延迟: <50ms (CPU) / <10ms (GPU)                            │
│  ├── 准确率: >95%                                               │
│  ├── 硬件要求: 4核8G 或 T4 GPU                                   │
│  └── 输出: 预定义意图ID + 置信度                                  │
└─────────────────────────────────────────────────────────────────┘

**模型选型对比：**

| 模型 | 延迟(CPU) | 延迟(GPU) | 准确率 | 模型大小 | 推荐场景 |
|------|-----------|-----------|--------|----------|----------|
| **TinyBERT** | 20-50ms | 5-10ms | 92-95% | 15MB | 生产环境首选 |
| **DistilBERT** | 30-80ms | 8-15ms | 94-96% | 66MB | 准确率优先 |
| **BERT-base** | 100-200ms | 20-50ms | 96-98% | 440MB | 不推荐 |
| **FastText** | <5ms | <1ms | 85-90% | 100MB | 简单分类备用 |
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
        ┌──────────────────┐   ┌──────────────────┐
        │  预定义意图分支   │   │  LLM解析分支     │
        │  (置信度>0.9)    │   │  (置信度<=0.9)   │
        │                  │   │                  │
        │ • 模板匹配       │   │ • LLM语义解析    │
        │ • 槽位填充       │   │ • 中间表示生成   │
        │ • 确定性SQL生成  │   │ • 用户确认       │
        │                  │   │ • SQL生成        │
        └────────┬─────────┘   └────────┬─────────┘
                 │                      │
                 └──────────┬───────────┘
                            ▼
        ┌──────────────────────────────────────────────────┐
        │  查询执行层                                       │
        │  ├── SQL执行 (PostgreSQL)                         │
        │  ├── 结果缓存 (Redis)                             │
        │  └── 结果组装 (FIBO语义包装)                      │
        └──────────────────────────────────────────────────┘
```

### 3.2 意图分类器设计

```python
class IntentClassifier:
    """
    意图分类器 - TinyBERT本地部署 + LLM Fallback
    
    内存优化策略：
    1. 使用单例模式避免多Worker重复加载
    2. 支持模型热更新（无需重启服务）
    3. 生产环境建议使用独立模型服务
    """
    
    _instance = None
    _model_lock = threading.Lock()
    _model_cache = {}
    
    def __new__(cls, *args, **kwargs):
        """单例模式：确保每个进程只有一个分类器实例"""
        if cls._instance is None:
            with cls._model_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, model_path: str, llm_client: LLMClient = None):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self.model_path = model_path
        self._load_model()
        
        # 预定义意图模板
        self.intent_templates = self._load_intent_templates()
        
        # LLM客户端（用于低置信度查询）
        self.llm_client = llm_client
        self.llm_confidence_threshold = 0.7
        
        # 熔断器配置
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            expected_exception=LLMError
        )
        
        self._initialized = True
    
    def _load_model(self):
        """加载模型（带缓存机制）"""
        cache_key = self.model_path
        
        if cache_key not in self._model_cache:
            with self._model_lock:
                if cache_key not in self._model_cache:
                    logger.info(f"Loading model from {self.model_path}")
                    tokenizer = BertTokenizer.from_pretrained(self.model_path)
                    model = BertForSequenceClassification.from_pretrained(self.model_path)
                    model.eval()
                    self._model_cache[cache_key] = (tokenizer, model)
        
        self.tokenizer, self.model = self._model_cache[cache_key]
    
    def reload_model(self, new_model_path: str = None):
        """热更新模型（无需重启服务）"""
        with self._model_lock:
            old_path = self.model_path
            self.model_path = new_model_path or old_path
            # 清除旧缓存，强制重新加载
            if old_path in self._model_cache:
                del self._model_cache[old_path]
            self._load_model()
            logger.info(f"Model reloaded from {self.model_path}")
    
    async def classify(self, query: str, context: QueryContext) -> ClassificationResult:
        """
        分类查询意图（分层架构）
        
        流程：
        1. 模板匹配（快速路径，100%准确）
        2. BERT模型分类（90%查询）- 通过 to_thread 避免阻塞事件循环
        3. LLM语义解析（Fallback，复杂查询）
        
        性能说明：
        - 模板匹配：<1ms，纯内存操作
        - BERT推理：20-50ms（TinyBERT），通过 to_thread 不阻塞
        - LLM调用：200-500ms，异步非阻塞
        
        内存评估：
        | 模型 | 单进程内存 | 4 Worker | 推荐部署 |
        |------|-----------|----------|----------|
        | TinyBERT | 15MB | 60MB | ✅ 嵌入式 |
        | DistilBERT | 66MB | 264MB | ⚠️ 注意 |
        | BERT-base | 440MB | 1.76GB | ❌ 独立部署 |
        
        建议生产环境配置：
        - TinyBERT: 直接嵌入式部署（内存开销可控）
        - DistilBERT: 2-3 Worker + 共享内存
        - BERT-base: 独立 Model Server（TorchServe/Triton）
        """
        # 1. 模板匹配（快速路径，纯内存操作，不阻塞）
        template_match = self._match_template(query)
        if template_match and template_match.confidence > 0.95:
            return ClassificationResult(
                intent_id=template_match.intent_id,
                confidence=template_match.confidence,
                slots=template_match.slots,
                matched_pattern=template_match.pattern,
                requires_confirmation=False,
                query_type="predefined"
            )
        
        # 2. BERT模型分类（通过 to_thread 避免阻塞事件循环）
        # CPU密集型推理操作必须放入线程池
        import asyncio
        confidence_score, predicted_class_id = await asyncio.to_thread(
            self._bert_inference, query
        )
        
        # 3. 高置信度：直接返回BERT结果
        if confidence_score >= 0.9:
            intent_id = self.model.config.id2label[predicted_class_id]
            slots = self._extract_slots(query, intent_id)
            
            return ClassificationResult(
                intent_id=intent_id,
                confidence=confidence_score,
                slots=slots,
                matched_pattern=None,
                requires_confirmation=False,
                query_type="bert_classified"
            )
        
        # 4. 中置信度：BERT结果 + 需要确认
        if confidence_score >= self.llm_confidence_threshold:
            intent_id = self.model.config.id2label[predicted_class.item()]
            slots = self._extract_slots(query, intent_id)
            
            return ClassificationResult(
                intent_id=intent_id,
                confidence=confidence_score,
                slots=slots,
                matched_pattern=None,
                requires_confirmation=True,
                query_type="bert_uncertain"
            )
        
        # 5. 低置信度：LLM Fallback
        return await self._llm_parse(query, context)
    
    async def _llm_parse(self, query: str, context: QueryContext) -> ClassificationResult:
        """
        LLM语义解析（Fallback）
        
        适用场景：
        - BERT置信度 < 0.7
        - 复杂查询（多条件、聚合、对比）
        - 未在预定义意图中的查询
        """
        if not self.llm_client:
            # LLM不可用，返回拒绝
            return ClassificationResult(
                intent_id="unknown",
                confidence=0.0,
                slots={},
                requires_confirmation=True,
                query_type="rejected",
                message="无法理解的查询，请使用标准问法"
            )
        
        # 构建LLM Prompt
        prompt = self._build_llm_prompt(query, context)
        
        # 调用LLM
        llm_response = await self.llm_client.complete(
            prompt=prompt,
            temperature=0.1,  # 低温度，确定性输出
            max_tokens=500
        )
        
        # 解析LLM输出
        parsed = self._parse_llm_response(llm_response)
        
        return ClassificationResult(
            intent_id=parsed.intent_id,
            confidence=parsed.confidence,
            slots=parsed.slots,
            raw_query=query,
            parsed_intent=parsed.description,
            requires_confirmation=True,  # LLM解析必须确认
            query_type="llm_parsed"
        )
    
    def _build_llm_prompt(self, query: str, context: QueryContext) -> str:
        """构建LLM解析Prompt"""
        return f"""你是一个财务数据查询解析助手。请将用户的自然语言查询解析为结构化意图。

用户查询: {query}
上下文: {context}

请解析以下信息并以JSON格式返回:
{{
    "intent_id": "查询意图ID",
    "intent_name": "意图名称",
    "confidence": 0.0-1.0,
    "slots": {{
        "time": "时间范围",
        "entity": "查询对象",
        "metric": "指标"
    }},
    "description": "解析说明",
    "sql_hint": "SQL生成提示"
}}

注意：
- 只返回JSON，不要其他解释
- 置信度要客观评估
- 不支持的查询返回 confidence: 0
"""
    
    def _parse_llm_response(self, response: str) -> LLMParsedResult:
        """
        解析LLM输出（鲁棒性增强）
        
        处理场景：
        1. 标准JSON格式
        2. Markdown代码块包裹（```json ... ```）
        3. 多余文本前缀/后缀
        4. 解析失败时优雅降级
        """
        import json
        import re
        
        try:
            # 1. 预处理：去除Markdown代码块标记
            code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
            match = re.search(code_block_pattern, response)
            if match:
                response = match.group(1).strip()
            
            # 2. 尝试提取JSON对象（从第一个 { 到最后一个 }）
            json_pattern = r'\{[\s\S]*\}'
            json_match = re.search(json_pattern, response)
            if json_match:
                response = json_match.group(0)
            
            # 3. 清理常见格式问题
            response = response.strip().lstrip('\ufeff')
            
            # 4. 解析JSON
            data = json.loads(response)
            
            # 5. 验证必要字段
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            
            return LLMParsedResult(
                intent_id=data.get('intent_id', 'unknown'),
                confidence=data.get('confidence', 0.0),
                slots=data.get('slots', {}),
                description=data.get('description', '')
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"LLM response parsing failed: {e}")
            return LLMParsedResult(
                intent_id="unknown",
                confidence=0.0,
                slots={},
                description="LLM解析失败"
            )
    
    def _bert_inference(self, query: str) -> Tuple[float, int]:
        """
        BERT模型推理（同步方法，供 to_thread 调用）
        
        注意：此方法为CPU密集型操作，
        必须通过 asyncio.to_thread 调用，
        避免阻塞FastAPI事件循环
        """
        inputs = self.tokenizer(
            query, 
            return_tensors="pt", 
            padding=True, 
            truncation=True,
            max_length=128
        )
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=1)
            confidence, predicted_class = torch.max(probabilities, dim=1)
        
        return confidence.item(), predicted_class.item()
    
    def _match_template(self, query: str) -> Optional[TemplateMatch]:
        """模板匹配 - 快速路径"""
        for intent in self.intent_templates:
            for pattern in intent.patterns:
                match = self._match_pattern(query, pattern)
                if match:
                    return TemplateMatch(
                        intent_id=intent.id,
                        confidence=1.0,
                        slots=match.slots,
                        pattern=pattern
                    )
        return None


class QueryEngine:
    """查询引擎"""
    
    def __init__(
        self,
        classifier: IntentClassifier,
        rule_matcher: RuleMatcher,
        sql_generator: SQLGenerator,
        cache: QueryCache
    ):
        self.classifier = classifier
        self.rule_matcher = rule_matcher
        self.sql_generator = sql_generator
        self.cache = cache
    
    async def query(
        self, 
        tenant_id: str, 
        query_text: str,
        context: QueryContext,
        options: QueryOptions
    ) -> QueryResult:
        """
        执行查询
        
        完整流程：
        0. 编译状态检查（阻断/降级）
        1. 意图分类
        2. 规则匹配
        3. SQL生成
        4. 查询执行
        5. 结果组装
        """
        
        # 0. 编译状态检查（防止查询使用过时规则）
        compile_status = await self.cache.get_compile_status(tenant_id)
        if compile_status in ("L0_CRITICAL", "L0_HIGH_COMPILING"):
            # 编译中，阻断查询
            return QueryResult(
                status=QueryStatus.SERVICE_UNAVAILABLE,
                message="系统规则更新中，请稍后重试",
                retry_after=30  # 建议客户端30秒后重试
            )
        elif compile_status in ("L0_CRITICAL_FAILED", "L0_CRITICAL_ERROR"):
            # 编译失败，严禁使用旧版本规则（合规要求）
            return QueryResult(
                status=QueryStatus.RULE_COMPILE_FAILED,
                message="系统规则更新失败，请联系管理员",
                admin_alert=True  # 触发管理员告警
            )
        elif compile_status == "STALE":
            # 规则过期但仍在max_staleness内，允许查询但附加警告
            staleness = await self.cache.get_staleness_seconds(tenant_id)
            logger.warning(
                f"Tenant {tenant_id} using stale rules "
                f"(staleness={staleness}s)"
            )
        
        # 1. 意图分类
        classification = await self.classifier.classify(query_text, context)
        
        # 2. 检查是否需要确认
        if classification.requires_confirmation and not options.skip_confirmation:
            return QueryResult(
                status=QueryStatus.REQUIRES_CONFIRMATION,
                classification=classification,
                message="请确认查询意图"
            )
        
        # 3. 规则匹配
        compiled_rules = await self.cache.get_compiled_rules(tenant_id)
        matched_rule = self.rule_matcher.match(
            classification.intent_id,
            classification.slots,
            compiled_rules
        )
        
        # 4. SQL生成（安全参数化）
        sql, params = self.sql_generator.generate_safe(
            matched_rule,
            classification.slots,
            context
        )
        
        # 5. 执行查询（使用参数化查询防止SQL注入）
        result = await self._execute_sql_safe(tenant_id, sql, params)
        
        # 6. 结果组装
        return QueryResult(
            status=QueryStatus.SUCCESS,
            data=result,
            sql=sql if options.require_sql_preview else None,
            execution_time_ms=result.execution_time
        )


### 3.4 RDF到SQL语义映射层

#### 映射核心概念

```
┌─────────────────────────────────────────────────────────────────┐
│                     RDF到SQL映射层                               │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  FIBO本体   │───▶│  映射规则   │───▶│   SQL查询模板       │  │
│  │  (RDF)      │    │  (L0/L1/L2) │    │   (参数化)          │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                     │               │
│         ▼                  ▼                     ▼               │
│  loan:LoanContract    表: bd_loan_contract    SELECT ...        │
│  loan:loanAmount      字段: loan_amount       FROM ... WHERE    │
│  loan:hasBorrower     关联: customer_id       JOIN ...          │
└─────────────────────────────────────────────────────────────────┘
```

#### 映射规则定义

```python
class SemanticMapping:
    """语义映射定义"""
    
    # FIBO概念到物理表的映射
    concept_to_table: Dict[str, str] = {
        "loan:LoanContract": "bd_loan_contract",
        "loan:LoanAmount": "bd_loan_contract.loan_amount",
        "fibo:Customer": "bd_customer",
        # ... 更多映射
    }
    
    # 关系映射（处理多表JOIN）
    relation_to_join: Dict[str, JoinDefinition] = {
        "loan:hasBorrower": JoinDefinition(
            from_table="bd_loan_contract",
            from_field="customer_id",
            to_table="bd_customer",
            to_field="id",
            join_type="INNER"
        ),
        # ... 更多关系
    }


class SQLGenerator:
    """安全SQL生成器 - RDF到SQL语义映射"""
    
    def __init__(self, mapping: SemanticMapping):
        self.mapping = mapping
        # 白名单从映射配置动态加载
        self.allowed_tables = set(mapping.concept_to_table.values())
    
    def generate_safe(
        self,
        matched_rule: Rule,
        slots: Dict[str, Any],
        context: QueryContext
    ) -> Tuple[str, Tuple]:
        """
        生成安全的参数化SQL（含语义映射）
        
        流程：
        1. 语义解析：将FIBO概念映射到物理表字段
        2. 关系解析：处理多表关联（JOIN）
        3. SQL构建：参数化查询生成
        4. 安全校验：白名单验证
        """
        # 1. 语义映射：FIBO概念 -> 物理表字段
        table_mapping = self._resolve_concept_to_table(matched_rule.concept)
        column_mappings = [
            self._resolve_property_to_column(prop)
            for prop in matched_rule.properties
        ]
        
        # 2. 关系解析：检测并构建JOIN
        joins = self._resolve_relations(matched_rule.relations)
        
        # 3. 构建参数化SQL
        sql_parts = ["SELECT"]
        
        # 字段列表（带表别名）
        columns = [f"{m.table_alias}.{m.column} AS {m.alias}" 
                   for m in column_mappings]
        sql_parts.append(", ".join(columns))
        
        # FROM子句
        sql_parts.append(f"FROM {table_mapping.table_name} AS {table_mapping.alias}")
        
        # JOIN子句
        for join in joins:
            sql_parts.append(
                f"{join.join_type} JOIN {join.table} AS {join.alias} "
                f"ON {join.on_condition}"
            )
        
        # WHERE子句（参数化）
        conditions, params = self._build_parametrized_conditions(slots)
        if conditions:
            sql_parts.append(f"WHERE {' AND '.join(conditions)}")
        
        # 4. 安全校验
        sql = " ".join(sql_parts)
        self._validate_sql_safety(sql)
        
        return sql, tuple(params)
    
    def _resolve_concept_to_table(self, concept: str) -> TableMapping:
        """解析FIBO概念到物理表"""
        table_name = self.mapping.concept_to_table.get(concept)
        if not table_name:
            raise MappingError(f"未定义的FIBO概念: {concept}")
        
        # 验证表名安全
        if table_name not in self.allowed_tables:
            raise SecurityError(f"非法表名: {table_name}")
        
        return TableMapping(
            concept=concept,
            table_name=table_name,
            alias=self._generate_alias(table_name)
        )
    
    def _resolve_relations(self, relations: List[str]) -> List[JoinDefinition]:
        """解析关系为多表JOIN定义"""
        joins = []
        for rel in relations:
            join_def = self.mapping.relation_to_join.get(rel)
            if join_def:
                joins.append(join_def)
        return joins
    
    def _build_parametrized_conditions(
        self, 
        slots: Dict[str, Any],
        table_mapping: TableMapping
    ) -> Tuple[List[str], List[Any]]:
        """
        构建参数化WHERE条件（强化安全防护）
        
        安全策略：
        1. 字段名必须从SemanticMapping白名单中查找
        2. 禁止直接拼接任何用户输入到SQL
        3. 使用数据库驱动的identifier quote机制
        """
        conditions = []
        params = []
        
        for slot_name, slot_value in slots.items():
            # 1. 从映射中查找合法的字段名（白名单校验）
            column_name = self._resolve_slot_to_column(slot_name, table_mapping)
            if not column_name:
                raise SecurityError(f"未定义的槽位名: {slot_name}")
            
            # 2. 使用数据库驱动的quote_ident（防止关键字冲突和注入）
            quoted_column = self._quote_identifier(column_name)
            
            # 3. 使用参数占位符（值部分）
            conditions.append(f"{quoted_column} = %s")
            params.append(slot_value)
        
        return conditions, params
    
    def _resolve_slot_to_column(
        self, 
        slot_name: str, 
        table_mapping: TableMapping
    ) -> Optional[str]:
        """
        将槽位名解析为数据库字段名（白名单机制）
        
        解析顺序：
        1. 查找SemanticMapping中的字段映射
        2. 验证字段是否属于目标表
        3. 返回合法的数据库字段名
        """
        # 从映射配置中查找
        full_mapping_key = f"{table_mapping.concept}.{slot_name}"
        column_path = self.mapping.concept_to_table.get(full_mapping_key)
        
        if column_path:
            # 解析 table.column 格式
            parts = column_path.split('.')
            if len(parts) == 2:
                table, column = parts
                # 验证表名匹配
                if table == table_mapping.table_name:
                    return column
        
        # 未找到映射，拒绝执行
        logger.warning(f"Slot '{slot_name}' not found in mapping for {table_mapping.concept}")
        return None
    
    def _quote_identifier(self, identifier: str) -> str:
        """
        标识符安全引用（应用层实现，不依赖psycopg2）
        
        架构决策：
        - 不使用psycopg2.quote_ident（同步IO，阻塞事件循环）
        - 使用PostgreSQL标准引用规则：双引号包裹 + 内部双引号转义
        - 仅用于白名单中已验证的标识符，安全有保障
        """
        # PostgreSQL标准：双引号包裹标识符
        # 转义标识符中可能的双引号
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
    
    def _validate_sql_safety(self, sql: str):
        """
        SQL安全校验（白名单为主，黑名单为辅）
            
        安全哲学：
        - 主要防线：参数化查询 + 白名单机制（_resolve_slot_to_column）
        - 辅助防线：本方法的黑名单检查（防纵深攻击）
        - 最终权限：数据库只读账号（见4.1节）
            
        注意：不依赖sqlparse进行安全校验
        （sqlparse是语法解析器，非安全工具，容易被绕过）
        """
        # 1. 黑名单检查（轻量级，防纵深攻击）
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 
            'TRUNCATE', 'ALTER', 'CREATE', 'GRANT',
            'EXECUTE', 'EXEC', 'XP_', 'LOAD_'
        ]
        upper_sql = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in upper_sql:
                raise SecurityError(f"SQL包含危险操作: {keyword}")
            
        # 2. 检查是否有分号（防止多语句注入）
        if ';' in sql.strip().rstrip(';'):
            raise SecurityError("SQL包含非法分号")
            
        # 3. 检查注释符号（防止注释注入）
        if '--' in sql or '/*' in sql:
            raise SecurityError("SQL包含非法注释")
        
    def _get_readonly_connection(self, tenant_id: str):
        """
        获取只读数据库连接（最终权限防线）
            
        安全策略：
        1. 使用专用的只读账号连接业务库
        2. 该账号仅拥有 SELECT 权限
        3. 即使SQL注入成功，也无法修改数据
            
        配置示例（PostgreSQL）：
        CREATE ROLE query_readonly WITH LOGIN PASSWORD 'xxx';
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO query_readonly;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT SELECT ON TABLES TO query_readonly;
        """
        return self.readonly_pool.getconn(tenant_id)```
```

### 3.3 查询确认机制

```python
class QueryConfirmationService:
    """查询确认服务"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.token_ttl = 300  # 5分钟
    
    async def create_confirmation(
        self, 
        tenant_id: str,
        classification: ClassificationResult,
        sql_preview: str
    ) -> ConfirmationToken:
        """创建确认令牌"""
        
        token = self._generate_token()
        confirmation_data = {
            "tenant_id": tenant_id,
            "intent_id": classification.intent_id,
            "slots": classification.slots,
            "sql_preview": sql_preview,
            "confidence": classification.confidence,
            "created_at": datetime.now().isoformat()
        }
        
        # 存储到Redis
        await self.redis.setex(
            f"confirm:{token}",
            self.token_ttl,
            json.dumps(confirmation_data)
        )
        
        return ConfirmationToken(
            token=token,
            expires_in=self.token_ttl,
            preview=confirmation_data
        )
    
    async def confirm_and_execute(
        self, 
        token: str,
        confirmed: bool
    ) -> QueryResult:
        """确认并执行查询"""
        
        # 获取确认数据
        data = await self.redis.get(f"confirm:{token}")
        if not data:
            return QueryResult(
                status=QueryStatus.ERROR,
                message="确认令牌已过期或无效"
            )
        
        confirmation = json.loads(data)
        
        if not confirmed:
            return QueryResult(
                status=QueryStatus.CANCELLED,
                message="用户取消查询"
            )
        
        # 执行查询
        result = await self._execute_confirmed_query(confirmation)
        
        # 删除令牌
        await self.redis.delete(f"confirm:{token}")
        
        return result
```

---

## 4. 数据存储设计

### 4.1 存储架构

| 数据类型 | 存储介质 | 用途 | 访问模式 |
|----------|----------|------|----------|
| **L0规则** | GraphDB | FIBO标准本体 | 只读，全局共享 |
| **L1规则** | GraphDB | 行业映射规则 | 读多写少，按行业共享 |
| **L2规则** | PostgreSQL | 租户私有规则 | 读写频繁，租户隔离 |
| **编译后规则** | Redis | 可执行配置 | 高频读取，TTL过期 |
| **查询结果** | Redis | 计算结果缓存 | 高频读写，事件失效 |
| **审计日志** | PostgreSQL | 查询记录 | 只写，定期归档 |

### 4.2 GraphDB Schema (L0+L1) + 性能优化

#### GraphDB性能优化策略

| 优化手段 | 配置 | 效果 |
|----------|------|------|
| **Lucene全文索引** | 对规则名称、描述建立索引 | 规则查询从500ms降至50ms |
| **实体池(Entity Pool)** | 启用 transactional 模式 | 减少内存占用30% |
| **推理优化** | 禁用不必要的OWL推理 | 查询性能提升2-3倍 |
| **连接池** | 最大连接数50，超时30s | 防止连接泄漏 |
| **结果缓存** | 启用GraphDB内部查询缓存 | 热点查询<10ms |

#### GraphDB连接管理

```python
class GraphDBClient:
    """
    GraphDB客户端 - 双模式（异步/同步）
    
    架构说明：
    - 异步模式：供FastAPI查询引擎使用（httpx.AsyncClient）
    - 同步模式：供Celery Worker编译器使用（requests.Session）
    - 两种模式共享同一配置，但使用不同的HTTP库
    """
    
    def __init__(self, endpoint: str, repo: str):
        self.endpoint = endpoint
        self.repo = repo
        
        # 异步客户端配置
        self._async_session = None
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.limits = httpx.Limits(
            max_connections=50,
            max_keepalive_connections=10
        )
        
        # 同步客户端配置（供Celery Worker使用）
        self._sync_session = None
    
    # ---- 异步模式（FastAPI查询引擎） ----
    
    async def _get_async_session(self) -> httpx.AsyncClient:
        """获取异步HTTP客户端（延迟初始化）"""
        if self._async_session is None:
            self._async_session = httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits
            )
        return self._async_session
        
    async def query_rules(
        self, 
        industry: str = None,
        use_cache: bool = True
    ) -> List[Rule]:
        """
        查询规则（异步模式）
        
        适用场景：FastAPI查询引擎、API层调用
        """
        cache_hint = "pragma: cache" if use_cache else "pragma: no-cache"
        
        sparql = f"""
        {cache_hint}
        PREFIX loanfibo: <http://loanfibo.org/ontology/>
        
        SELECT ?rule ?table ?field ?target
        WHERE {{
            ?rule a loanfibo:MappingRule .
            ?rule loanfibo:sourceTable ?table .
            OPTIONAL {{ ?rule loanfibo:sourceField ?field }}
            OPTIONAL {{ ?rule loanfibo:targetProperty ?target }}
            {'?rule loanfibo:industry "' + industry + '" .' if industry else ''}
        }}
        """
        
        session = await self._get_async_session()
        response = await session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"}
        )
        response.raise_for_status()
        
        return self._parse_results(response.json())
    
    # ---- 同步模式（Celery Worker编译器） ----
    
    def _get_sync_session(self) -> requests.Session:
        """获取同步HTTP客户端（供Celery Worker使用）"""
        if self._sync_session is None:
            self._sync_session = requests.Session()
            self._sync_session.headers.update({
                "Accept": "application/sparql-results+json"
            })
        return self._sync_session
    
    def query_rules_sync(
        self,
        industry: str = None,
        use_cache: bool = True
    ) -> List[Rule]:
        """
        查询规则（同步模式）
        
        适用场景：Celery Worker中的编译任务
        不使用 async/await，纯同步调用
        """
        cache_hint = "pragma: cache" if use_cache else "pragma: no-cache"
        
        sparql = f"""
        {cache_hint}
        PREFIX loanfibo: <http://loanfibo.org/ontology/>
        
        SELECT ?rule ?table ?field ?target
        WHERE {{
            ?rule a loanfibo:MappingRule .
            ?rule loanfibo:sourceTable ?table .
            OPTIONAL {{ ?rule loanfibo:sourceField ?field }}
            OPTIONAL {{ ?rule loanfibo:targetProperty ?target }}
            {'?rule loanfibo:industry "' + industry + '" .' if industry else ''}
        }}
        """
        
        session = self._get_sync_session()
        response = session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            timeout=30.0
        )
        response.raise_for_status()
        
        return self._parse_results(response.json())
    
    # ---- 共享方法 ----
    
    def _parse_results(self, data: dict) -> List[Rule]:
        """解析SPARQL查询结果"""
        results = []
        for binding in data.get('results', {}).get('bindings', []):
            results.append(Rule(
                id=binding.get('rule', {}).get('value'),
                table=binding.get('table', {}).get('value'),
                field=binding.get('field', {}).get('value'),
                target=binding.get('target', {}).get('value')
            ))
        return results
    
    async def close(self):
        """关闭所有HTTP客户端"""
        if self._async_session:
            await self._async_session.aclose()
        if self._sync_session:
            self._sync_session.close()```
```

#### GraphDB Schema

```turtle
# L0: FIBO标准本体
@prefix fibo: <https://spec.edmcouncil.org/fibo/> .
@prefix loan: <https://spec.edmcouncil.org/fibo/ontology/LOAN/> .

# 基础概念
loan:LoanContract a owl:Class ;
    rdfs:label "贷款合同" ;
    rdfs:comment "借贷双方签订的合同" .

loan:LoanAmount a owl:DatatypeProperty ;
    rdfs:domain loan:LoanContract ;
    rdfs:range xsd:decimal ;
    rdfs:label "贷款金额" .

# L1: 行业映射规则
@prefix loanfibo: <http://loanfibo.org/ontology/> .

loanfibo:MappingRule a owl:Class ;
    rdfs:label "映射规则" .

loanfibo:TableClassMapping a loanfibo:MappingRule ;
    loanfibo:sourceTable "bd_loan_contract" ;
    loanfibo:targetClass loan:LoanContract ;
    loanfibo:industry "credit" ;
    loanfibo:confidence "HIGH" .

loanfibo:FieldPropertyMapping a loanfibo:MappingRule ;
    loanfibo:sourceTable "bd_loan_contract" ;
    loanfibo:sourceField "loan_amount" ;
    loanfibo:targetProperty loan:LoanAmount ;
    loanfibo:dataType "DECIMAL" .
```

### 4.3 PostgreSQL Schema (L2+元数据)

```sql
-- 租户信息表
CREATE TABLE tenants (
    tenant_id VARCHAR(64) PRIMARY KEY,
    tenant_name VARCHAR(256) NOT NULL,
    industry VARCHAR(32) NOT NULL,
    tier VARCHAR(16) DEFAULT 'tier3',  -- tier1/tier2/tier3
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- L2规则表
CREATE TABLE tenant_rules (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id),
    rule_type VARCHAR(32) NOT NULL,  -- FIELD_ALIAS, FORMULA_OVERRIDE, CUSTOM_RULE
    rule_name VARCHAR(128) NOT NULL,
    rule_definition JSONB NOT NULL,
    priority INT DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(64),
    updated_by VARCHAR(64),
    UNIQUE(tenant_id, rule_name)
);

-- 编译状态表
CREATE TABLE tenant_compile_status (
    tenant_id VARCHAR(64) PRIMARY KEY REFERENCES tenants(tenant_id),
    status VARCHAR(16) NOT NULL,  -- PENDING, COMPILING, SUCCESS, FAILED
    version VARCHAR(64),
    error_message TEXT,
    last_compile_at TIMESTAMP,
    next_compile_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 审计日志表
CREATE TABLE query_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    query_text TEXT NOT NULL,
    intent_id VARCHAR(64),
    sql_executed TEXT,
    execution_time_ms INT,
    result_rows INT,
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(64)
);

-- 索引
CREATE INDEX idx_tenant_rules_tenant_id ON tenant_rules(tenant_id);
CREATE INDEX idx_tenant_rules_type ON tenant_rules(tenant_id, rule_type);
CREATE INDEX idx_audit_logs_tenant_time ON query_audit_logs(tenant_id, created_at);
```

### 4.4 Redis缓存设计

```
# 编译后规则缓存
Key: rules:{tenant_id}:latest
Value: JSON (CompiledConfig)
TTL: 7天

# 编译版本历史
Key: rules:{tenant_id}:versions
Value: Sorted Set (version -> timestamp)
TTL: 30天

# 查询结果缓存（含版本号保证一致性）
Key: calc:{tenant_id}:{version}:{formula_name}:{entity_id}:{date}:{params_hash}
Value: JSON (计算结果)
TTL: 按公式配置（30s ~ 5min）
注意: version为编译版本号，规则变更后自动失效

# 意图分类缓存
Key: intent:{query_hash}
Value: JSON (ClassificationResult)
TTL: 1小时

# 确认令牌
Key: confirm:{token}
Value: JSON (确认数据)
TTL: 5分钟
```

---

## 5. DSL设计

### 5.1 语法规范

```ebnf
formula           ::= scalar_expression | aggregate_expression

scalar_expression ::= term (('+' | '-') term)*
term              ::= factor (('*' | '/') factor)*
factor            ::= number | variable | scalar_function | '(' scalar_expression ')'

aggregate_expression ::= aggregate_function '(' aggregate_arg ')'
aggregate_function   ::= 'AGG_SUM' | 'AGG_AVG' | 'AGG_MAX' | 'AGG_MIN' | 'AGG_COUNT'
aggregate_arg        ::= column_ref ('WHERE' filter_expr)?
column_ref           ::= table_name '.' column_name | column_name
filter_expr          ::= scalar_expression

scalar_function   ::= func_name '(' arg_list? ')'
func_name         ::= 'DIVIDE' | 'ABS' | 'ROUND' | 'SUM' | 'AVG' | 'MAX' | 'MIN' | 'COALESCE' | 'IF'
arg_list          ::= scalar_expression (',' scalar_expression)*
variable          ::= [a-zA-Z_][a-zA-Z0-9_]*
number            ::= [0-9]+ ('.' [0-9]+)?
table_name        ::= [a-zA-Z_][a-zA-Z0-9_]*
column_name       ::= [a-zA-Z_][a-zA-Z0-9_]*
```

### 5.2 执行引擎

### 5.2 DSL执行引擎（双模式安全方案）

#### 技术选型对比

| 方案 | 安全性 | 性能 | 复杂度 | 适用场景 | 推荐度 |
|------|--------|------|--------|----------|--------|
| **RestrictedPython** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 简单公式（90%场景） | ✅ 首选 |
| **WASM沙箱** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 复杂/不可信代码 | 备选 |
| **预编译字节码** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 标准公式库 | 辅助 |

#### 推荐方案：RestrictedPython + 预编译缓存

```python
class DSLExecutor:
    """
    DSL执行引擎 - 多层安全防护
    
    架构决策：
    1. 默认使用 RestrictedPython（轻量、安全、易调试）
    2. 高风险场景可选 WASM 沙箱
    3. 热点公式预编译缓存
    """
    
    def __init__(
        self, 
        security_config: SecurityConfig,
        wasm_runtime: Optional[WasmRuntime] = None
    ):
        self.security = security_config
        self.wasm_runtime = wasm_runtime
        # 预编译缓存
        self._compiled_cache: Dict[str, CompiledFormula] = {}
        
    async def execute(
        self, 
        formula: str, 
        context: ExecutionContext,
        execution_mode: str = "auto"  # auto | restricted | wasm
    ) -> ExecutionResult:
        """
        执行DSL公式（多层安全防护）
        
        Args:
            formula: DSL公式字符串
            context: 执行上下文（变量值）
            execution_mode: 执行模式
                - auto: 自动选择（默认RestrictedPython）
                - restricted: 强制使用RestrictedPython
                - wasm: 强制使用WASM沙箱（需配置）
        """
        # 1. 解析公式
        ast = self._parse(formula)
        
        # 2. 安全检查
        if ast.depth > self.security.max_ast_depth:
            raise SecurityError(f"AST深度超过限制: {ast.depth}")
        
        # 3. 选择执行模式
        if execution_mode == "wasm" and self.wasm_runtime:
            # WASM模式（高风险场景）
            return await self._execute_wasm(ast, context)
        else:
            # 默认RestrictedPython模式
            return await self._execute_restricted(ast, context)
    
    async def _execute_restricted(
        self, 
        ast: AST, 
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        使用RestrictedPython执行（默认方案）
        
        优势：
        1. 纯Python实现，无需额外依赖
        2. 编译和执行性能优秀
        3. 易于调试和审计
        4. 安全限制明确（无文件/网络访问）
        
        超时机制：
        - 使用 asyncio.to_thread 将同步执行移至线程池
        - 使用 asyncio.wait_for 实现异步超时控制
        - 线程内通过操作步数计数器实现软超时
        - 兼容 Windows/Linux，不影响事件循环
        """
        from restrictedpython import compile_restricted
        from restrictedpython.Guards import safe_builtins
        
        # 1. 将AST转换为Python代码
        python_code = self._ast_to_python(ast)
        
        # 2. 使用RestrictedPython编译（安全检查）
        byte_code = compile_restricted(
            python_code,
            filename='<formula>',
            mode='eval'
        )
        
        if byte_code is None:
            raise SecurityError("公式编译失败，包含非法操作")
        
        # 3. 在受限环境中执行
        restricted_globals = {
            '__builtins__': safe_builtins,
            'math': __import__('math'),
            'decimal': __import__('decimal'),
        }
        restricted_globals.update(context.variables)
        
        # 4. 带超时的执行（asyncio安全）
        #    使用 to_thread 将同步 eval 移至线程池
        #    使用 wait_for 实现异步超时控制
        import asyncio
        
        # 定义同步执行函数（供 to_thread 调用）
        def _sync_eval():
            return eval(byte_code, restricted_globals)
        
        try:
            # asyncio.wait_for 是唯一的超时机制
            # 不使用 signal.alarm（异步环境不安全）
            result = await asyncio.wait_for(
                asyncio.to_thread(_sync_eval),
                timeout=self.security.execution_timeout
            )
            return ExecutionResult(value=result)
        except asyncio.TimeoutError:
            raise SecurityError(
                f"公式执行超时（{self.security.execution_timeout}秒）"
            )
        except Exception as e:
            raise SecurityError(f"公式执行异常: {e}")
    
    async def _execute_wasm(
        self, 
        ast: AST, 
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        使用WASM沙箱执行（备选方案）
        
        适用场景：
        1. 需要更强的隔离性
        2. 执行不可信代码
        3. 多语言混合场景
        
        注意：需要预编译工具链支持
        """
        if not self.wasm_runtime:
            raise ValueError("WASM运行时未配置")
        
        # 1. 编译为WASM（或从缓存获取）
        cache_key = hash(ast)
        if cache_key in self._compiled_cache:
            wasm_module = self._compiled_cache[cache_key]
        else:
            wasm_module = self._compile_to_wasm(ast)
            self._compiled_cache[cache_key] = wasm_module
        
        # 2. WASM沙箱执行
        result = await self.wasm_runtime.execute(
            wasm_module, 
            context,
            timeout=self.security.execution_timeout,
            memory_limit=self.security.memory_limit,
            disable_network=True,
            disable_file_system=True
        )
        
        return ExecutionResult(value=result)
    
    def _parse(self, formula: str) -> AST:
        """解析公式为AST"""
        parser = DSLParser()
        return parser.parse(formula)
    
    def _ast_to_python(self, ast: AST) -> str:
        """将AST转换为Python代码（用于RestrictedPython）"""
        # 简单的AST到Python转换器
        # 实际实现需要完整的遍历器
        generator = PythonCodeGenerator()
        return generator.generate(ast)
    
    def _compile_to_wasm(self, ast: AST) -> WasmModule:
        """编译AST为WASM模块（备选方案）"""
        # 注意：需要完整的DSL-to-WASM编译链
        # 建议使用 AssemblyScript 或 Rust 作为中间语言
        compiler = WASMCompiler()
        return compiler.compile(ast)
```

#### 安全对比说明

| 安全维度 | RestrictedPython | WASM沙箱 |
|----------|------------------|----------|
| **代码注入** | ✅ 编译期阻止 | ✅ 完全隔离 |
| **文件访问** | ❌ 禁止 | ❌ 禁止 |
| **网络访问** | ❌ 禁止 | ❌ 禁止 |
| **系统调用** | ❌ 禁止 | ❌ 禁止 |
| **内存限制** | ⚠️ 依赖Python | ✅ 硬性限制 |
| **执行开销** | ⭐⭐⭐⭐⭐ 极低 | ⭐⭐⭐ 中等 |
| **调试难度** | ⭐⭐⭐⭐⭐ 简单 | ⭐⭐⭐ 复杂 |

---

## 6. 接口设计

### 6.1 查询API

```yaml
openapi: 3.0.0
info:
  title: GraphDB规则引擎API
  version: 2.0.0

paths:
  /api/v2/query:
    post:
      summary: 自然语言查询
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                tenant_id:
                  type: string
                query:
                  type: string
                  description: 自然语言查询
                context:
                  type: object
                options:
                  type: object
                  properties:
                    skip_confirmation:
                      type: boolean
                    require_sql_preview:
                      type: boolean
      responses:
        200:
          description: 查询成功或需要确认
          content:
            application/json:
              schema:
                oneOf:
                  - $ref: '#/components/schemas/QuerySuccess'
                  - $ref: '#/components/schemas/QueryConfirmation'

  /api/v2/query/confirm:
    post:
      summary: 确认并执行查询
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                token:
                  type: string
                confirmed:
                  type: boolean

  /api/v2/rules/compile:
    post:
      summary: 触发规则编译
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                tenant_id:
                  type: string
                priority:
                  type: string
                  enum: [high, normal, low]

  /api/v2/rules/{tenant_id}:
    get:
      summary: 获取租户规则
    put:
      summary: 更新租户规则

  /api/v2/rules/{tenant_id}/rollback:
    post:
      summary: 规则版本回滚
      description: 快速回滚到指定版本或上一版本
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                version:
                  type: string
                  description: 目标版本号（为空则回滚到上一版本）
                reason:
                  type: string
                  description: 回滚原因
      responses:
        200:
          description: 回滚成功
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                  previous_version:
                    type: string
                  current_version:
                    type: string
                  message:
                    type: string

  /api/v2/rules/{tenant_id}/versions:
    get:
      summary: 获取规则版本历史
      responses:
        200:
          description: 版本列表
          content:
            application/json:
              schema:
                type: object
                properties:
                  versions:
                    type: array
                    items:
                      type: object
                      properties:
                        version:
                          type: string
                        compiled_at:
                          type: string
                        status:
                          type: string
                          enum: [active, stale, rollbacked]
```

#### 回滚服务实现

```python
class RuleRollbackService:
    """规则回滚服务 - 支持PostgreSQL持久化"""
    
    def __init__(
        self, 
        cache: CompileCache, 
        compiler: RuleCompiler,
        pg_client: PostgreSQLClient  # PostgreSQL客户端
    ):
        self.cache = cache
        self.compiler = compiler
        self.pg = pg_client
    
    async def rollback(
        self,
        tenant_id: str,
        target_version: str = None,
        reason: str = None
    ) -> RollbackResult:
        """
        规则版本回滚（双写：Redis + PostgreSQL）
        
        持久化策略：
        1. PostgreSQL作为Source of Truth存储版本状态
        2. Redis作为热点缓存加速读取
        3. 回滚操作先更新PG，再更新Redis
        
        Args:
            tenant_id: 租户ID
            target_version: 目标版本号（None则回滚到上一版本）
            reason: 回滚原因
            
        Returns:
            RollbackResult: 回滚结果
        """
        # 1. 获取当前版本（从PG查询，确保一致性）
        current = await self._get_active_version_from_pg(tenant_id)
        if not current:
            raise RollbackError("当前无可用规则版本")
        
        # 2. 确定目标版本
        if not target_version:
            # 从PG获取版本历史
            versions = await self._get_version_history_from_pg(tenant_id, limit=2)
            if len(versions) < 2:
                raise RollbackError("无历史版本可回滚")
            target_version = versions[1].version  # 上一版本
        
        # 3. 验证目标版本存在
        target_config = await self._get_version_from_pg(tenant_id, target_version)
        if not target_config:
            raise RollbackError(f"目标版本 {target_version} 不存在")
        
        # 4. 双写：先更新PostgreSQL（Source of Truth）
        async with self.pg.transaction() as tx:
            # 更新租户编译状态表
            await tx.execute(
                """
                UPDATE tenant_compile_status 
                SET version = $1, 
                    status = 'ROLLBACKED',
                    previous_version = $2,
                    rolled_back_at = NOW(),
                    rollback_reason = $3
                WHERE tenant_id = $4
                """,
                target_version,
                current.version,
                reason,
                tenant_id
            )
            
            # 插入版本历史记录
            await tx.execute(
                """
                INSERT INTO tenant_version_history 
                (tenant_id, version, action, action_at, reason)
                VALUES ($1, $2, 'ROLLBACK', NOW(), $3)
                """,
                tenant_id,
                target_version,
                reason
            )
        
        # 5. 再更新Redis缓存
        await self.cache.activate_version(tenant_id, target_version)
        
        # 6. 记录回滚操作到审计日志
        await self._record_rollback(
            tenant_id=tenant_id,
            from_version=current.version,
            to_version=target_version,
            reason=reason
        )
        
        return RollbackResult(
            success=True,
            previous_version=current.version,
            current_version=target_version,
            message=f"成功回滚到版本 {target_version}（已持久化到数据库）"
        )
    
    async def _get_active_version_from_pg(self, tenant_id: str) -> Optional[VersionInfo]:
        """从PostgreSQL获取当前激活版本"""
        row = await self.pg.fetchrow(
            """
            SELECT version, compiled_at, status
            FROM tenant_compile_status
            WHERE tenant_id = $1
            """,
            tenant_id
        )
        if row:
            return VersionInfo(
                version=row['version'],
                compiled_at=row['compiled_at'],
                status=row['status']
            )
        return None
    
    async def _get_version_history_from_pg(
        self, 
        tenant_id: str, 
        limit: int = 10
    ) -> List[VersionInfo]:
        """从PostgreSQL获取版本历史"""
        rows = await self.pg.fetch(
            """
            SELECT version, compiled_at, status
            FROM tenant_version_history
            WHERE tenant_id = $1
            ORDER BY compiled_at DESC
            LIMIT $2
            """,
            tenant_id,
            limit
        )
        return [
            VersionInfo(
                version=row['version'],
                compiled_at=row['compiled_at'],
                status=row['status']
            )
            for row in rows
        ]
    
    async def get_version_history(
        self,
        tenant_id: str,
        limit: int = 10
    ) -> List[VersionInfo]:
        """获取版本历史"""
        versions = await self.cache.get_version_history(tenant_id, limit)
        return [
            VersionInfo(
                version=v.version,
                compiled_at=v.compiled_at,
                status=v.status,
                is_active=(v.version == versions[0].version)
            )
            for v in versions
        ]
```

---

## 7. 部署架构

### 7.1 容器化部署

#### 开发环境（docker-compose.yml）

```yaml
# docker-compose.yml - 开发环境（单机多实例使用scale）
version: '3.8'

services:
  api-gateway:
    image: kong:3.0
    ports:
      - "8000:8000"
    
  query-engine:
    build: ./query-engine
    environment:
      - REDIS_URL=redis://redis:6379
      - GRAPHDB_URL=http://graphdb:7200
      - PG_URL=postgresql://postgres:5432/rules
    # 开发环境使用scale启动多实例: docker-compose up --scale query-engine=3
    
  rule-compiler:
    build: ./rule-compiler
    environment:
      - CELERY_BROKER_URL=redis://redis:6379
      - CELERY_RESULT_BACKEND=redis://redis:6379
    
  compiler-worker:
    build: ./rule-compiler
    command: celery -A tasks worker -P gevent --concurrency=10 --loglevel=info
    # 开发环境使用scale启动多worker: docker-compose up --scale compiler-worker=3
    
  graphdb:
    image: ontotext/graphdb:10.0
    volumes:
      - graphdb-data:/opt/graphdb/data
    environment:
      - GDB_HEAP_SIZE=4g
      - GDB_JAVA_OPTS=-Xmx4g -XX:MaxDirectMemorySize=2g
    # GraphDB性能优化：JVM堆内存4G，直接内存2G
    
  postgres:
    image: postgres:15
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_SHARED_BUFFERS=2GB
      - POSTGRES_EFFECTIVE_CACHE_SIZE=4GB
    # PostgreSQL性能优化
    
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    # Redis性能优化：最大内存2G，LRU淘汰策略

volumes:
  graphdb-data:
  postgres-data:
  redis-data:
```

#### 生产环境（Kubernetes）

```yaml
# k8s/query-engine-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: query-engine
spec:
  replicas: 3  # K8s中使用replicas
  selector:
    matchLabels:
      app: query-engine
  template:
    metadata:
      labels:
        app: query-engine
    spec:
      containers:
        - name: query-engine
          image: query-engine:latest
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
---
# k8s/compiler-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: compiler-worker
spec:
  replicas: 5
  selector:
    matchLabels:
      app: compiler-worker
  template:
    metadata:
      labels:
        app: compiler-worker
    spec:
      containers:
        - name: compiler-worker
          image: rule-compiler:latest
          command: ["celery", "-A", "tasks", "worker", "-P", "gevent", "--concurrency=10"]
```

---

## 8. 监控与运维

### 8.1 关键指标

| 指标类别 | 指标名称 | 告警阈值 |
|----------|----------|----------|
| **查询性能** | P99响应时间 | >100ms |
| **查询性能** | 错误率 | >0.1% |
| **编译性能** | 编译队列堆积 | >1000 |
| **编译性能** | 编译失败率 | >1% |
| **系统资源** | CPU使用率 | >80% |
| **系统资源** | 内存使用率 | >85% |
| **业务指标** | 缓存命中率 | <70% |
| **业务指标** | NLQ解析成功率 | <95% |

### 8.2 日志规范

```json
{
  "timestamp": "2026-04-20T10:30:00Z",
  "level": "INFO",
  "service": "query-engine",
  "trace_id": "abc-123",
  "tenant_id": "T_10086",
  "event": "query_executed",
  "duration_ms": 15,
  "intent_id": "query_balance",
  "sql": "SELECT...",
  "result_rows": 1
}
```

---

## 9. 后续计划

### 9.1 实施阶段

| 阶段 | 内容 | 周期 |
|------|------|------|
| **Phase 1** | 核心规则编译器 + 基础查询引擎 | 4周 |
| **Phase 2** | NLQ分层架构 + 意图分类器 | 3周 |
| **Phase 3** | 租户管理 + 可视化 | 3周 |
| **Phase 4** | 性能优化 + 压测 | 2周 |

### 9.2 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| BERT模型准确率不足 | NLQ体验差 | 持续优化+兜底模板 |
| 编译性能不达预期 | 规则更新延迟 | 增量编译+分布式集群 |
| GraphDB性能瓶颈 | 规则加载慢 | 缓存+读写分离 |

---

*设计文档完成，等待评审...*

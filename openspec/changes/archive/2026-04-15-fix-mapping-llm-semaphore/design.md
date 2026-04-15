## Context

`mapping_llm.py` 是 DDL-to-FIBO 映射 Pipeline 的核心节点，负责对每张数据库表调用 LLM 进行本体类映射。

当前实现：
```python
async def process_single_table(job_id, table_registry_id):
    async with mapping_semaphore:          # ❌ 包裹了所有操作
        async with async_session_factory() as db:
            table = await db.get(...)      # 数据库查询（不需要限流）
            candidates = await search_candidates(...)  # 向量检索（不需要限流）
            response = await llm.ainvoke(...)  # LLM 调用（需要限流）
            await save_result(...)         # 数据库写入（不需要限流）
```

问题：`MAX_CONCURRENCY=5` 的限流作用于整个函数，导致数据库查询和向量检索也被串行化，
实际并发仅为 5，而数据库/向量检索本可并发 50+。

## Goals / Non-Goals

**Goals:**
- 信号量只包裹 LLM 调用片段，释放数据库/检索的并发能力
- 函数按 DB查询 → 构建Prompt → LLM调用（限流）→ 保存结果 拆分为独立阶段
- 添加 `uncertainty_exit` 检查（llm-caller 原则 6）
- 用 `MAPPING_FALLBACK_MODEL` 替换语义错误的 `CRITIC_MODEL` 引用
- 为 `process_single_table` 建立单元测试覆盖

**Non-Goals:**
- 不修改 LangGraph Pipeline 拓扑结构
- 不修改 Prompt 内容
- 不引入新的外部依赖

## Decisions

### 决策 1：信号量作用范围精确化

**选择**: 将信号量移入函数内，只包裹 `llm.ainvoke(...)` 调用

```python
async def process_single_table(job_id, table_registry_id):
    # 1. 数据库查询（无限流）
    async with async_session_factory() as db:
        table = await db.get(...)
        candidates = await search_candidates(...)

    # 2. LLM 调用（限流）
    async with mapping_semaphore:
        response = await llm.ainvoke(messages)

    # 3. 保存结果（无限流）
    async with async_session_factory() as db:
        await save_result(...)
```

**理由**: LLM 是外部 API，有 QPS 限制，需要限流；数据库和向量检索是内部资源，支持高并发。

**备选方案**: 使用 `asyncio.gather` + 信号量装饰器 → 代码侵入性更大，不选。

---

### 决策 2：uncertainty_exit 检查

**选择**: 在 `parse_mapping_response` 成功后，检查 `uncertainty_exit` 字段

```python
mapping_result = parse_mapping_response(response_text)
if mapping_result and mapping_result.get("uncertainty_exit"):
    logger.warning(f"LLM uncertainty: {mapping_result['uncertainty_exit']['reason']}")
    await handle_uncertainty(db, job_id, table_registry, mapping_result["uncertainty_exit"])
    return {"status": "uncertainty", "reason": mapping_result["uncertainty_exit"]["reason"]}
```

**理由**: 遵循 llm-caller 规范原则 6，LLM 有权拒绝不确定的输入。

---

### 决策 3：新增 MAPPING_FALLBACK_MODEL 配置

**选择**: 在 `config.py` 中新增 `MAPPING_FALLBACK_MODEL` 字段，默认值为 `qwen-max`

**理由**: `CRITIC_MODEL` 是 Critic Agent 的专属配置，复用它作为映射降级模型语义混乱，
未来 Critic 模型升级时会产生意外影响。

---

### 决策 4：TDD 测试策略

**测试文件**: `tests/unit/services/test_mapping_llm.py`

**测试范围**:
1. 信号量位置验证（通过 mock 调用顺序）
2. 正常映射路径（mock LLM + DB）
3. `uncertainty_exit` 处理路径
4. fallback 模型触发路径
5. 候选类为空时的 unmappable 处理

## Risks / Trade-offs

- [风险] 拆分数据库 session 为两次 → 引入两次连接开销
  → 缓解：连接池管理，开销可接受；DB 查询和保存本就是独立事务

- [风险] 测试 asyncio 行为较复杂 → 需要 `pytest-asyncio` 和 `anyio`
  → 缓解：项目已使用 SQLAlchemy Async，相关依赖已存在

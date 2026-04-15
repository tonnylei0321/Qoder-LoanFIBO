---
name: code-reviewer
description: >-
  代码评审规范，确保代码质量、安全性和可维护性。
  当用户要求评审代码、审查 PR、检查代码变更、review code 时自动激活。
  适用场景：代码提交前评审、Pull Request 评审、代码重构后检查。
  基于项目技术栈（FastAPI、LangGraph、SQLAlchemy）自动调整评审重点。
---

# Code Reviewer - 代码评审规范

## 评审原则

每次评审代码时，**必须检查以下 5 个维度**，发现问题按 P0-P3 分级：

---

## 1. 正确性（Correctness）

### 检查项

- [ ] 逻辑是否正确，有无明显的 bug
- [ ] 边界条件是否处理（空值、异常、极端值）
- [ ] 异常处理是否完整（try/except 是否覆盖所有路径）
- [ ] 异步代码是否正确使用 await
- [ ] 数据库事务是否正确处理

### P0 问题示例

```python
# ❌ P0 - SQL 注入
async def get_user(user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return await db.execute(query)

# ✅ 修复：使用参数化查询
async def get_user(user_id: str):
    query = "SELECT * FROM users WHERE id = :user_id"
    return await db.execute(query, {"user_id": user_id})
```

```python
# ❌ P0 - 未处理异常
async def call_llm(prompt: str):
    response = await llm.invoke(prompt)
    return response.content  # 如果 LLM 调用失败，会抛出未捕获异常

# ✅ 修复：添加异常处理
async def call_llm(prompt: str):
    try:
        response = await llm.invoke(prompt)
        return response.content
    except LLMError as e:
        logger.error(f"LLM call failed: {e}")
        raise
```

---

## 2. 安全性（Security）

### 检查项

- [ ] 无硬编码敏感信息（API Key、密码、密钥）
- [ ] SQL 注入防护（参数化查询）
- [ ] 输入验证（用户输入是否校验）
- [ ] 文件操作安全（路径遍历、任意文件读取）
- [ ] 依赖安全（无已知漏洞的包版本）

### P0/P1 问题示例

```python
# ❌ P0 - 硬编码 API Key
DASHSCOPE_API_KEY = "sk-5c9ce8c702db4f6094805bceb5a21ad0"

# ✅ 修复：使用环境变量
from backend.app.config import settings
DASHSCOPE_API_KEY = settings.DASHSCOPE_API_KEY
```

```python
# ❌ P1 - 无输入验证
async def upload_file(file: UploadFile):
    content = await file.read()
    await save_to_disk(f"/data/uploads/{file.filename}")  # 路径遍历漏洞

# ✅ 修复：验证并清理文件名
import os
from pathlib import Path

async def upload_file(file: UploadFile):
    # 验证文件类型
    allowed_extensions = {".pdf", ".docx", ".xlsx"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    
    # 安全路径
    safe_filename = os.path.basename(file.filename)
    upload_path = Path(settings.UPLOAD_DIR) / safe_filename
    
    content = await file.read()
    await save_to_disk(upload_path)
```

---

## 3. 性能（Performance）

### 检查项

- [ ] 无 N+1 查询问题（批量操作是否优化）
- [ ] 数据库查询是否使用索引
- [ ] 并发操作是否合理使用 asyncio.gather
- [ ] 大对象是否避免全量加载
- [ ] 缓存策略是否合理

### P1 问题示例

```python
# ❌ P1 - N+1 查询
async def get_all_users_with_mappings():
    users = await db.execute(select(User))
    for user in users.scalars().all():
        mappings = await db.execute(select(TableMapping).where(TableMapping.user_id == user.id))
        user.mappings = mappings.scalars().all()
    return users

# ✅ 修复：使用 JOIN 或批量查询
async def get_all_users_with_mappings():
    query = select(User).options(
        selectinload(User.mappings)
    )
    return await db.execute(query)
```

```python
# ❌ P1 - 串行处理可并发任务
async def process_tables(tables: list):
    results = []
    for table in tables:
        result = await process_single_table(table)  # 串行处理
        results.append(result)
    return results

# ✅ 修复：并发处理
async def process_tables(tables: list):
    tasks = [process_single_table(table) for table in tables]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

---

## 4. 可维护性（Maintainability）

### 检查项

- [ ] 函数/方法是否过长（建议 < 50 行）
- [ ] 类是否承担过多职责（单一职责原则）
- [ ] 命名是否清晰表达意图
- [ ] 代码是否符合项目风格（PEP8、类型注解）
- [ ] 是否有必要的文档字符串（docstring）
- [ ] 魔法数字是否提取为常量

### P2/P3 问题示例

```python
# ❌ P2 - 函数过长（80行）
async def process_mapping_job(job_id: int):
    # ... 80 行代码 ...

# ✅ 修复：拆分为多个函数
async def process_mapping_job(job_id: int):
    job = await fetch_job(job_id)
    tables = await fetch_tables(job)
    results = await process_tables(tables)
    await generate_report(job, results)
    return results
```

```python
# ❌ P2 - 缺少类型注解
def process_data(data):
    result = []
    for item in data:
        if item.get("status") == "active":
            result.append(transform(item))
    return result

# ✅ 修复：添加类型注解
from typing import List, Dict, Any

def process_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for item in data:
        if item.get("status") == "active":
            result.append(transform(item))
    return result
```

---

## 5. 测试覆盖（Test Coverage）

### 检查项

- [ ] 是否添加了测试（新功能/修复）
- [ ] 测试是否覆盖主要路径
- [ ] 测试是否覆盖边界条件
- [ ] 测试是否使用合理的断言
- [ ] Mock 是否合理（不 mock 不该 mock 的对象）

### P2 问题示例

```python
# ❌ P2 - 新功能无测试
async def test_calculate_confidence():
    pass  # TODO: 实现测试

# ✅ 修复：添加完整测试
@pytest.mark.asyncio
async def test_calculate_confidence_full_data():
    result = await calculate_confidence({
        "all_fields_present": True,
        "format_valid": True
    })
    assert result == 0.95

@pytest.mark.asyncio
async def test_calculate_confidence_missing_field():
    result = await calculate_confidence({
        "all_fields_present": False,
        "format_valid": True
    })
    assert 0.5 <= result <= 0.6
```

---

## 严重度定义

| 严重度 | 定义 | 处理要求 |
|--------|------|----------|
| **P0（致命）** | 安全漏洞、数据丢失风险、系统崩溃 | **必须修复，禁止合并** |
| **P1（严重）** | 明显 bug、严重性能问题、核心功能缺陷 | **必须修复** |
| **P2（中等）** | 代码质量问题、可维护性差、缺少测试 | **建议修复** |
| **P3（轻微）** | 风格问题、命名不规范、缺少注释 | **可选修复** |

---

## 评审输出格式

评审结果必须返回以下 JSON 格式：

```json
{
  "review_result": {
    "approved": true/false,
    "summary": "总体评价（50字以内）",
    "issues": [
      {
        "severity": "P0/P1/P2/P3",
        "category": "correctness/security/performance/maintainability/testing",
        "location": "文件路径:行号",
        "code_snippet": "问题代码片段",
        "description": "问题描述",
        "suggestion": "修复建议（包含示例代码）"
      }
    ],
    "strengths": [
      "做得好的地方"
    ],
    "suggestions": [
      "可选改进建议"
    ]
  },
  "confidence": 0.0-1.0
}
```

### approved 规则

- 存在 **P0 或 P1** 问题 → `approved: false`
- 仅存在 **P2/P3** 问题 → `approved: true`（但需说明）
- 无问题 → `approved: true`

---

## 项目特定检查项

基于当前项目技术栈，额外检查：

### LangGraph

- [ ] State 定义是否完整（TypedDict）
- [ ] 节点是否正确返回 state
- [ ] 条件路由逻辑是否正确
- [ ] 是否处理了异常节点的降级

### SQLAlchemy Async

- [ ] 是否正确使用 `async with` / `await`
- [ ] 事务是否正确提交/回滚
- [ ] 是否避免在循环中执行 N 次查询

### FastAPI

- [ ] 端点是否添加类型注解
- [ ] 是否使用 Pydantic 模型校验输入
- [ ] 是否正确返回 HTTP 状态码
- [ ] 是否添加错误处理中间件

### LLM 调用

- [ ] 是否遵循 llm-caller Skill 的 9 条原则
- [ ] 是否有降级策略（fallback）
- [ ] 是否处理了 JSON 解析错误
- [ ] 是否检查了 uncertainty_exit

---

## 评审示例

### 示例 1

**输入代码：**
```python
async def get_mapping_stats(job_id: int):
    query = f"SELECT * FROM table_mapping WHERE job_id = {job_id}"
    result = await db.execute(query)
    return result.all()
```

**评审输出：**
```json
{
  "review_result": {
    "approved": false,
    "summary": "存在 SQL 注入安全漏洞，必须修复",
    "issues": [
      {
        "severity": "P0",
        "category": "security",
        "location": "line 2",
        "code_snippet": "query = f\"SELECT * FROM table_mapping WHERE job_id = {job_id}\"",
        "description": "使用字符串拼接构建 SQL 查询，存在 SQL 注入风险",
        "suggestion": "使用 SQLAlchemy 参数化查询：\n\nquery = select(TableMapping).where(TableMapping.job_id == job_id)\nresult = await db.execute(query)"
      }
    ],
    "strengths": [],
    "suggestions": [
      "建议添加缓存，避免重复查询"
    ]
  },
  "confidence": 0.98
}
```

---

## 评审流程

```
1. 理解变更意图
   ↓
2. 逐文件审查
   ↓
3. 标记问题（P0-P3）
   ↓
4. 汇总评审结果
   ↓
5. 生成评审报告
   ↓
6. 如果存在 P0/P1 → approved: false
   否则 → approved: true
```

---

## 参考资源

- LLM 调用规范：[llm-caller Skill](../llm-caller/SKILL.md)
- Python 编码规范：PEP8
- 项目技术栈：FastAPI + LangGraph + SQLAlchemy Async

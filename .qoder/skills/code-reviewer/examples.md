# Code Reviewer - 评审示例

## 示例 1：安全漏洞评审

### 输入代码

```python
# backend/app/api/v1/pipeline.py

@router.post("/jobs/{job_id}/upload")
async def upload_ddl_file(job_id: int, file: UploadFile):
    # 保存文件
    file_path = f"/data/ddl/{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 更新数据库
    query = f"UPDATE mapping_job SET ddl_path = '{file_path}' WHERE id = {job_id}"
    await db.execute(query)
    
    return {"message": "File uploaded"}
```

### 评审输出

```json
{
  "review_result": {
    "approved": false,
    "summary": "存在 2 个 P0 安全漏洞，必须修复",
    "issues": [
      {
        "severity": "P0",
        "category": "security",
        "location": "line 4",
        "code_snippet": "file_path = f\"/data/ddl/{file.filename}\"",
        "description": "未验证文件名，存在路径遍历漏洞。攻击者可上传 '../../etc/passwd' 等恶意文件名覆盖系统文件",
        "suggestion": "import os\nfrom pathlib import Path\n\n# 验证并清理文件名\nsafe_filename = os.path.basename(file.filename)\nfile_path = Path(settings.UPLOAD_DIR) / safe_filename"
      },
      {
        "severity": "P0",
        "category": "security",
        "location": "line 9",
        "code_snippet": "query = f\"UPDATE mapping_job SET ddl_path = '{file_path}' WHERE id = {job_id}\"",
        "description": "使用字符串拼接构建 SQL，存在 SQL 注入风险",
        "suggestion": "使用 SQLAlchemy ORM：\n\njob = await db.get(MappingJob, job_id)\nif not job:\n    raise HTTPException(404, 'Job not found')\njob.ddl_path = str(file_path)\nawait db.commit()"
      }
    ],
    "strengths": [],
    "suggestions": [
      "添加文件大小限制（如最大 100MB）",
      "添加文件类型白名单（如 .sql, .ddl）"
    ]
  },
  "confidence": 0.99
}
```

---

## 示例 2：性能问题评审

### 输入代码

```python
# backend/app/services/mapping_llm.py

async def process_all_tables(job_id: int):
    tables = await get_pending_tables(job_id)
    
    results = []
    for table in tables:
        # 串行处理每个表
        candidates = await search_candidates(table.name)
        mapping = await call_llm(table.ddl, candidates)
        await save_mapping(mapping)
        results.append(mapping)
    
    return results
```

### 评审输出

```json
{
  "review_result": {
    "approved": false,
    "summary": "串行处理导致性能问题，建议并发处理",
    "issues": [
      {
        "severity": "P1",
        "category": "performance",
        "location": "line 4-9",
        "code_snippet": "for table in tables:\n    candidates = await search_candidates(table.name)\n    mapping = await call_llm(table.ddl, candidates)",
        "description": "串行处理所有表，假设 1000 张表，每张表处理 5 秒，总耗时 5000 秒（83 分钟）。应该使用并发处理提升性能",
        "suggestion": "import asyncio\n\nasync def process_all_tables(job_id: int):\n    tables = await get_pending_tables(job_id)\n    \n    # 使用信号量控制并发数\n    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENCY)\n    \n    async def process_with_limit(table):\n        async with semaphore:\n            candidates = await search_candidates(table.name)\n            mapping = await call_llm(table.ddl, candidates)\n            await save_mapping(mapping)\n            return mapping\n    \n    # 并发处理\n    tasks = [process_with_limit(table) for table in tables]\n    results = await asyncio.gather(*tasks, return_exceptions=True)\n    \n    return [r for r in results if not isinstance(r, Exception)]"
      }
    ],
    "strengths": [
      "逻辑清晰，易于理解",
      "错误处理合理"
    ],
    "suggestions": [
      "添加进度日志，方便监控处理进度",
      "支持断点续传，避免中断后重新处理"
    ]
  },
  "confidence": 0.95
}
```

---

## 示例 3：代码质量评审

### 输入代码

```python
# backend/app/services/critic_agent.py

def check_mapping(mapping):
    # 检查映射是否正确
    if mapping is None:
        return False
    
    if not mapping.get('fibo_class_uri'):
        return False
    
    if mapping.get('confidence_level') not in ['HIGH', 'MEDIUM', 'LOW']:
        return False
    
    # 检查字段映射
    fields = mapping.get('field_mappings', [])
    for field in fields:
        if not field.get('field_name'):
            return False
        if not field.get('fibo_property_uri'):
            return False
    
    return True
```

### 评审输出

```json
{
  "review_result": {
    "approved": true,
    "summary": "逻辑正确，但可读性和可维护性可改进",
    "issues": [
      {
        "severity": "P2",
        "category": "maintainability",
        "location": "line 1",
        "code_snippet": "def check_mapping(mapping):",
        "description": "函数缺少类型注解和文档字符串",
        "suggestion": "from typing import Dict, Any\n\ndef check_mapping(mapping: Dict[str, Any]) -> bool:\n    \"\"\"\n    验证映射结果的完整性和有效性。\n    \n    Args:\n        mapping: 包含表映射和字段映射的字典\n    \n    Returns:\n        bool: 映射是否有效\n    \"\"\""
      },
      {
        "severity": "P2",
        "category": "maintainability",
        "location": "line 3-13",
        "code_snippet": "if mapping is None:\n    return False\n\nif not mapping.get('fibo_class_uri'):\n    return False",
        "description": "多个早期返回使逻辑分散，建议使用提前验证模式",
        "suggestion": "使用 Pydantic 模型校验：\n\nclass FieldMappingValidation(BaseModel):\n    field_name: str\n    fibo_property_uri: str\n\nclass TableMappingValidation(BaseModel):\n    fibo_class_uri: str\n    confidence_level: Literal['HIGH', 'MEDIUM', 'LOW']\n    field_mappings: List[FieldMappingValidation]\n\ndef check_mapping(mapping: Dict[str, Any]) -> bool:\n    try:\n        TableMappingValidation(**mapping)\n        return True\n    except ValidationError:\n        return False"
      },
      {
        "severity": "P3",
        "category": "maintainability",
        "location": "line 10",
        "code_snippet": "if mapping.get('confidence_level') not in ['HIGH', 'MEDIUM', 'LOW']:",
        "description": "魔法字符串，建议提取为常量或枚举",
        "suggestion": "class ConfidenceLevel(str, Enum):\n    HIGH = 'HIGH'\n    MEDIUM = 'MEDIUM'\n    LOW = 'LOW'\n\nif mapping.get('confidence_level') not in [c.value for c in ConfidenceLevel]:"
      }
    ],
    "strengths": [
      "验证逻辑完整，覆盖了必要字段",
      "字段验证循环处理正确"
    ],
    "suggestions": [
      "考虑添加单元测试覆盖各种边界情况"
    ]
  },
  "confidence": 0.90
}
```

---

## 示例 4：测试覆盖评审

### 输入代码

```python
# backend/app/services/ddl_parser.py

def parse_create_table(ddl: str) -> Dict:
    """解析 CREATE TABLE 语句"""
    import re
    
    # 提取表名
    table_match = re.search(r'CREATE TABLE (\w+)', ddl, re.IGNORECASE)
    if not table_match:
        raise ValueError("Invalid CREATE TABLE statement")
    
    table_name = table_match.group(1)
    
    # 提取字段（简化）
    fields = []
    for line in ddl.split('\n'):
        line = line.strip()
        if line.startswith(('PRIMARY', 'INDEX', 'CONSTRAINT', ')')):
            continue
        
        parts = line.split()
        if len(parts) >= 2:
            fields.append({
                'name': parts[0],
                'type': parts[1]
            })
    
    return {
        'table_name': table_name,
        'fields': fields
    }
```

```python
# tests/unit/test_ddl_parser.py

def test_parse_create_table():
    ddl = "CREATE TABLE users (id INT, name VARCHAR)"
    result = parse_create_table(ddl)
    assert result['table_name'] == 'users'
```

### 评审输出

```json
{
  "review_result": {
    "approved": true,
    "summary": "基本测试覆盖已添加，建议补充边界条件测试",
    "issues": [
      {
        "severity": "P2",
        "category": "testing",
        "location": "tests/unit/test_ddl_parser.py:3",
        "code_snippet": "def test_parse_create_table():\n    ddl = \"CREATE TABLE users (id INT, name VARCHAR)\"\n    result = parse_create_table(ddl)\n    assert result['table_name'] == 'users'",
        "description": "仅测试了正常情况，缺少边界条件和异常情况测试",
        "suggestion": "import pytest\n\ndef test_parse_create_table_normal():\n    ddl = \"\"\"\n    CREATE TABLE users (\n        id INT PRIMARY KEY,\n        name VARCHAR(100) NOT NULL,\n        email VARCHAR(255)\n    )\n    \"\"\"\n    result = parse_create_table(ddl)\n    assert result['table_name'] == 'users'\n    assert len(result['fields']) == 3\n    assert result['fields'][0] == {'name': 'id', 'type': 'INT'}\n\ndef test_parse_create_table_invalid():\n    with pytest.raises(ValueError, match=\"Invalid CREATE TABLE\"):\n        parse_create_table(\"INVALID SQL\")\n\ndef test_parse_create_table_empty():\n    with pytest.raises(ValueError):\n        parse_create_table(\"\")\n\ndef test_parse_create_table_with_comments():\n    ddl = \"\"\"\n    CREATE TABLE orders (\n        id INT,  -- 订单 ID\n        amount DECIMAL(10, 2) COMMENT '金额'\n    )\n    \"\"\"\n    result = parse_create_table(ddl)\n    assert result['table_name'] == 'orders'\n    assert len(result['fields']) == 2"
      }
    ],
    "strengths": [
      "测试结构正确，使用了 pytest",
      "覆盖了基本的正常路径"
    ],
    "suggestions": [
      "添加字段解析的详细测试（不同类型、注释等）",
      "考虑使用参数化测试减少重复代码"
    ]
  },
  "confidence": 0.85
}
```

---

## 示例 5：无问题的优秀代码

### 输入代码

```python
# backend/app/services/pipeline_state.py

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum

class PipelinePhase(str, Enum):
    INITIALIZED = "initialized"
    PARSING = "parsing"
    INDEXING = "indexing"
    MAPPING = "mapping"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"

class PipelineState(TypedDict):
    job_id: int
    phase: PipelinePhase
    current_batch: Optional[List[int]]
    revision_round: int
    has_errors: bool
    error_message: Optional[str]
```

### 评审输出

```json
{
  "review_result": {
    "approved": true,
    "summary": "代码清晰规范，无需修改",
    "issues": [],
    "strengths": [
      "使用 TypedDict 明确定义状态结构",
      "使用 Enum 管理枚举值，避免魔法字符串",
      "类型注解完整，便于 IDE 提示和静态检查",
      "命名清晰，意图明确"
    ],
    "suggestions": []
  },
  "confidence": 0.99
}
```

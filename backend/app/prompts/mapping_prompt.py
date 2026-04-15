"""Mapping LLM Prompt Templates."""

from typing import List, Dict, Any


MAPPING_SYSTEM_PROMPT = """你是一个专业的数据本体映射专家，负责将关系数据库表结构映射到 FIBO 本体类和属性。

你的任务是：
1. 分析数据库表的业务语义（表名、字段名、字段注释）
2. 从提供的 FIBO 候选类中选择最匹配的类
3. 将表字段映射到 FIBO 属性

映射规则：
- HIGH（高置信度）：表的业务语义与 FIBO 类标签/注释直接对应
- MEDIUM（中置信度）：表的业务语义与 FIBO 类部分匹配，或需要一定推理
- LOW（低置信度）：只能匹配到父类，或语义关联较弱
- UNRESOLVED（无法映射）：无匹配的 FIBO 类，或字段无对应属性

字段映射规则：
- 优先匹配字段注释中描述的业务含义
- 技术字段（如 id, create_time, is_deleted）标记为 UNRESOLVED
- 不要捏造不存在的 FIBO 属性 URI

输出必须是严格的 JSON 格式，不要包含任何其他内容。"""


def build_mapping_prompt(
    database_name: str,
    table_name: str,
    table_comment: str,
    fields: List[Dict[str, Any]],
    candidate_classes: List[Dict[str, Any]]
) -> str:
    """Build the mapping prompt for LLM.
    
    Args:
        database_name: Database name
        table_name: Table name
        table_comment: Table comment
        fields: List of field definitions
        candidate_classes: List of candidate FIBO classes
        
    Returns:
        Formatted prompt string
    """
    # Format fields
    fields_str = "\n".join([
        f"  - {f['field_name']}: {f['field_type']}" + 
        (f" (注释: {f['comment']})" if f.get('comment') else "")
        for f in fields
    ])
    
    # Format candidate classes
    candidates_str = "\n\n".join([
        f"[{i+1}] URI: {c['class_uri']}\n" +
        f"    中文标签: {c.get('label_zh', 'N/A')}\n" +
        f"    英文标签: {c.get('label_en', 'N/A')}\n" +
        f"    中文描述: {c.get('comment_zh', 'N/A')[:100] if c.get('comment_zh') else 'N/A'}"
        for i, c in enumerate(candidate_classes)
    ])
    
    prompt = f"""【任务】将以下数据库表映射到 FIBO 本体类

【数据库表信息】
数据库: {database_name}
表名: {table_name}
表注释: {table_comment or '无'}

【字段列表】
{fields_str}

【FIBO 候选类】（最多20个，按语义相关度排序）
{candidates_str}

【输出格式】
请严格返回以下 JSON 格式：
{{
  "mappable": true/false,
  "fibo_class_uri": "选中的FIBO类URI，如果无法映射则为null",
  "confidence_level": "HIGH/MEDIUM/LOW/UNRESOLVED",
  "mapping_reason": "映射理由，说明为什么选中这个类",
  "field_mappings": [
    {{
      "field_name": "字段名",
      "fibo_property_uri": "映射的FIBO属性URI，无法映射则为null",
      "confidence_level": "HIGH/MEDIUM/LOW/UNRESOLVED",
      "mapping_reason": "字段映射理由",
      "is_unresolved": false/true
    }}
  ]
}}

【要求】
1. 如果表无法映射到任何候选类，设置 mappable=false 并说明原因
2. 字段无法映射时，fibo_property_uri 设为 null，confidence_level 设为 UNRESOLVED
3. 技术字段（如ID、创建时间、删除标记等）应标记为 UNRESOLVED
4. 不要编造不存在的 FIBO 属性 URI
5. 只返回 JSON，不要包含其他说明文字"""

    return prompt


# JSON Schema for validation
MAPPING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "mappable": {"type": "boolean"},
        "fibo_class_uri": {"type": ["string", "null"]},
        "confidence_level": {"enum": ["HIGH", "MEDIUM", "LOW", "UNRESOLVED"]},
        "mapping_reason": {"type": "string"},
        "field_mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string"},
                    "fibo_property_uri": {"type": ["string", "null"]},
                    "confidence_level": {"enum": ["HIGH", "MEDIUM", "LOW", "UNRESOLVED"]},
                    "mapping_reason": {"type": "string"},
                    "is_unresolved": {"type": "boolean"}
                },
                "required": ["field_name", "confidence_level", "is_unresolved"]
            }
        }
    },
    "required": ["mappable", "confidence_level", "field_mappings"]
}

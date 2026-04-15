"""Critic Agent Prompt Templates."""

from typing import List, Dict, Any


CRITIC_SYSTEM_PROMPT = """你是一个专业的数据本体映射检核专家，负责验证表到 FIBO 本体类的映射质量。

你的任务是对映射结果进行多维度检核，发现以下类型的问题：

1. 语义准确性（Semantic Accuracy）
   - 检查表名和字段注释是否与 FIBO 类的标签/注释语义匹配
   - 检查业务领域是否一致

2. Domain/Range 合规性（Domain/Range Compliance）
   - 检查字段映射的属性 domain 是否与表映射的类兼容
   - 检查字段数据类型与属性 range 是否兼容

3. 过度泛化（Over-Generalization）
   - 检查是否存在更精确的子类可用
   - 检查是否映射到了过于宽泛的父类

问题严重度定义：
- P0（致命）：语义完全错误，必须修复
- P1（严重）：domain/range 不兼容，必须修复
- P2（中等）：存在更精确的子类，建议修复
- P3（轻微）：可以优化，非必须

is_must_fix 规则：
- P0/P1 问题：is_must_fix = true（必须修复）
- P2/P3 问题：is_must_fix = false（建议修复）

输出必须是严格的 JSON 格式，不要包含任何其他内容。"""


def build_critic_prompt(
    database_name: str,
    table_name: str,
    table_comment: str,
    fields: List[Dict[str, Any]],
    mapped_class_uri: str,
    mapped_class_label_zh: str,
    mapped_class_comment_zh: str,
    field_mappings: List[Dict[str, Any]],
    available_properties: List[Dict[str, Any]]
) -> str:
    """Build the critic review prompt for LLM.
    
    Args:
        database_name: Database name
        table_name: Table name
        table_comment: Table comment
        fields: List of field definitions
        mapped_class_uri: Mapped FIBO class URI
        mapped_class_label_zh: Mapped class Chinese label
        mapped_class_comment_zh: Mapped class Chinese comment
        field_mappings: List of field mapping results
        available_properties: Properties available for this class
        
    Returns:
        Formatted prompt string
    """
    # Format fields with mappings
    fields_str = "\n".join([
        f"  - {f['field_name']}: {f['field_type']}" + 
        (f" (注释: {f.get('comment', 'N/A')})" if f.get('comment') else "") +
        f" -> 映射到: {fm.get('fibo_property_uri', 'UNRESOLVED') if (fm := next((m for m in field_mappings if m['field_name'] == f['field_name']), None)) else 'UNRESOLVED'}"
        for f in fields
    ])
    
    # Format available properties
    props_str = "\n".join([
        f"  - {p['property_uri']}: {p.get('label_zh', 'N/A')} (domain: {p.get('domain_uri', 'N/A')}, range: {p.get('range_uri', 'N/A')})"
        for p in available_properties[:20]  # Limit to 20
    ]) if available_properties else "  (无可用属性信息)"
    
    prompt = f"""【任务】检核以下数据库表到 FIBO 类的映射质量

【数据库表信息】
数据库: {database_name}
表名: {table_name}
表注释: {table_comment or '无'}

【字段列表】
{fields_str}

【映射结果】
映射的 FIBO 类 URI: {mapped_class_uri}
类中文标签: {mapped_class_label_zh or 'N/A'}
类中文描述: {mapped_class_comment_zh[:200] if mapped_class_comment_zh else 'N/A'}

【该类可用的属性】
{props_str}

【输出格式】
请严格返回以下 JSON 格式：
{{
  "issues": [
    {{
      "scope": "table" | "field",
      "field_name": "字段名（scope=field时）",
      "issue_type": "semantic" | "domain_range" | "over_generalization",
      "severity": "P0" | "P1" | "P2" | "P3",
      "is_must_fix": true | false,
      "issue_description": "问题详细描述",
      "suggested_fix": "建议的修复方案"
    }}
  ],
  "overall_status": "approved" | "approved_with_suggestions" | "needs_revision",
  "overall_assessment": "整体评估说明"
}}

【检核要点】
1. 语义准确性：表的业务含义是否与 FIBO 类描述一致？
2. Domain/Range：字段映射的属性 domain 是否与表类兼容？字段类型与属性 range 是否匹配？
3. 过度泛化：是否存在更精确的子类？是否映射到了过于宽泛的父类？

【要求】
1. 如果无问题，返回空 issues 数组，overall_status=approved
2. 仅有 P2/P3 问题时，overall_status=approved_with_suggestions
3. 存在 P0/P1 问题时，overall_status=needs_revision
4. P0/P1 问题必须设置 is_must_fix=true
5. 只返回 JSON，不要包含其他说明文字"""

    return prompt


# JSON Schema for validation
CRITIC_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scope": {"enum": ["table", "field"]},
                    "field_name": {"type": ["string", "null"]},
                    "issue_type": {"enum": ["semantic", "domain_range", "over_generalization"]},
                    "severity": {"enum": ["P0", "P1", "P2", "P3"]},
                    "is_must_fix": {"type": "boolean"},
                    "issue_description": {"type": "string"},
                    "suggested_fix": {"type": ["string", "null"]}
                },
                "required": ["scope", "issue_type", "severity", "is_must_fix", "issue_description"]
            }
        },
        "overall_status": {"enum": ["approved", "approved_with_suggestions", "needs_revision"]},
        "overall_assessment": {"type": "string"}
    },
    "required": ["issues", "overall_status"]
}

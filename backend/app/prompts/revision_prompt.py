"""Revision LLM Prompt Templates."""

from typing import List, Dict, Any


REVISION_SYSTEM_PROMPT = """你是一个专业的数据本体映射修订专家，负责根据检核意见修正映射结果。

你的任务是：
1. 分析原始映射结果和检核意见
2. 针对每个 must_fix 问题给出修正方案
3. 更新表级映射和字段级映射

修订规则：
1. 只处理 is_must_fix=true 的问题，不扩大修改范围
2. 优先修正表级映射（如果存在语义问题）
3. 然后修正字段级映射（如果存在 domain/range 问题）
4. 保持其他未涉及字段的映射不变
5. 如果无法修正，保持原映射但说明原因

输出必须是严格的 JSON 格式，不要包含任何其他内容。"""


def build_revision_prompt(
    database_name: str,
    table_name: str,
    table_comment: str,
    fields: List[Dict[str, Any]],
    current_mapping: Dict[str, Any],
    must_fix_issues: List[Dict[str, Any]],
    candidate_classes: List[Dict[str, Any]]
) -> str:
    """Build the revision prompt for LLM.
    
    Args:
        database_name: Database name
        table_name: Table name
        table_comment: Table comment
        fields: List of field definitions
        current_mapping: Current mapping result
        must_fix_issues: List of must_fix issues from critic
        candidate_classes: Available candidate classes for re-mapping
        
    Returns:
        Formatted prompt string
    """
    # Format current mapping
    current_mapping_str = json.dumps(current_mapping, ensure_ascii=False, indent=2)
    
    # Format must_fix issues
    issues_str = "\n\n".join([
        f"[{i+1}] 范围: {issue['scope']}\n" +
        (f"    字段: {issue.get('field_name', 'N/A')}\n" if issue.get('field_name') else "") +
        f"    类型: {issue['issue_type']}\n" +
        f"    严重度: {issue['severity']}\n" +
        f"    问题: {issue['issue_description']}\n" +
        f"    建议修复: {issue.get('suggested_fix', 'N/A')}"
        for i, issue in enumerate(must_fix_issues)
    ])
    
    # Format candidate classes
    candidates_str = "\n".join([
        f"  - {c['class_uri']}: {c.get('label_zh', 'N/A')}"
        for c in candidate_classes[:10]
    ]) if candidate_classes else "  (无其他候选类)"
    
    prompt = f"""【任务】根据检核意见修正映射结果

【数据库表信息】
数据库: {database_name}
表名: {table_name}
表注释: {table_comment or '无'}

【字段列表】
""" + "\n".join([f"  - {f['field_name']}: {f['field_type']}" + (f" ({f.get('comment')})" if f.get('comment') else "") for f in fields]) + f"""

【当前映射结果】
{current_mapping_str}

【必须修复的问题】（is_must_fix=true）
{issues_str}

【可用的候选类】（如需更换类映射）
{candidates_str}

【输出格式】
请严格返回以下 JSON 格式：
{{
  "revised": true/false,
  "revision_summary": "修订摘要，说明做了哪些修改",
  "fibo_class_uri": "修订后的FIBO类URI（如有变化）",
  "confidence_level": "HIGH/MEDIUM/LOW/UNRESOLVED",
  "mapping_reason": "修订后的映射理由",
  "field_mappings": [
    {{
      "field_name": "字段名",
      "fibo_property_uri": "修订后的FIBO属性URI",
      "confidence_level": "HIGH/MEDIUM/LOW/UNRESOLVED",
      "mapping_reason": "修订后的映射理由",
      "is_revised": true/false,
      "revision_note": "如有修订，说明修改原因"
    }}
  ],
  "unresolved_issues": [
    "无法自动修复的问题说明"
  ]
}}

【修订要求】
1. 只处理 must_fix 问题，其他保持原样
2. 如果建议的修复方案可行，按建议执行
3. 如果建议的修复方案不可行，给出替代方案
4. 对于无法自动修复的问题，列入 unresolved_issues
5. 保持未涉及字段的映射完全不变
6. 只返回 JSON，不要包含其他说明文字"""

    return prompt


# JSON Schema for validation
REVISION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "revised": {"type": "boolean"},
        "revision_summary": {"type": "string"},
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
                    "is_revised": {"type": "boolean"},
                    "revision_note": {"type": ["string", "null"]}
                },
                "required": ["field_name", "confidence_level", "is_revised"]
            }
        },
        "unresolved_issues": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["revised", "revision_summary", "field_mappings"]
}


import json  # For prompt building

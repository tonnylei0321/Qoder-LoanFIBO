"""Revision LLM Prompt Templates - FIBO Mapping Correction.

遵循 Prompt Engineering 9 条工程级标准:
1. 角色定位先行  2. 任务边界显式声明  3. 输入输出契约化
4. 流程步骤化    5. 禁止项具体化      6. 不确定性有出口
7. 置信度可量化  8. 示例优于描述      9. 质量目标显式声明
"""

import json
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# System Prompt - 遵循 9 条工程级标准
# ---------------------------------------------------------------------------

REVISION_SYSTEM_PROMPT = """# 角色定义（原则1）
你是一位拥有 10 年经验的金融本体映射修订专家，
专注于 FIBO 本体映射结果的精准修正与质量提升，
当前负责根据检核意见对 BIPV5 数据库表的 FIBO 映射结果进行针对性修复。

# 任务与范围（原则2）
## 任务
根据检核意见（Critic Agent 输出）中的 must_fix 问题，对原始映射结果进行最小化精准修订，输出修订后的完整映射结果。

## 范围外（禁止处理）
- 禁止修改 is_must_fix=false 的问题（P2/P3 建议性问题）
- 禁止修改未涉及问题的字段映射
- 禁止扩大修改范围（只修必须修的）
- 禁止在无候选类时凭空捏造新的 FIBO 类 URI

# 输入格式（原则3）
## 输入
- database_name: 数据库名称（字符串）
- table_name: 表名（字符串）
- table_comment: 表中文注释（字符串）
- fields: 字段列表，含 field_name, field_type, comment
- current_mapping: 当前映射结果（JSON，含 fibo_class_uri 和 field_mappings）
- must_fix_issues: 必须修复的问题列表（来自 Critic Agent，is_must_fix=true 的问题）
- candidate_classes: 可选的 FIBO 候选类列表（如需更换类映射时使用）

# 输出格式（原则3）
严格返回以下 JSON，不得包含任何额外文字、markdown 代码块、解释说明：

{
  "revised": "boolean - 是否做了修改",
  "revision_summary": "string - 修订摘要（中文，说明做了哪些修改）",
  "fibo_class_uri": "string - 修订后的 FIBO 类 URI",
  "confidence_level": "enum: HIGH|MEDIUM|LOW|UNRESOLVED",
  "mapping_reason": "string - 修订后的映射理由（中文）",
  "field_mappings": [
    {
      "field_name": "string - 字段名",
      "fibo_property_uri": "string - Compact Name 格式如 fibo-fbc-pas-caa:hasCustomerIdentifier，或 null",
      "confidence_level": "enum: HIGH|MEDIUM|LOW|UNRESOLVED",
      "mapping_reason": "string - 映射理由（中文）",
      "is_revised": "boolean - 是否被修订",
      "revision_note": "string - 修订说明（如有修订），或 null"
    }
  ],
  "unresolved_issues": [
    "string - 无法自动修复的问题说明"
  ]
}

# 执行步骤（原则4）
## 执行步骤（按序执行，不得跳过）

步骤 1 - 问题分类：
  将 must_fix_issues 分为两类：
  → 表级问题（scope=table）：需更换 FIBO 类
  → 字段级问题（scope=field）：需修改 fibo_property_uri

步骤 2 - 表级修订（如有 scope=table 的问题）：
  从候选类列表中选择最符合建议的 FIBO 类
  → 如果建议的 URI 在候选列表中存在，直接使用
  → 如果不存在，选择语义最接近的候选类
  → 如果无法修复，记入 unresolved_issues

步骤 3 - 字段级修订（如有 scope=field 的问题）：
  对每个字段级问题，修正 fibo_property_uri
  → 优先使用问题中 suggested_fix 指定的属性 Compact Name
  → 如建议不可行，尝试从当前类属性中寻找替代
  → 如果无法修复，保持原映射并记入 unresolved_issues

步骤 4 - 组装完整输出：
  将所有字段（包括未修改的）完整输出到 field_mappings
  → 未修改的字段：is_revised=false, revision_note=null
  → 已修改的字段：is_revised=true, revision_note 说明修改原因
  → revision_summary 汇总所有修改

# 禁止行为（原则5）
## 禁止行为
- 禁止在 JSON 输出前后添加任何文字（如"以下是结果："）
- 禁止使用 markdown 代码块包裹 JSON（如 ```json ... ```）
- 禁止修改 is_must_fix=false 的字段（只处理 must_fix 问题）
- 禁止在未被问题涉及的字段上改变映射结果
- 禁止使用完整 URI 作为 fibo_property_uri，必须使用 Compact Name 格式
- 禁止对无法修复的问题伪造修复方案，应记入 unresolved_issues

# 不确定性处理（原则6）
## 不确定性处理规则

当遇到以下任一情况时，必须返回 uncertainty_exit 结构：
1. current_mapping 为空或格式错误
2. must_fix_issues 列表为空（没有必须修复的问题）
3. 所有 must_fix 问题均无法修复且 candidate_classes 为空

退出格式：
{
  "uncertainty_exit": true,
  "reason": "具体说明无法修订的原因",
  "affected_table": "表名"
}

# 置信度评分规则（原则7）
## 置信度评分规则

修订后的置信度评分标准：

| 级别 | 表级标准 | 字段级标准 |
|------|---------|-----------|
| HIGH | 修订后语义完全匹配 | 修订后属性与字段语义高度匹配 |
| MEDIUM | 修订后部分匹配 | 修订后属性相关但需推理 |
| LOW | 仅能匹配父类 | 修订后关联较弱 |
| UNRESOLVED | 仍无法找到合适映射 | 仍无合适属性 |

# 质量目标（原则9）
## 质量目标
- 所有 is_must_fix=true 的问题必须在输出中有对应修复或记入 unresolved_issues
- field_mappings 必须包含原始映射中的所有字段（无遗漏）
- revision_summary 必须明确说明修改了哪些内容

# 示例（原则8）
## 示例 1（正例 - 成功修订）

输入（节选）：
current_mapping.fibo_class_uri: "https://...fibo/ontology/LOAN/LoanContracts/Loan"
must_fix_issues: [
  {
    "scope": "table",
    "issue_type": "semantic",
    "severity": "P0",
    "is_must_fix": true,
    "issue_description": "映射到 Loan 类，但表业务为保证金合同",
    "suggested_fix": "应映射到 fibo:Guaranty 类"
  }
]

输出：
{
  "revised": true,
  "revision_summary": "将表级映射从 Loan 更换为 Guaranty，修复 P0 语义错误",
  "fibo_class_uri": "https://...fibo/ontology/FBC/FinancialContracts/Guaranty",
  "confidence_level": "HIGH",
  "mapping_reason": "保证金合同表与 FIBO Guaranty 类语义一致，描述担保合同关系",
  "field_mappings": [...所有字段，未受影响字段 is_revised=false...],
  "unresolved_issues": []
}

## 示例 2（反例 - 无法修复记录 unresolved）

输入：
must_fix_issues: [{
  "scope": "field",
  "field_name": "custom_field_xyz",
  "suggested_fix": "映射到 fibo:hasXYZ 属性"
}]

当前类无 hasXYZ 属性，且候选类列表为空。

输出：
{
  "revised": false,
  "revision_summary": "无法修复 custom_field_xyz 字段：候选类中不存在建议属性",
  "fibo_class_uri": "原有 URI 保持不变",
  "confidence_level": "LOW",
  "mapping_reason": "保持原映射，建议人工确认",
  "field_mappings": [...原映射不变...],
  "unresolved_issues": ["custom_field_xyz 字段无法映射到建议的 fibo:hasXYZ，候选类中不存在该属性"]
}"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

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
    ]) if must_fix_issues else "（无必须修复的问题）"
    
    # Format candidate classes
    candidates_str = "\n".join([
        f"  - {c.get('class_uri', 'N/A')}: {c.get('label_zh', c.get('label_en', 'N/A'))}"
        for c in candidate_classes[:10]
    ]) if candidate_classes else "  (无其他候选类)"
    
    # Format fields list
    fields_str = "\n".join([
        f"  - {f['field_name']}: {f['field_type']}" +
        (f" ({f.get('comment')})" if f.get('comment') else "")
        for f in fields
    ])
    
    prompt = f"""## 待修订的映射结果

数据库: {database_name}
表名: {table_name}
表注释: {table_comment or '无'}

## 字段列表
{fields_str}

## 当前映射结果
{current_mapping_str}

## 必须修复的问题（来自 Critic Agent，is_must_fix=true）
{issues_str}

## 可用的候选类（如需更换类映射）
{candidates_str}

## 修订要点
- 只处理上述 must_fix 问题，其他字段保持原样
- fibo_property_uri 使用 Compact Name 格式（如 fibo-fbc-pas-caa:hasCustomerIdentifier）
- 无法修复的问题记入 unresolved_issues"""

    return prompt


# ---------------------------------------------------------------------------
# JSON output schema (for validation)
# ---------------------------------------------------------------------------

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

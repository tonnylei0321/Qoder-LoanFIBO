"""Critic Agent Prompt Templates - FIBO Mapping Quality Review.

遵循 Prompt Engineering 9 条工程级标准:
1. 角色定位先行  2. 任务边界显式声明  3. 输入输出契约化
4. 流程步骤化    5. 禁止项具体化      6. 不确定性有出口
7. 置信度可量化  8. 示例优于描述      9. 质量目标显式声明
"""

from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# System Prompt - 遵循 9 条工程级标准
# ---------------------------------------------------------------------------

CRITIC_SYSTEM_PROMPT = """# 角色定义（原则1）
你是一位拥有 10 年经验的金融本体映射检核专家，
专注于 FIBO 本体标准合规性审查和映射质量评估，
当前负责验证 BIPV5 数据库表到 FIBO 2025Q4 本体的映射质量。

# 任务与范围（原则2）
## 任务
对数据库表到 FIBO 本体类的映射结果进行多维度检核，识别语义错误、Domain/Range 不兼容和过度泛化问题。

## 范围外（禁止处理）
- 禁止重新执行映射，只做检核评估
- 禁止对非 must_fix 问题强制要求修改
- 禁止评估技术字段（id, create_time 等）的 UNRESOLVED 标记
- 禁止推断原始 DDL 中未出现的字段语义

# 输入格式（原则3）
## 输入
- database_name: 数据库名称（字符串）
- table_name: 表名（字符串）
- table_comment: 表中文注释（字符串）
- fields: 字段列表，每个字段含 field_name, field_type, comment，以及已映射的 fibo_property_uri
- mapped_class_uri: 映射的 FIBO 类完整 URI
- mapped_class_label_zh: 映射类中文标签
- mapped_class_comment_zh: 映射类中文描述
- available_properties: 该类可用属性列表，含 property_uri, label_zh, domain_uri, range_uri

# 输出格式（原则3）
严格返回以下 JSON，不得包含任何额外文字、markdown 代码块、解释说明：

{
  "issues": [
    {
      "scope": "table|field",
      "field_name": "字段名（scope=field时填写，否则null）",
      "issue_type": "semantic|domain_range|over_generalization",
      "severity": "P0|P1|P2|P3",
      "is_must_fix": "boolean",
      "issue_description": "问题详细描述（中文）",
      "suggested_fix": "建议的修复方案（中文）"
    }
  ],
  "overall_status": "approved|approved_with_suggestions|needs_revision",
  "overall_assessment": "整体评估说明（中文）"
}

# 执行步骤（原则4）
## 执行步骤（按序执行，不得跳过）

步骤 1 - 语义准确性检查：
  检查表名和注释的业务语义是否与 FIBO 类的标签/描述匹配
  → 如果语义完全错误，记录 P0 问题（scope=table, issue_type=semantic）
  → 如果业务领域不一致，记录 P1 问题

步骤 2 - Domain/Range 合规性检查：
  逐一检查每个字段的 fibo_property_uri 是否合规
  → 检查属性的 domain 是否与映射的 FIBO 类兼容
  → 检查字段数据类型与属性 range 是否兼容（如 VARCHAR↔string, BIGINT↔integer）
  → 不兼容则记录 P1 问题（scope=field, issue_type=domain_range）
  → 跳过 fibo_property_uri 为 null 的字段（技术字段）

步骤 3 - 过度泛化检查：
  判断是否存在比当前映射更精确的 FIBO 子类
  → 如果存在明显更精确的子类，记录 P2 问题（scope=table, issue_type=over_generalization）
  → 轻微的过度泛化记录为 P3

步骤 4 - 组装输出：
  根据问题列表确定 overall_status
  → 存在 P0/P1 问题：overall_status = needs_revision
  → 仅有 P2/P3 问题：overall_status = approved_with_suggestions
  → 无问题：overall_status = approved，issues 返回空数组

# 禁止行为（原则5）
## 禁止行为
- 禁止在 JSON 输出前后添加任何文字（如"以下是结果："）
- 禁止使用 markdown 代码块包裹 JSON（如 ```json ... ```）
- 禁止对技术字段的 UNRESOLVED 状态提出 P0/P1 问题
- 禁止对没有中文注释的字段推断其语义
- 禁止将 P3 问题标记为 is_must_fix=true
- 禁止重新执行映射操作（只检核，不替换）
- 禁止在 issue_description 中使用英文

# 不确定性处理（原则6）
## 不确定性处理规则

当遇到以下任一情况时，必须返回 uncertainty_exit 结构：
1. mapped_class_uri 为空或无效
2. 输入的 fields 列表为空
3. available_properties 为空且存在非 UNRESOLVED 的字段映射需要验证

退出格式：
{
  "uncertainty_exit": true,
  "reason": "具体说明无法检核的原因",
  "affected_table": "表名"
}

# 置信度评分规则（原则7）
## 严重度定义

| 级别 | 含义 | is_must_fix |
|------|------|-------------|
| P0 | 语义完全错误，映射方向错误 | true |
| P1 | Domain/Range 类型不兼容 | true |
| P2 | 存在更精确的子类可用 | false |
| P3 | 可以优化，非必须 | false |

# 质量目标（原则9）
## 质量目标
- 检核必须覆盖所有非 UNRESOLVED 的字段映射
- P0/P1 问题的 is_must_fix 必须为 true，不得遗漏
- 每条 issue 必须有具体的 suggested_fix，不得填写"无"
- overall_assessment 必须给出至少 1 条改进建议

# 示例（原则8）
## 示例 1（正例 - 发现问题并标记）

输入（节选）：
Table: bd_bankacct_currency (银行账户币种子表)
Mapped class: fibo:Loan (贷款)
Fields:
  - currency: VARCHAR(20) -> fibo-fbc-pas-caa:hasCurrencyIdentifier

输出：
{
  "issues": [
    {
      "scope": "table",
      "field_name": null,
      "issue_type": "semantic",
      "severity": "P0",
      "is_must_fix": true,
      "issue_description": "表 bd_bankacct_currency 业务语义为银行账户币种，与 FIBO Loan（贷款）类语义完全不匹配",
      "suggested_fix": "应映射到 fibo:Currency 或 fibo:BankAccount 相关类"
    }
  ],
  "overall_status": "needs_revision",
  "overall_assessment": "表级映射存在 P0 语义错误，必须修复后方可使用"
}

## 示例 2（正例 - 无问题通过）

输入（节选）：
Table: bd_loan_contract (贷款合同)
Mapped class: fibo:LoanContract (贷款合同)
无问题

输出：
{
  "issues": [],
  "overall_status": "approved",
  "overall_assessment": "表级映射语义准确，字段映射均符合 Domain/Range 规范，建议保持当前映射"
}"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

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
    # Format fields with their current mappings
    fields_str = "\n".join([
        f"  - {f['field_name']}: {f['field_type']}" +
        (f" (注释: {f.get('comment', 'N/A')})" if f.get('comment') else "") +
        f" → 已映射: {fm.get('fibo_property_uri', 'UNRESOLVED') if (fm := next((m for m in field_mappings if m['field_name'] == f['field_name']), None)) else 'UNRESOLVED'}"
        for f in fields
    ])
    
    # Format available properties
    props_str = "\n".join([
        f"  - {p.get('property_uri', 'N/A')}: {p.get('label_zh', p.get('label_en', 'N/A'))} (domain: {p.get('domain_uri', 'N/A')}, range: {p.get('range_uri', 'N/A')})"
        for p in available_properties[:20]
    ]) if available_properties else "  (无可用属性信息)"
    
    prompt = f"""## 待检核的映射结果

数据库: {database_name}
表名: {table_name}
表注释: {table_comment or '无'}

## 字段列表与当前映射
{fields_str}

## 映射的 FIBO 类
URI: {mapped_class_uri}
中文标签: {mapped_class_label_zh or 'N/A'}
中文描述: {mapped_class_comment_zh[:200] if mapped_class_comment_zh else 'N/A'}

## 该类可用的属性（用于验证字段映射合规性）
{props_str}

## 检核要点
- 语义准确性：表业务含义是否与 FIBO 类描述一致？
- Domain/Range：字段映射的属性 domain 是否兼容？字段类型与属性 range 是否匹配？
- 过度泛化：是否存在更精确的子类？"""

    return prompt


# ---------------------------------------------------------------------------
# JSON output schema (for validation)
# ---------------------------------------------------------------------------

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

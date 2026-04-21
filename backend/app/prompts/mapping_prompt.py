"""Mapping LLM Prompt Templates - FIBO 2025Q4 International Standard Edition.

Uses the OMG/EDMC FIBO ontology (https://spec.edmcouncil.org/fibo/) as the
authoritative target ontology. Each candidate class is presented to the LLM
with its full semantic context: label, description, parent chain, and the
properties (with domain/range) that belong to that class.

遵循 Prompt Engineering 9 条工程级标准:
1. 角色定位先行  2. 任务边界显式声明  3. 输入输出契约化
4. 流程步骤化    5. 禁止项具体化      6. 不确定性有出口
7. 置信度可量化  8. 示例优于描述      9. 质量目标显式声明
"""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helper: Build compact name from FIBO URI
# ---------------------------------------------------------------------------

def _build_compact_name(uri: str) -> str:
    """Convert FIBO URI to compact name format: fibo-module-path:LocalName.
    
    Example: https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/hasCustomerIdentifier
             → fibo-fbc-pas-caa:hasCustomerIdentifier
    """
    if not uri:
        return ""
    
    # Extract local name (last part after / or #)
    local_name = uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    
    # Extract module path from FIBO URI
    # Format: https://spec.edmcouncil.org/fibo/ontology/MODULE/PATH/ClassOrProperty
    if "/ontology/" in uri:
        path_part = uri.split("/ontology/", 1)[-1]
        # Remove local name from path
        path_without_local = path_part.rsplit("/", 1)[0] if "/" in path_part else ""
        if path_without_local:
            # Build prefix: fibo-module-submodule
            path_parts = path_without_local.split("/")
            prefix = "fibo-" + "-".join(p.lower()[:3] for p in path_parts if p)
            return f"{prefix}:{local_name}"
    
    return local_name


# ---------------------------------------------------------------------------
# System Prompt - 遵循 9 条工程级标准
# ---------------------------------------------------------------------------

MAPPING_SYSTEM_PROMPT = """# 角色定义（原则1）
你是一位拥有 10 年经验的金融本体工程专家，
专注于 FIBO（Financial Industry Business Ontology）国际标准本体工程，
当前负责将中国企业 ERP 系统（BIPV5）的数据库表映射到 FIBO 2025Q4 本体。

# 任务与范围（原则2）
## 任务
将关系型数据库表映射到最合适的 FIBO 类和属性，输出符合 JSON Schema 的映射结果。

## 范围外（禁止处理）
- 禁止修改或推断原始 DDL 字段类型
- 禁止为同一个字段匹配多个 FIBO 属性
- 禁止将业务字段标记为 UNRESOLVED 仅因匹配难度较高
- 禁止返回任何非 JSON 格式的文本说明

# 输入格式（原则3）
## 输入
- database_name: 数据库名称（字符串）
- table_name: 表名（字符串）
- table_comment: 表中文注释（字符串）
- fields: 字段列表，每个字段包含 field_name, field_type, comment
- candidate_classes: FIBO 候选类列表，每个类包含 class_uri, label_en, comment_en, properties

# 输出格式（原则3）
严格返回以下 JSON，不得包含任何额外文字、markdown 代码块、解释说明：

{
  "mappable": "boolean - 是否可以映射",
  "fibo_class_uri": "string - 选中的 FIBO 类完整 URI",
  "confidence_level": "enum: HIGH|MEDIUM|LOW|UNRESOLVED",
  "mapping_reason": "string - 映射理由（2-3句中文）",
  "field_mappings": [
    {
      "field_name": "string - 字段名",
      "fibo_property_uri": "string - Compact Name格式如 fibo-fbc-pas-caa:hasCustomerIdentifier，或 null",
      "confidence_level": "enum: HIGH|MEDIUM|LOW|UNRESOLVED",
      "mapping_reason": "string - 映射理由（1句中文）",
      "is_unresolved": "boolean - 是否无法映射"
    }
  ]
}

# 执行步骤（原则4）
## 执行步骤（按序执行，不得跳过）

步骤 1 - 表级映射（类选择）：
  分析表名和注释的业务语义，从候选类中选择最佳匹配的 FIBO 类
  → 评估标准：类标签、描述、父类链与表业务的语义重叠度
  → 输出：fibo_class_uri, confidence_level (HIGH/MEDIUM/LOW/UNRESOLVED)

步骤 2 - 字段级映射（属性选择）：
  对表中的每个业务字段，从选中类的 Properties 列表中匹配最合适的属性
  → 必须使用 Compact Name 格式：fibo-模块前缀:属性名
  → 匹配依据：字段名、注释、数据类型与属性语义、range 类型的兼容性
  → 技术字段（id, create_time, update_time, is_deleted, tenant_id）标记为 UNRESOLVED
  → 输出：每个字段的 fibo_property_uri（Compact Name 格式）

步骤 3 - 置信度评估：
  对表级和字段级映射分别评估置信度
  → 依据原则7的评分规则
  → 低于 0.6 的字段标记为 needs_review

步骤 4 - 组装输出：
  按原则3定义的 JSON Schema 组装结果
  → 确保所有输入字段都出现在 field_mappings 中
  → 检查 JSON 格式合法性

# 禁止行为（原则5）
## 禁止行为
- 禁止在 JSON 输出前后添加任何文字（如"以下是结果："）
- 禁止使用 markdown 代码块包裹 JSON（如 ```json ... ```）
- 禁止将业务字段轻易标记为 UNRESOLVED，必须尝试匹配属性
- 禁止推断原始数据中未出现的字段值
- 禁止为同一个字段匹配多个 FIBO 属性
- 禁止使用完整 URI 作为 fibo_property_uri，必须使用 Compact Name 格式
- 禁止从其他候选类中选择属性，只能从选中的类中选择

# 不确定性处理（原则6）
## 不确定性处理规则

当遇到以下任一情况时，不得强行输出，必须返回 uncertainty_exit 结构：
1. 所有候选类与表的业务语义重叠度 < 40%
2. 输入数据缺少必要字段（table_name 或 fields 为空）
3. 候选类列表为空
4. 无法解析字段类型导致无法判断 range 兼容性

退出格式（替代正常输出）：
{
  "uncertainty_exit": true,
  "reason": "具体说明无法处理的原因",
  "confidence": "估计的语义重叠百分比"
}

# 置信度评分规则（原则7）
## 置信度评分规则

对表级和字段级映射分别评分（HIGH/MEDIUM/LOW/UNRESOLVED）：

| 级别 | 表级映射标准 | 字段级映射标准 |
|------|-------------|---------------|
| HIGH | 表业务语义与类标签/定义直接对应 | 字段名+注释与属性语义高度匹配，数据类型兼容 |
| MEDIUM | 表部分匹配或需一步推理 | 字段与属性语义相关但需推理，或类型不完全匹配 |
| LOW | 仅能匹配父类/祖先类，语义重叠弱 | 字段与属性语义关联较弱 |
| UNRESOLVED | 无合理候选类 | 技术字段或完全无语义关联 |

低于 MEDIUM 的字段必须在 mapping_reason 中说明原因。

# 质量目标（原则9）
## 质量目标
- 业务字段（非技术字段）映射覆盖率目标：≥ 80%
- 字段映射置信度为 HIGH 或 MEDIUM 的比例目标：≥ 70%
- 单表处理时间控制在 30 秒内
- 禁止为降低难度而将业务字段标记为 UNRESOLVED

# 示例（原则8）
## 示例 1（正例 - 完整映射）

输入：
Database: yonbip_fi_ctmfm
Table: bd_bankacct_currency
Comment: 银行账户币种子表
Fields:
  - id: BIGINT  # 主键
  - currency: VARCHAR(20)  # 币种代码
  - bankacct: VARCHAR(50)  # 银行账户ID
  - enable: TINYINT  # 启用状态

候选类（节选）：
[1] URI: https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/Currency
    Label: Currency
    Properties:
      • fibo-fbc-pas-caa:hasCurrencyIdentifier | hasCurrencyIdentifier (DatatypeProperty) → string
      • fibo-fbc-pas-caa:isIssuedBy | isIssuedBy (ObjectProperty) → IssuingAuthority

输出：
{
  "mappable": true,
  "fibo_class_uri": "https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/Currency",
  "confidence_level": "HIGH",
  "mapping_reason": "银行账户币种子表直接对应 FIBO Currency 类，描述货币与银行账户的关系",
  "field_mappings": [
    {
      "field_name": "id",
      "fibo_property_uri": null,
      "confidence_level": "UNRESOLVED",
      "mapping_reason": "技术主键，无业务语义",
      "is_unresolved": true
    },
    {
      "field_name": "currency",
      "fibo_property_uri": "fibo-fbc-pas-caa:hasCurrencyIdentifier",
      "confidence_level": "HIGH",
      "mapping_reason": "币种代码对应货币标识符属性",
      "is_unresolved": false
    },
    {
      "field_name": "bankacct",
      "fibo_property_uri": null,
      "confidence_level": "UNRESOLVED",
      "mapping_reason": "外键关联银行账户，Currency 类无直接关联账户的属性",
      "is_unresolved": true
    },
    {
      "field_name": "enable",
      "fibo_property_uri": null,
      "confidence_level": "UNRESOLVED",
      "mapping_reason": "业务状态标志，Currency 类无状态属性",
      "is_unresolved": true
    }
  ]
}

## 示例 2（反例 - 不确定性出口）

输入：
Database: unknown_db
Table: xyz_temp_table
Comment: （无注释）
Fields:
  - col1: VARCHAR(100)
  - col2: INT

候选类：（空列表或无匹配）

输出：
{
  "uncertainty_exit": true,
  "reason": "表名和注释无法识别业务语义，候选类列表为空，无法确定映射目标",
  "confidence": "0%"
}"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_mapping_prompt(
    database_name: str,
    table_name: str,
    table_comment: str,
    fields: List[Dict[str, Any]],
    candidate_classes: List[Dict[str, Any]],
) -> str:
    """Build the FIBO mapping prompt for LLM.

    Args:
        database_name:    Source database name.
        table_name:       Source table name.
        table_comment:    Chinese table comment / description.
        fields:           Parsed field list (field_name, field_type, comment).
        candidate_classes: Retrieved FIBO candidates (with properties + parent_chain).

    Returns:
        Formatted prompt string.
    """
    # ---- Fields section ----
    fields_lines = []
    for f in fields:
        line = f"  - {f.get('field_name', '')}: {f.get('field_type', '')}"
        if f.get("comment"):
            line += f"  # {f['comment']}"
        fields_lines.append(line)
    fields_str = "\n".join(fields_lines) if fields_lines else "  (no fields)"

    # ---- Candidates section ----
    candidate_blocks = []
    for i, c in enumerate(candidate_classes, 1):
        uri = c.get("class_uri", "")
        label = c.get("label_en") or uri.rsplit("/", 1)[-1]
        comment = c.get("comment_en", "") or ""
        module = c.get("module_path", "")
        parent_chain = c.get("parent_chain", [])
        properties = c.get("properties", [])

        block = f"[{i}] URI: {uri}\n"
        block += f"    Label: {label}\n"
        if module:
            block += f"    Module: {module}\n"
        if comment:
            block += f"    Description: {comment[:200]}\n"
        if parent_chain:
            block += f"    Parent chain: {' → '.join(parent_chain)}\n"
        if properties:
            block += "    Properties:\n"
            for p in properties[:15]:  # max 15 props per class
                prop_label = p.get("label_en") or p.get("uri", "").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                prop_range = p.get("range", "")
                if prop_range:
                    prop_range_name = prop_range.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                else:
                    prop_range_name = "–"
                # Build compact name: fibo-module-path:propertyName
                prop_uri = p.get("uri", "")
                compact_name = _build_compact_name(prop_uri)
                block += f"      • {compact_name} | {prop_label} ({p.get('type', 'Property')}) → {prop_range_name}\n"
        candidate_blocks.append(block)

    candidates_str = "\n".join(candidate_blocks) if candidate_blocks else "(no candidates found)"

    # ---- Full-field list for field_mappings output ----
    field_names_str = ", ".join(
        f.get("field_name", "") for f in fields if f.get("field_name")
    )

    prompt = f"""## 待映射的数据库表

Database: {database_name}
Table:    {table_name}
Comment:  {table_comment or '(none)'}

## 字段列表
{fields_str}

## FIBO 候选类（按语义相似度排序）

{candidates_str}

## 提醒
- 所有字段必须出现在 field_mappings 中: {field_names_str}
- 业务字段必须使用 Compact Name 格式（如 fibo-fbc-pas-caa:hasCustomerIdentifier）
- 禁止轻易将业务字段标记为 UNRESOLVED"""

    return prompt


# ---------------------------------------------------------------------------
# JSON output schema (for validation)
# ---------------------------------------------------------------------------

MAPPING_OUTPUT_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "description": "Normal mapping result",
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
                            "confidence_level": {
                                "enum": ["HIGH", "MEDIUM", "LOW", "UNRESOLVED"]
                            },
                            "mapping_reason": {"type": "string"},
                            "is_unresolved": {"type": "boolean"},
                        },
                        "required": ["field_name", "confidence_level", "is_unresolved"],
                    },
                },
            },
            "required": ["mappable", "confidence_level", "field_mappings"],
        },
        {
            "description": "Uncertainty exit (LLM cannot map with confidence)",
            "properties": {
                "uncertainty_exit": {"const": True},
                "reason": {"type": "string"},
                "confidence": {"type": "string"},
            },
            "required": ["uncertainty_exit", "reason"],
        },
    ],
}

---
name: llm-caller
description: >-
  统一的外部 LLM 调用规范，确保所有 LLM Prompt 符合工程级质量标准。
  当代码中涉及调用外部 LLM（OpenAI、Anthropic、Gemini、DeepSeek、DashScope 等）时自动激活。
  适用场景：编写 system_prompt、user_prompt、few-shot 示例、LLM 调用函数、Prompt 模板字符串。
  当用户说"写一个提示词"、"调用 LLM"、"接入大模型"、"写 prompt"时激活。
  确保所有写入代码的 Prompt 符合 9 条工程级质量标准，禁止生成单薄、模糊、无结构的提示词。
---

# LLM Caller - 统一外部 LLM 调用规范

## 核心原则：9 条工程级 Prompt 标准

每次为项目编写任何 LLM Prompt（system prompt、user prompt、few-shot 示例）时，
**必须严格遵守以下 9 条原则，全部满足才可写入代码**。

---

### 原则 1：角色定位先行（Role Before Task）

System Prompt 的第一句必须是角色定义，且角色必须包含三要素：
**专业身份 + 领域背景 + 工作语境**

```
✅ 正确：
你是一位拥有 10 年经验的供应链金融审核专家，
专注于央企应收账款保理业务的合规审核，
当前负责对接 SAP/用友/金蝶 ERP 系统导出的财务凭证数据。

❌ 禁止：
你是一个 AI 助手。
你是一个有用的助手。
你是专业的分析师。（没有领域背景和工作语境）
```

角色越具体，模型的回答越聚焦，幻觉越少。

---

### 原则 2：任务边界显式声明（Scope Boundary）

必须同时声明"做什么"和"不做什么"，缺一不可。

```
✅ 正确：
## 任务
从以下财务凭证 JSON 中提取：供应商名称、金额、开票日期、发票号码。

## 范围外（禁止处理）
- 不分析凭证的真实性
- 不推断未出现在原始数据中的字段
- 不对金额做任何计算或汇总

❌ 禁止：
请分析这份财务凭证。（没有边界，模型自由发挥）
```

---

### 原则 3：输入输出契约化（I/O Contract）

必须在 Prompt 中明确声明输入格式和输出格式，输出必须有 Schema 约束。

**输入声明：**
```
## 输入
- 类型：JSON 数组
- 字段：invoice_id(string), amount(float), supplier_name(string), issue_date(ISO8601)
- 示例见下方 <input_example>
```

**输出声明（必须包含完整 JSON Schema）：**
```
## 输出格式
严格返回以下 JSON，不得包含任何额外文字、markdown 代码块、解释说明：

{
  "extracted_items": [
    {
      "invoice_id": "string",
      "supplier_name": "string",
      "amount": "number",
      "issue_date": "YYYY-MM-DD",
      "confidence": "number (0.0-1.0)"
    }
  ],
  "total_count": "number",
  "has_uncertainty": "boolean"
}
```

代码实现要求：
- 输出解析必须有 try/catch，JSON.parse 失败时有明确的错误处理
- 禁止直接使用 `response.content` 而不做格式校验

---

### 原则 4：流程步骤化且强制有序（Ordered Steps）

复杂任务必须拆解为有编号的步骤，且明确步骤间的依赖关系。

```
✅ 正确：
## 执行步骤（按序执行，不得跳过）

步骤 1 - 数据完整性检查：
  检查输入 JSON 是否包含所有必要字段（invoice_id, amount, supplier_name）
  → 如果缺少任何字段，跳转至【不确定性处理】，不继续执行后续步骤

步骤 2 - 字段提取：
  从通过步骤 1 的数据中提取目标字段
  → amount 字段必须转换为 float，保留 2 位小数

步骤 3 - 置信度评估：
  对每条提取结果评估置信度（规则见原则 7）

步骤 4 - 组装输出：
  按原则 3 定义的 JSON Schema 组装结果

❌ 禁止：
请提取数据，然后评估质量，最后输出结果。（步骤模糊，无法校验执行）
```

---

### 原则 5：禁止项要比允许项更具体（Negative Constraints）

禁止项必须列举具体的行为，而不是泛泛的"不要出错"。

```
✅ 正确（具体禁止项）：
## 禁止行为
- 禁止在 JSON 输出前后添加任何文字（如"以下是结果："）
- 禁止使用 markdown 代码块包裹 JSON（如 ```json ... ```）
- 禁止推断原始数据中未出现的字段值
- 禁止对金额字段做四舍五入以外的数学运算
- 禁止在 supplier_name 为空时使用"未知"或"N/A"填充，应标记 confidence: 0

❌ 禁止（泛泛禁止项）：
不要犯错。
保持准确性。
不要产生幻觉。
```

---

### 原则 6：不确定性必须有出口（Uncertainty Exit）

LLM 遇到无法处理的情况时，必须有明确的退出路径，不允许模型自行猜测。

```
✅ 正确：
## 不确定性处理规则

当遇到以下任一情况时，不得继续执行任务，必须返回 uncertainty_exit 结构：
1. 输入数据缺少必要字段（invoice_id 或 amount）
2. 字段值格式无法识别（如日期格式不是 ISO8601）
3. 同一发票号出现多条冲突记录
4. 金额字段包含非数字字符且无法解析

退出格式（替代正常输出）：
{
  "uncertainty_exit": true,
  "reason": "具体说明无法处理的原因",
  "affected_items": ["受影响的 invoice_id 列表"],
  "suggestion": "建议人工处理的方式"
}

❌ 禁止：
遇到不确定的情况请尽力猜测。
如果数据不完整请自行补全。
```

代码实现要求：
- 调用方必须检查响应是否包含 `uncertainty_exit: true`
- 存在 uncertainty_exit 时必须走人工审核或错误处理流程，不得继续下游处理

---

### 原则 7：置信度可量化（Confidence Calibration）

每条输出结果必须附带置信度，且置信度评分规则必须在 Prompt 中明确定义。

```
✅ 正确（明确评分规则）：
## 置信度评分规则

对每条提取结果，按以下规则评分（0.0 - 1.0，保留 1 位小数）：

| 场景 | 置信度 |
|------|--------|
| 所有字段完整、格式标准、无歧义 | 0.9 - 1.0 |
| 字段完整但存在格式不规范（如日期格式多样） | 0.7 - 0.8 |
| 有 1 个非关键字段缺失或不确定 | 0.5 - 0.6 |
| 关键字段（invoice_id/amount）存在歧义 | 0.3 - 0.4 |
| 关键字段缺失或无法识别 | 0.0 - 0.2（触发 uncertainty_exit） |

低于 0.6 的结果必须在输出中标记 needs_review: true

❌ 禁止：
请评估结果的可信度。（没有评分规则，模型随意给分）
```

代码实现要求：
- 置信度低于阈值（建议 0.6）的结果必须走人工审核队列
- 阈值必须写成配置项，不得硬编码在 Prompt 中

---

### 原则 8：示例优于描述（Examples Over Descriptions）

每个 Prompt 必须包含至少 1 个完整的输入输出示例（few-shot），
复杂场景必须包含正例和反例各 1 个。

```
✅ 正确（完整 few-shot 示例）：
## 示例

### 示例 1（正例 - 数据完整）

输入：
{
  "invoice_id": "INV-2024-001",
  "amount": "158000.00",
  "supplier_name": "北京华润供应链有限公司",
  "issue_date": "2024-03-15"
}

输出：
{
  "extracted_items": [{
    "invoice_id": "INV-2024-001",
    "supplier_name": "北京华润供应链有限公司",
    "amount": 158000.00,
    "issue_date": "2024-03-15",
    "confidence": 1.0,
    "needs_review": false
  }],
  "total_count": 1,
  "has_uncertainty": false
}

### 示例 2（反例 - 触发不确定性出口）

输入：
{
  "invoice_id": "INV-2024-002",
  "amount": "金额待确认",
  "supplier_name": "上海XX贸易",
  "issue_date": "20240316"
}

输出：
{
  "uncertainty_exit": true,
  "reason": "amount 字段包含非数字内容'金额待确认'，无法解析；issue_date 格式不符合 ISO8601",
  "affected_items": ["INV-2024-002"],
  "suggestion": "请人工核实发票金额并修正日期格式后重新提交"
}

❌ 禁止：
示例输入：一张发票
示例输出：提取结果（没有实际数据的示例毫无意义）
```

---

### 原则 9：质量目标显式声明（Quality Targets）

当业务对输出质量有明确要求时，必须在 Prompt 中声明可量化的质量目标，
让 LLM 在自评置信度时有参照标准。

必须包含：
- 准确率目标：核心字段的识别准确率阈值
- 完整率目标：必填字段的覆盖率要求
- 拒识条件：什么情况下必须触发 uncertainty_exit 而不强行输出

示例：
```
## 质量目标
- 核心字段（金额、供应商名称、发票号）识别置信度 < 0.8 时，
  必须触发 uncertainty_exit，不得强行输出低质量结果
- 单条记录处理的输出 token 数控制在 500 以内
```

---

## 模型路由配置

### 模型选择策略

| 任务类型 | 主模型 | 降级模型 | 说明 |
|----------|--------|----------|------|
| 代码评审 | qwen-max | qwen-turbo | 需要强推理能力 |
| 需求评审 | qwen-max | - | 复杂语义理解 |
| 设计评审 | qwen-max | - | 架构分析 |
| 测试评审 | qwen-max | qwen-turbo | 逻辑检查 |
| 数据映射 | qwen-long | qwen-max | 长上下文 |
| 快速任务 | qwen-turbo | - | 简单问答 |

### 调用代码模板

```python
from backend.app.agents.llm_caller import LLMCaller, ModelType

# 初始化调用器
caller = LLMCaller(
    api_key=settings.DASHSCOPE_API_KEY,
    api_base=settings.DASHSCOPE_API_BASE
)

# 调用示例
result = await caller.call(
    task_type="code_review",  # 自动选择模型
    system_prompt=SYSTEM_PROMPT,
    user_prompt=user_input,
    output_schema=OUTPUT_SCHEMA
)

# 处理不确定性出口
if result.uncertainty_exit:
    logger.warning(f"Uncertainty: {result.uncertainty_exit['reason']}")
    await send_to_manual_review(result)
    return

# 处理低置信度结果
if result.confidence < CONFIDENCE_THRESHOLD:
    logger.warning(f"Low confidence: {result.confidence}")
    await flag_for_review(result)
```

---

## 检查清单

每次生成包含 LLM Prompt 的代码后，必须自检以下清单，
**有任何一项为 ❌ 则重新生成，不得提交给用户**：

| 检查项 | 原则 |
|--------|------|
| System Prompt 第一句是角色定义，包含身份+背景+语境 | 原则1 |
| 明确声明了任务范围和范围外的禁止项 | 原则2 |
| 输入格式和输出 JSON Schema 都有明确声明 | 原则3 |
| 复杂任务拆解为有编号的有序步骤 | 原则4 |
| 禁止项列举了至少 3 条具体行为 | 原则5 |
| 存在不确定性出口，并定义了退出格式 | 原则6 |
| 每条输出结果都有置信度字段，且评分规则明确 | 原则7 |
| 包含至少 1 个完整的输入输出示例 | 原则8 |
| 调用代码有 JSON 解析的 try/catch | 原则3 |
| 调用代码检查了 uncertainty_exit | 原则6 |
| 置信度阈值写成配置项而非硬编码 | 原则7 |

---

## 参考文件

- 详细 Prompt 模板示例：[examples.md](examples.md)
- 模型路由详细配置：[routing.md](routing.md)

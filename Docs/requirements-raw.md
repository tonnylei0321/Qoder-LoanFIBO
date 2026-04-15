# 需求文档

## 简介

本功能构建一条从 BIPV5 源系统 DDL 文件到 SASAC_GOV_v4.4 FIBO 本体的自动化映射 Pipeline。

**背景**：现有映射方式（Python 代码生成 TTL 占位符）产生的 242 个 TTL 文件中，227 个为空占位符，数据从未真正入库。新 Pipeline 改为"映射关系存入 PostgreSQL → ETL 时查映射表动态生成三元组"的架构，将映射规则与数据彻底分离。

**范围**：覆盖 DDL 拆解 → TTL 预处理 → LLM 映射 → 检核 Agent → 映射修订五个阶段，不包含后续 ETL 导入 GraphDB 的步骤。

**数据规模**：
- 源系统：BIPV5，77 个数据库，16,612 张表，DDL 文件约 114 万行
- 本体：SASAC_GOV_v4.4_FINAL.ttl，563 个类，282 个属性，约 400K 行

---

## 词汇表

- **DDL_Parser**：负责解析 DDL 文件并拆分为单表结构信息的组件
- **TTL_Indexer**：负责预处理 TTL 本体文件并构建结构化索引的组件
- **Mapping_LLM**：负责调用 LLM（qwen-max/qwen-turbo）执行表→FIBO 类映射的组件
- **Critic_Agent**：负责对入库映射关系进行多维度检核的 LangGraph Agent
- **Revision_LLM**：负责根据检核意见修订映射关系的组件（复用 Mapping_LLM 能力）
- **Pipeline_Orchestrator**：负责协调上述各组件按序执行的 LangGraph 工作流
- **TableDDL**：单张数据表的结构信息，包含表名、字段名、字段类型、注释
- **MappingRecord**：一条表→FIBO 类的映射关系记录，存储于 PostgreSQL
- **FieldMappingRecord**：一条字段→FIBO 属性的映射关系记录，存储于 PostgreSQL
- **ReviewRecord**：检核 Agent 对一条 MappingRecord 的检核意见记录
- **OntologyIndex**：TTL 本体文件预处理后的结构化索引，包含类名、属性、标签
- **ConfidenceLevel**：映射置信度，取值为 HIGH / MEDIUM / LOW / UNRESOLVED
- **FIBO_Class**：SASAC_GOV_v4.4 本体中的 OWL 类
- **FIBO_Property**：SASAC_GOV_v4.4 本体中的 OWL 属性（含 ObjectProperty 和 DatatypeProperty）

---

## 需求

### 需求 1：DDL 文件解析与拆分

**用户故事**：作为数据工程师，我希望系统能自动解析 BIPV5 的 DDL 文件并以数据表为单位拆分，以便后续逐表进行 FIBO 映射。

#### 验收标准

1. WHEN 用户上传或指定一个 DDL 文件路径，THE DDL_Parser SHALL 解析该文件并提取所有 CREATE TABLE 语句
2. WHEN DDL_Parser 解析一条 CREATE TABLE 语句，THE DDL_Parser SHALL 提取表名、每个字段的字段名、字段类型和字段注释（COMMENT）
3. IF 一个 DDL 文件中包含多个数据库的建表语句，THEN THE DDL_Parser SHALL 按数据库名对表进行分组，并在 TableDDL 中记录所属数据库名
4. IF 一条 CREATE TABLE 语句存在语法错误无法解析，THEN THE DDL_Parser SHALL 记录该表名和错误原因到解析错误日志，并继续处理剩余语句
5. THE DDL_Parser SHALL 将解析结果以 TableDDL 结构存入 PostgreSQL 的 table_registry 表，包含 database_name、table_name、raw_ddl、parsed_fields（JSON）字段
6. WHEN DDL_Parser 完成一个文件的解析，THE DDL_Parser SHALL 返回解析统计信息，包含总表数、成功解析数、失败数
7. FOR ALL 解析成功的 TableDDL，THE DDL_Parser SHALL 保证 parsed_fields 中每个字段至少包含 field_name 和 field_type 两个非空属性（round-trip 属性：原始 DDL 中的字段数 = parsed_fields 中的字段数）

---

### 需求 2：TTL 本体文件预处理与索引构建

**用户故事**：作为数据工程师，我希望系统预先将 400K+ 的 TTL 本体文件解析为结构化索引，以便 LLM 映射时只传入相关片段而非全量文件。

#### 验收标准

1. WHEN 用户指定 TTL 文件路径，THE TTL_Indexer SHALL 解析该文件并提取所有 OWL 类（owl:Class）的 URI、rdfs:label（中英文）、rdfs:comment
2. WHEN TTL_Indexer 解析 TTL 文件，THE TTL_Indexer SHALL 提取所有 OWL 属性（owl:ObjectProperty 和 owl:DatatypeProperty）的 URI、rdfs:label、rdfs:domain、rdfs:range
3. THE TTL_Indexer SHALL 将解析结果持久化到 PostgreSQL 的 ontology_class_index 表和 ontology_property_index 表
4. WHEN TTL_Indexer 完成索引构建，THE TTL_Indexer SHALL 支持按关键词（中文或英文）检索相关 FIBO_Class 列表，返回结果按语义相关度排序，单次检索最多返回 20 条
5. WHEN TTL_Indexer 完成索引构建，THE TTL_Indexer SHALL 支持按 FIBO_Class URI 查询其所有关联 FIBO_Property（domain 匹配该类或其父类）
6. IF TTL 文件格式不合法（非有效 Turtle 语法），THEN THE TTL_Indexer SHALL 返回解析失败错误，包含具体的行号和错误描述
7. THE TTL_Indexer SHALL 在索引构建完成后记录版本信息（文件名、文件 MD5、构建时间）到 ontology_index_meta 表，支持检测文件变更后重建索引
8. FOR ALL 解析成功的 FIBO_Class，THE TTL_Indexer SHALL 保证 ontology_class_index 中的 class_uri 与原始 TTL 文件中的 URI 完全一致（round-trip 属性）

---

### 需求 3：LLM 映射执行

**用户故事**：作为数据工程师，我希望系统将单表 DDL 信息和相关 TTL 片段发给 LLM，由 LLM 判断表是否可映射到 FIBO 类并返回映射关系，以便将映射结果入库。

#### 验收标准

1. WHEN Pipeline_Orchestrator 触发对一张表的映射，THE Mapping_LLM SHALL 从 OntologyIndex 中检索与该表语义相关的 FIBO_Class 候选列表（最多 20 个），而非传入全量 TTL 内容
2. WHEN Mapping_LLM 收到 TableDDL 和候选 FIBO_Class 列表，THE Mapping_LLM SHALL 调用 qwen-max 模型判断该表是否可映射到某个 FIBO_Class
3. IF Mapping_LLM 判断该表可映射，THEN THE Mapping_LLM SHALL 返回：目标 FIBO_Class URI、映射置信度（ConfidenceLevel）、映射理由说明
4. IF Mapping_LLM 判断该表可映射，THEN THE Mapping_LLM SHALL 同时返回每个字段的映射结果：字段名、目标 FIBO_Property URI（或 UNRESOLVED）、置信度、映射理由
5. IF Mapping_LLM 判断该表无法映射到任何 FIBO_Class，THEN THE Mapping_LLM SHALL 返回 unmappable 状态和原因说明，不生成字段级映射
6. THE Mapping_LLM SHALL 将映射结果写入 PostgreSQL 的 table_mapping 表（MappingRecord）和 field_mapping 表（FieldMappingRecord），包含 mapping_status、fibo_class_uri、confidence_level、mapping_reason 字段
7. IF qwen-max 调用失败或超时（超过 30 秒），THEN THE Mapping_LLM SHALL 自动降级使用 qwen-turbo 重试一次，并在 MappingRecord 中记录实际使用的模型名称
8. THE Mapping_LLM SHALL 支持批量处理模式，Pipeline_Orchestrator 可并发提交多张表的映射任务，并发数上限可配置（默认 5）
9. WHEN 一张表的映射任务完成，THE Mapping_LLM SHALL 更新 table_registry 中该表的 mapping_status 字段为 mapped 或 unmappable

---

### 需求 4：映射关系检核

**用户故事**：作为数据质量负责人，我希望系统对入库的映射关系进行多维度自动检核，以便发现语义错误、domain/range 不合规和过度泛化等问题。

#### 验收标准

1. WHEN Critic_Agent 对一条 MappingRecord 执行检核，THE Critic_Agent SHALL 验证表的业务语义（表名+字段注释）与目标 FIBO_Class 的 rdfs:label 和 rdfs:comment 是否语义匹配
2. WHEN Critic_Agent 对一条 FieldMappingRecord 执行检核，THE Critic_Agent SHALL 验证目标 FIBO_Property 的 rdfs:domain 是否与该字段所属表映射的 FIBO_Class 兼容（domain 为该类或其父类）
3. WHEN Critic_Agent 对一条 FieldMappingRecord 执行检核，THE Critic_Agent SHALL 验证目标 FIBO_Property 的 rdfs:range 是否与字段的 SQL 数据类型兼容（例如 VARCHAR → xsd:string，DECIMAL → xsd:decimal）
4. WHEN Critic_Agent 对一条 MappingRecord 执行检核，THE Critic_Agent SHALL 检查是否存在比当前映射类更精确的子类可用（过度泛化检查），若存在则在检核意见中列出候选子类
5. THE Critic_Agent SHALL 将每条检核结果写入 PostgreSQL 的 mapping_review 表（ReviewRecord），包含 issue_type（semantic / domain_range / over_generalization）、severity（P0-P3）、issue_description、suggested_fix 字段
6. IF 一条 MappingRecord 的检核结果包含 P0 或 P1 级问题，THEN THE Critic_Agent SHALL 将该 MappingRecord 的 review_status 更新为 needs_revision
7. IF 一条 MappingRecord 的检核结果仅包含 P2/P3 级问题或无问题，THEN THE Critic_Agent SHALL 将该 MappingRecord 的 review_status 更新为 approved 或 approved_with_suggestions
8. THE Critic_Agent SHALL 支持对单条 MappingRecord 的按需检核，也支持批量检核所有 review_status 为 pending 的记录
9. WHEN Critic_Agent 完成一批检核，THE Critic_Agent SHALL 返回检核统计摘要，包含总检核数、approved 数、needs_revision 数、各 issue_type 的问题数量

---

### 需求 5：映射关系修订

**用户故事**：作为数据工程师，我希望系统根据检核意见自动修订映射关系，以便提升映射质量并减少人工干预。

#### 验收标准

1. WHEN Pipeline_Orchestrator 触发修订流程，THE Revision_LLM SHALL 读取所有 review_status 为 needs_revision 的 MappingRecord 及其关联的 ReviewRecord
2. WHEN Revision_LLM 处理一条需修订的 MappingRecord，THE Revision_LLM SHALL 将原始 TableDDL、原映射结果、检核意见（ReviewRecord）一并发给 LLM，要求针对每条 must_fix 问题给出修订方案
3. WHEN Revision_LLM 完成修订，THE Revision_LLM SHALL 更新 table_mapping 和 field_mapping 表中对应记录的映射结果，并将 revision_count 字段加 1
4. THE Revision_LLM SHALL 在 mapping_review 表中记录每次修订的变更内容（revision_diff），包含修订前后的 fibo_class_uri 和 confidence_level
5. IF 一条 MappingRecord 经过 3 次修订后 review_status 仍为 needs_revision，THEN THE Revision_LLM SHALL 将该记录标记为 manual_review_required，并停止自动修订
6. WHEN 修订完成后，THE Pipeline_Orchestrator SHALL 自动触发 Critic_Agent 对修订后的记录重新检核，形成"修订→检核"闭环
7. THE Revision_LLM SHALL 记录每次修订使用的 LLM 模型名称和 token 消耗量到 mapping_revision_log 表

---

### 需求 6：Pipeline 编排与进度管理

**用户故事**：作为数据工程师，我希望系统提供完整的 Pipeline 编排能力，支持断点续跑、进度查询和任务管理，以便处理 16,612 张表的大规模映射任务。

#### 验收标准

1. THE Pipeline_Orchestrator SHALL 支持创建映射任务（MappingJob），指定目标数据库范围（全量或指定数据库名列表）
2. WHEN 一个 MappingJob 被创建，THE Pipeline_Orchestrator SHALL 按 DDL 拆解 → TTL 预处理 → LLM 映射 → 检核 → 修订的顺序依次执行各阶段
3. IF Pipeline_Orchestrator 在执行过程中发生中断（服务重启、异常退出），THEN THE Pipeline_Orchestrator SHALL 在重启后从上次中断的表继续执行，不重复处理已完成的表
4. THE Pipeline_Orchestrator SHALL 提供 REST API 接口，支持查询 MappingJob 的当前状态（pending / running / paused / completed / failed）、已处理表数、成功率
5. THE Pipeline_Orchestrator SHALL 支持暂停和恢复 MappingJob，暂停后正在执行的当前批次完成后停止，不中断单表任务
6. WHEN 一个 MappingJob 全部阶段完成，THE Pipeline_Orchestrator SHALL 生成执行报告，包含：总表数、mapped 数、unmappable 数、approved 数、needs_revision 数、manual_review_required 数、LLM token 总消耗
7. THE Pipeline_Orchestrator SHALL 支持对单张表触发重新映射（覆盖已有映射结果），用于人工干预后的重跑场景

---

### 需求 7：映射结果查询与导出

**用户故事**：作为数据工程师，我希望能查询和导出映射结果，以便进行人工审核和后续 ETL 阶段使用。

#### 验收标准

1. THE Pipeline_Orchestrator SHALL 提供 REST API，支持按数据库名、表名、mapping_status、review_status、confidence_level 等条件分页查询 MappingRecord，每页最多 100 条
2. THE Pipeline_Orchestrator SHALL 提供 REST API，支持查询指定表的完整映射详情，包含表级映射和所有字段级映射及其检核意见
3. THE Pipeline_Orchestrator SHALL 支持将指定范围的映射结果导出为 JSON 格式，导出内容包含 MappingRecord、FieldMappingRecord 和 ReviewRecord
4. WHERE 用户需要人工修正映射关系，THE Pipeline_Orchestrator SHALL 提供 REST API 支持直接更新单条 MappingRecord 或 FieldMappingRecord 的映射目标，并记录修改人和修改时间
5. THE Pipeline_Orchestrator SHALL 提供映射统计概览接口，返回各数据库的映射完成率、各 ConfidenceLevel 的分布比例、FIBO_Class 使用频次 Top 20

---

### 需求 8：LLM Prompt 质量保障

**用户故事**：作为系统开发者，我希望所有 LLM 调用使用经过工程化审查的 Prompt，以便保证映射质量的一致性和可追溯性。

#### 验收标准

1. THE Mapping_LLM SHALL 使用结构化 Prompt 模板，模板包含：角色定义、输入格式说明（TableDDL + 候选 FIBO_Class 列表）、输出格式约束（JSON Schema）、映射规则说明（置信度定义、UNRESOLVED 处理策略）
2. THE Critic_Agent SHALL 使用结构化 Prompt 模板，模板包含：检核维度说明（语义准确性、domain/range 合规性、过度泛化）、问题严重度定义（P0-P3）、输出格式约束（JSON Schema）
3. THE Revision_LLM SHALL 使用结构化 Prompt 模板，模板包含：修订规则（逐条处理 must_fix、不扩大修改范围）、输出格式约束（JSON Schema）
4. IF LLM 返回的 JSON 格式不符合预期 Schema，THEN THE Mapping_LLM SHALL 重试最多 2 次，若仍失败则将该表标记为 llm_parse_error 并记录原始响应
5. THE Mapping_LLM SHALL 记录每次 LLM 调用的 prompt_tokens、completion_tokens、model_name、latency_ms 到 llm_call_log 表，用于成本分析和性能监控

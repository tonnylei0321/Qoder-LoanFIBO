## ADDED Requirements

### Requirement: sqlglot 主解析路径覆盖
`parse_ddl_content` SHALL 使用 sqlglot 解析标准 MySQL CREATE TABLE 语句，返回包含 `table_name`、`database_name`、`parsed_fields`、`raw_ddl` 的字典列表。

#### Scenario: 标准 CREATE TABLE 被 sqlglot 正确解析
- **WHEN** 调用 `parse_ddl_content` 传入含一个标准 CREATE TABLE 的 DDL 字符串
- **THEN** 返回列表长度为 1，且结果包含正确的 `table_name` 和非空的 `parsed_fields`

#### Scenario: 字段级信息被正确提取
- **WHEN** DDL 包含字段名、类型、注释约束
- **THEN** `parsed_fields` 中每个字段含 `field_name`、`field_type`、`is_nullable`、`is_primary_key`

### Requirement: regex 兜底解析路径覆盖
当 sqlglot 抛出异常时，`parse_ddl_content` SHALL 降级调用 `parse_ddl_regex`，仍返回解析结果。

#### Scenario: sqlglot 失败时 regex 接管
- **WHEN** sqlglot 无法解析（通过 patch 抛出异常），调用 `parse_ddl_content`
- **THEN** 结果非空，`table_name` 正确，且 `parsed_fields` 至少包含带 comment 的字段

### Requirement: DDL 目录不存在时节点返回 error state
`parse_ddl_node` SHALL 在 DDL 目录不存在时，向 `state['error']` 写入错误信息并返回，不抛出异常。

#### Scenario: 目录不存在时 state 包含 error 字段
- **WHEN** `DDL_DIR` 环境变量指向不存在的路径，调用 `parse_ddl_node`
- **THEN** 返回的 state 中 `state['error']` 不为 None，且函数不抛出异常

### Requirement: DB 幂等性（同表不重复插入）
`parse_ddl_node` SHALL 在同一张表已存在于 `table_registry` 时跳过插入，不抛出唯一约束异常。

#### Scenario: 同表第二次解析跳过 DB insert
- **WHEN** mock DB 的 `scalar_one_or_none` 返回非 None（模拟已存在记录），调用 `parse_ddl_node`
- **THEN** `db.add` 未被调用，函数正常返回 state

## ADDED Requirements

### Requirement: calculate_file_md5 纯函数正确性
`calculate_file_md5` SHALL 对给定文件返回确定性的 MD5 hex 字符串，相同内容返回相同 hash，不同内容返回不同 hash。

#### Scenario: 相同文件内容返回相同 MD5
- **WHEN** 给定一个文件路径调用 `calculate_file_md5`
- **THEN** 返回 32 字符的十六进制字符串，且对相同内容的文件两次调用结果相同

### Requirement: extract_namespace 纯函数正确性
`extract_namespace` SHALL 从 URI 字符串中提取命名空间前缀，支持 `#` 分隔和 `/` 分隔两种格式。

#### Scenario: 井号分隔的 URI 提取命名空间
- **WHEN** 传入 `http://example.org/ontology#LoanClass`
- **THEN** 返回 `http://example.org/ontology#`

#### Scenario: 斜杠分隔的 URI 提取命名空间
- **WHEN** 传入 `http://example.org/ontology/LoanClass`
- **THEN** 返回 `http://example.org/ontology/`

### Requirement: parse_ttl_file 解析最小 TTL 图
`parse_ttl_file` SHALL 从 TTL 文件路径中提取 owl:Class 和 owl:Property 定义，以字典列表形式返回。

#### Scenario: 解析含 2 个 Class 的 TTL 文件返回 2 个 class 记录
- **WHEN** 给定一个包含 2 个 owl:Class 定义的 TTL 文件路径（mock Graph.query）
- **THEN** 返回 (classes, properties) 元组，classes 列表长度为 2，每个元素含 class_uri 字段

### Requirement: index_ttl_node 目录不存在时返回 error state
`index_ttl_node` SHALL 在 TTL 目录不存在时，向 `state['error']` 写入错误信息并返回，不抛出异常。

#### Scenario: 目录不存在时 state 包含 error 字段
- **WHEN** `TTL_DIR` 环境变量指向不存在的路径，调用 `index_ttl_node`
- **THEN** 返回的 state 中 `state['error']` 不为 None，函数不抛出异常

### Requirement: index_ttl_node 文件已索引时跳过（幂等）
`index_ttl_node` SHALL 在同一 TTL 文件（文件名+MD5 匹配）已存在于索引元数据表时，跳过解析和插入。

#### Scenario: 同文件第二次索引时 parse_ttl_file 不被调用
- **WHEN** mock DB 的 `scalar_one_or_none` 返回非 None（模拟已存在记录），调用 `index_ttl_node`
- **THEN** `parse_ttl_file` 未被调用，函数正常返回 state

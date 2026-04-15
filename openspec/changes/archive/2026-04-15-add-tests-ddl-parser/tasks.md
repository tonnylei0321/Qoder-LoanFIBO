## 1. RED — 编写失败测试

- [x] 1.1 创建 `tests/unit/services/test_ddl_parser.py`，编写 5 个测试（sqlglot 主路径、字段提取、regex 兜底、目录不存在、DB 幂等）
- [x] 1.2 运行测试，确认全部失败（RED 状态）
- [x] 1.3 提交：`test: add failing tests for ddl_parser`

## 2. GREEN — 确认现有实现满足规范

- [x] 2.1 运行测试，确认全部通过（纯函数路径无需改代码）
- [x] 2.2 如有测试失败，修复生产代码使其通过
- [x] 2.3 提交：`feat: verify ddl_parser meets test requirements`

## 3. REFACTOR — 可选优化

- [x] 3.1 检查 `parse_ddl_content` 中的 exception catch 是否过宽，必要时缩小
- [x] 3.2 提交（如有改动）：`refactor: improve ddl_parser error handling`

## 4. REVIEW — 代码评审

- [x] 4.1 使用 code-reviewer Skill 评审测试文件和变更
- [x] 4.2 修复所有 P1/P2 问题
- [x] 4.3 提交：`review: address code-reviewer feedback for ddl_parser tests`

## 5. ARCHIVE — 归档

- [x] 5.1 将 delta specs 同步到 `openspec/specs/ddl-parser-tests/spec.md`
- [x] 5.2 归档变更到 `openspec/changes/archive/`
- [x] 5.3 提交并推送：`chore: archive add-tests-ddl-parser change`

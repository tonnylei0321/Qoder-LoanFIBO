# OpenSpec 使用指南

## 简介

OpenSpec 是一个轻量级的规范驱动开发框架，帮助你在编写代码前先规划清楚需求。

**版本**: 1.2.0  
**安装**: `npm install -g @fission-ai/openspec@latest`

---

## 目录结构

```
openspec/
├── config.yaml          # OpenSpec 配置
├── specs/               # 规范文件（按功能组织）
└── changes/             # 变更提案
```

---

## 快速开始

### 1. 创建第一个规范提案

在 Qoder 中使用 slash 命令：

```
/opsx:propose "Add user authentication with JWT tokens"
```

或者使用 CLI：

```bash
openspec propose "Add user authentication"
```

### 2. 工作流

```
提案（Proposal） → 设计（Design） → 任务分解（Tasks） → 实施（Apply） → 归档（Archive）
```

---

## Slash 命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/opsx:propose` | 创建变更提案 | `/opsx:propose "Add rate limiting"` |
| `/opsx:apply` | 实施变更 | `/opsx:apply add-rate-limiting` |
| `/opsx:archive` | 归档已完成的变更 | `/opsx:archive add-rate-limiting` |
| `/opsx:explore` | 浏览现有规范 | `/opsx:explore` |

---

## 规范文件结构

### 规范文件示例

```markdown
# authentication Specification

## Purpose
Manage user authentication and session lifecycle.

## Requirements

### Requirement: User login
The system SHALL authenticate users with email and password.

#### Scenario: Successful login
- GIVEN a registered user
- WHEN they provide valid credentials
- THEN return a JWT token
- AND set session expiration

#### Scenario: Failed login
- GIVEN an invalid email or password
- WHEN login is attempted
- THEN return 401 Unauthorized
- AND increment failed attempt counter
```

---

## 变更提案结构

```
openspec/changes/add-authentication/
├── proposal.md        # 变更描述和影响分析
├── design.md          # 技术设计决策
├── tasks.md           # 实施任务分解
└── specs/             # 规范 delta
    └── authentication/
        └── spec.md    # 新增/修改的规范
```

---

## 与 TDD 结合

OpenSpec 和 TDD 完美配合：

```
1. OpenSpec: 创建规范提案
   ↓
2. OpenSpec: 生成实施任务
   ↓
3. TDD RED: 编写失败的测试
   ↓
4. TDD GREEN: 实现代码
   ↓
5. TDD REFACTOR: 重构优化
   ↓
6. Code Review: LLM 评审
   ↓
7. OpenSpec: 归档变更
```

---

## 最佳实践

### 1. 规范粒度

- 一个规范文件 = 一个功能模块
- 规范长度建议 < 500 字
- 使用场景（Scenario）描述行为

### 2. 变更管理

- 每次功能变更创建一个提案
- 提案通过后再开始编码
- 完成后及时归档

### 3. 规范维护

- 规范与代码一起提交
- 代码变更时同步更新规范
- 定期审查规范的准确性

---

## 配置说明

### openspec/config.yaml

```yaml
schema: spec-driven

# 项目上下文（可选）
# 提供给 AI 使用，描述技术栈、约定、领域知识等
context: |
  Tech stack: Python 3.11, FastAPI, LangGraph, SQLAlchemy Async
  We follow TDD (Red-Green-Refactor)
  Domain: DDL to FIBO ontology mapping pipeline
  LLM: DashScope (qwen-max, qwen-long)

# 自定义规则（可选）
rules:
  proposal:
    - 提案描述不超过 500 字
    - 必须包含影响分析
  tasks:
    - 每个任务不超过 2 小时
    - 必须包含测试任务
```

---

## 示例：创建第一个规范

### 场景：为 Pipeline 添加进度报告功能

```bash
# 1. 创建提案
/opsx:propose "Add progress reporting endpoint for pipeline jobs"

# 2. 查看生成的文件
ls openspec/changes/add-progress-report/
# proposal.md  design.md  tasks.md  specs/

# 3. 评审提案
cat openspec/changes/add-progress-report/proposal.md

# 4. 开始实施
/opsx:apply add-progress-report

# 5. 完成后归档
/opsx:archive add-progress-report
```

---

## 故障排查

### 问题：Slash 命令不生效

**解决**: 重启 Qoder

### 问题：找不到 openspec 命令

**解决**: 确认已全局安装
```bash
npm install -g @fission-ai/openspec@latest
openspec --version
```

### 问题：规范文件未生成

**解决**: 检查 Qoder 是否有 `.qoder/` 目录写权限

---

## 学习资源

- **官方文档**: https://openspec.dev/
- **GitHub**: https://github.com/Fission-AI/OpenSpec/
- **Discord**: https://discord.gg/YctCnvvshC

---

## 项目规范

本项目遵循以下规范：

1. **OpenSpec**: 规范驱动开发
2. **TDD**: 测试驱动开发（Red-Green-Refactor）
3. **LLM Caller**: 统一 LLM 调用规范（9 条原则）
4. **Code Reviewer**: 代码评审规范（6 维度检查）

所有规范文件位于 `.qoder/skills/` 目录。

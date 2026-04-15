## Why

`tests/conftest.py` 目前同时承担两个职责：
1. 为 unit 测试 mock 所有外部依赖（langchain、sqlalchemy、DB models 等）
2. 作为 pytest 根 conftest 被所有测试子目录继承

当未来添加 integration 测试时，这些 unit 专用 mock 会错误地污染 integration 测试，
导致 integration 测试无法使用真实依赖。

## What Changes

- 将所有 unit 专用 mock 迁移到 `tests/unit/conftest.py`
- `tests/conftest.py` 保留为极简 root conftest（仅放跨层共享内容，或留空）
- 创建 `tests/integration/` 目录占位，为后续 integration 测试做准备

## Capabilities

### Modified Capabilities

- `conftest-layered-structure`: conftest 分层，unit mock 与 root 配置分离

## Impact

- 影响文件：`tests/conftest.py`（清空 unit mock）
- 新增文件：`tests/unit/conftest.py`（承接全部 unit mock）
- 行为无变化：所有 23 个 unit 测试仍应通过

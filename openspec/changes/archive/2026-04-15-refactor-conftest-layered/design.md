## Design

### Structure After Refactor

```
tests/
├── conftest.py          # Root: shared pytest settings only (e.g. asyncio_mode)
├── unit/
│   ├── conftest.py      # Unit-layer: all sys.modules mock stubs
│   └── services/
│       ├── test_ddl_parser.py
│       ├── test_ttl_indexer.py
│       ├── test_critic_agent.py
│       └── test_mapping_llm.py
└── integration/
    └── __init__.py      # Placeholder for future integration tests
```

### pytest conftest Scoping Rules

pytest loads conftest.py files from **outermost to innermost** directory, in order:
1. `tests/conftest.py` — applied to all tests
2. `tests/unit/conftest.py` — applied only to tests under `tests/unit/`
3. `tests/integration/conftest.py` — applied only to tests under `tests/integration/`

By moving unit mocks to `tests/unit/conftest.py`, integration tests will load
`tests/conftest.py` only, getting clean (unmocked) imports.

### Migration Plan

1. Create `tests/unit/conftest.py` with full content from current `tests/conftest.py`
2. Replace `tests/conftest.py` with a minimal root conftest (comment only)
3. Verify 23 unit tests still pass

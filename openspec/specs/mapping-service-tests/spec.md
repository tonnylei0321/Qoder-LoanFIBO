## ADDED Requirements

### Requirement: Unit Test Coverage for process_single_table
`process_single_table` MUST have unit test coverage for all major execution paths.
Tests SHALL use mocks for database session, LLM client, and vector search.

#### Scenario: Happy path test exists
- **WHEN** LLM returns a valid mapping JSON
- **THEN** a passing test verifies the function returns `{"status": "success"}` and calls `save_mapping_result`

#### Scenario: Uncertainty path test exists
- **WHEN** LLM returns a response containing `uncertainty_exit`
- **THEN** a passing test verifies the function returns `{"status": "uncertainty"}` and does NOT call `save_mapping_result`

#### Scenario: No candidates path test exists
- **WHEN** `search_candidates` returns an empty list
- **THEN** a passing test verifies the function returns `{"status": "unmappable"}` and calls `mark_unmappable`

#### Scenario: Fallback path test exists
- **WHEN** the primary LLM call raises an exception
- **THEN** a passing test verifies `try_fallback_mapping` is called

---

### Requirement: TDD Commit Convention
All tests for this change SHALL be committed before the implementation code.
Commit messages MUST follow the convention:
- `test: add failing test for <feature>` (RED phase)
- `feat: implement <feature> to pass tests` (GREEN phase)
- `refactor: improve <feature>` (REFACTOR phase)

#### Scenario: Test commit precedes implementation commit
- **WHEN** reviewing git log for this change
- **THEN** the `test:` commit appears before the `feat:` commit in history

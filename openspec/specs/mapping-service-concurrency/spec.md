## ADDED Requirements

### Requirement: Semaphore Scope
`mapping_semaphore` SHALL only wrap the `llm.ainvoke(...)` call within `process_single_table`,
and MUST NOT wrap database queries, vector search, or result persistence operations.

#### Scenario: DB query runs outside semaphore
- **WHEN** 10 tables are processed concurrently with `MAX_CONCURRENCY=5`
- **THEN** all 10 database queries run in parallel without waiting for the semaphore

#### Scenario: LLM calls respect concurrency limit
- **WHEN** 10 tables are processed concurrently with `MAX_CONCURRENCY=5`
- **THEN** at most 5 `llm.ainvoke()` calls execute simultaneously at any point in time

---

### Requirement: Uncertainty Exit Handling
After parsing the LLM response, the system SHALL check for the `uncertainty_exit` field.
If present and non-null, the system MUST log a warning, persist the uncertainty record,
and return `{"status": "uncertainty"}` without proceeding to save a mapping result.

#### Scenario: LLM returns uncertainty_exit
- **WHEN** the LLM response JSON contains `{"uncertainty_exit": {"reason": "ambiguous DDL"}}`
- **THEN** the function returns `{"status": "uncertainty", "reason": "ambiguous DDL"}` and does NOT insert a `TableMapping` record

#### Scenario: LLM returns normal result
- **WHEN** the LLM response JSON does NOT contain `uncertainty_exit`
- **THEN** the function proceeds to save the mapping result normally

---

### Requirement: Fallback Model Configuration
The fallback model for mapping MUST be configured via `settings.MAPPING_FALLBACK_MODEL`,
and MUST NOT reference `settings.CRITIC_MODEL`.

#### Scenario: Fallback uses correct config
- **WHEN** the primary LLM call fails
- **THEN** `try_fallback_mapping` uses `settings.MAPPING_FALLBACK_MODEL` to instantiate the fallback LLM client

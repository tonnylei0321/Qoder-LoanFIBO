"""Unit tests for mapping_llm.py — RED phase.

TDD: These tests are written BEFORE the fix.
They describe the DESIRED behavior after the fix is applied.
Running them now should FAIL (except unmappable path which may pass).
"""
import asyncio
import json
import importlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Must import the module before patching
import backend.app.services.mapping_llm  # noqa: F401

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_table_registry(table_name="loan_account", raw_ddl="CREATE TABLE loan_account (id INT);", parsed_fields=None):
    """Create a minimal mock TableRegistry object."""
    registry = MagicMock()
    registry.table_name = table_name
    registry.database_name = "lending_db"
    registry.raw_ddl = raw_ddl
    registry.parsed_fields = parsed_fields or [{"name": "id", "type": "INT"}]
    registry.mapping_status = None
    return registry


def make_llm_response(content: str):
    """Create a minimal mock LLM response."""
    resp = MagicMock()
    resp.content = content
    resp.usage = MagicMock()
    resp.usage.total_tokens = 500
    return resp


VALID_MAPPING_JSON = json.dumps({
    "mappable": True,
    "fibo_class_uri": "https://spec.edmcouncil.org/fibo/ontology/LOAN/LoanCore/LoanAccount",
    "confidence_level": "HIGH",
    "mapping_reason": "The table name and structure match LoanAccount.",
    "field_mappings": [
        {
            "field_name": "id",
            "fibo_property_uri": "https://www.omg.org/spec/Commons/Identifiers/identifier",
            "confidence_level": "HIGH",
            "mapping_reason": "id is a standard identifier property."
        }
    ]
})

UNCERTAINTY_EXIT_JSON = json.dumps({
    "uncertainty_exit": {
        "reason": "The DDL is too ambiguous to determine a FIBO mapping.",
        "confidence": 0.2
    }
})


# ---------------------------------------------------------------------------
# Test 1: 信号量只包裹 LLM 调用（核心 P1 修复）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semaphore_only_wraps_llm_call():
    """
    SPEC: mapping-service-concurrency / Semaphore Scope

    GIVEN: process_single_table is called with valid table and candidates
    WHEN:  execution flows through DB query → LLM call → save result
    THEN:  the semaphore is only acquired AROUND llm.ainvoke(), not around db.get()
           i.e., db.get() is called BEFORE semaphore is acquired (or concurrently)

    This test verifies the call ordering:
        db.get() → search_candidates() → [acquire semaphore] → llm.ainvoke() → [release semaphore] → save
    """
    call_order = []

    mock_table = make_table_registry()

    # Track call order for each operation
    async def mock_db_get(*args, **kwargs):
        call_order.append("db_get")
        return mock_table

    async def mock_search_candidates(*args, **kwargs):
        call_order.append("search_candidates")
        return [{"uri": "http://example.com#LoanAccount", "label": "LoanAccount"}]

    async def mock_llm_invoke(*args, **kwargs):
        call_order.append("llm_invoke")
        return make_llm_response(VALID_MAPPING_JSON)

    async def mock_save(*args, **kwargs):
        call_order.append("save_result")

    # Build a semaphore that records acquire/release
    real_semaphore = asyncio.Semaphore(5)
    original_aenter = real_semaphore.__aenter__

    async def tracked_aenter(*args, **kwargs):
        call_order.append("semaphore_acquire")
        return await original_aenter(*args, **kwargs)

    real_semaphore.__aenter__ = tracked_aenter

    mock_db_session = AsyncMock()
    mock_db_session.get = mock_db_get
    mock_db_ctx = AsyncMock()
    mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.services.mapping_llm.async_session_factory", return_value=mock_db_ctx), \
         patch("backend.app.services.mapping_llm.search_candidates", side_effect=mock_search_candidates), \
         patch("backend.app.services.mapping_llm.mapping_semaphore", real_semaphore), \
         patch("backend.app.services.mapping_llm.save_mapping_result", side_effect=mock_save):

        mock_llm = MagicMock()
        mock_llm.ainvoke = mock_llm_invoke

        with patch("backend.app.services.mapping_llm.get_mapping_llm", return_value=mock_llm):
            from backend.app.services.mapping_llm import process_single_table
            await process_single_table(job_id=1, table_registry_id=100)

    # ASSERT: db_get must come before semaphore_acquire
    assert "db_get" in call_order, "db_get was not called"
    assert "semaphore_acquire" in call_order, "semaphore was never acquired"
    assert "llm_invoke" in call_order, "llm_invoke was not called"

    db_idx = call_order.index("db_get")
    sem_idx = call_order.index("semaphore_acquire")
    llm_idx = call_order.index("llm_invoke")

    assert db_idx < sem_idx, (
        f"FAIL: db_get (pos {db_idx}) should happen BEFORE semaphore_acquire (pos {sem_idx}). "
        f"Full order: {call_order}"
    )
    assert sem_idx < llm_idx, (
        f"FAIL: semaphore_acquire (pos {sem_idx}) should happen BEFORE llm_invoke (pos {llm_idx}). "
        f"Full order: {call_order}"
    )


# ---------------------------------------------------------------------------
# Test 2: 正常映射路径（happy path）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_single_table_success():
    """
    SPEC: mapping-service-tests / Unit Test Coverage for process_single_table

    GIVEN: DB returns a valid table, search_candidates returns candidates, LLM returns valid JSON
    WHEN:  process_single_table is called
    THEN:  returns {"status": "success"} and save_mapping_result is called once
    """
    mock_table = make_table_registry()
    mock_candidates = [{"uri": "http://example.com#LoanAccount", "label": "LoanAccount"}]

    mock_db_session = AsyncMock()
    mock_db_session.get = AsyncMock(return_value=mock_table)
    mock_db_ctx = AsyncMock()
    mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_save = AsyncMock()

    with patch("backend.app.services.mapping_llm.async_session_factory", return_value=mock_db_ctx), \
         patch("backend.app.services.mapping_llm.search_candidates", return_value=mock_candidates), \
         patch("backend.app.services.mapping_llm.save_mapping_result", mock_save):

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=make_llm_response(VALID_MAPPING_JSON))

        with patch("backend.app.services.mapping_llm.get_mapping_llm", return_value=mock_llm):
            from backend.app.services import mapping_llm
            # Reload to pick up fresh module state
            import importlib
            importlib.reload(mapping_llm)

            result = await mapping_llm.process_single_table(job_id=1, table_registry_id=100)

    assert result["status"] == "success", f"Expected 'success', got: {result}"
    mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: uncertainty_exit 路径
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_single_table_uncertainty_exit():
    """
    SPEC: mapping-service-concurrency / Uncertainty Exit Handling

    GIVEN: LLM returns a response containing uncertainty_exit
    WHEN:  process_single_table is called
    THEN:  returns {"status": "uncertainty"} and save_mapping_result is NOT called
    """
    mock_table = make_table_registry()
    mock_candidates = [{"uri": "http://example.com#LoanAccount", "label": "LoanAccount"}]

    mock_db_session = AsyncMock()
    mock_db_session.get = AsyncMock(return_value=mock_table)
    mock_db_ctx = AsyncMock()
    mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_save = AsyncMock()

    with patch("backend.app.services.mapping_llm.async_session_factory", return_value=mock_db_ctx), \
         patch("backend.app.services.mapping_llm.search_candidates", return_value=mock_candidates), \
         patch("backend.app.services.mapping_llm.save_mapping_result", mock_save):

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=make_llm_response(UNCERTAINTY_EXIT_JSON))

        with patch("backend.app.services.mapping_llm.get_mapping_llm", return_value=mock_llm):
            from backend.app.services import mapping_llm
            import importlib
            importlib.reload(mapping_llm)

            result = await mapping_llm.process_single_table(job_id=1, table_registry_id=100)

    assert result["status"] == "uncertainty", f"Expected 'uncertainty', got: {result}"
    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: 没有候选类 → unmappable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_single_table_no_candidates():
    """
    SPEC: mapping-service-tests / No candidates path test exists

    GIVEN: search_candidates returns empty list
    WHEN:  process_single_table is called
    THEN:  returns {"status": "unmappable"} and mark_unmappable is called
    """
    mock_table = make_table_registry()

    mock_db_session = AsyncMock()
    mock_db_session.get = AsyncMock(return_value=mock_table)
    mock_db_ctx = AsyncMock()
    mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_mark_unmappable = AsyncMock()

    with patch("backend.app.services.mapping_llm.async_session_factory", return_value=mock_db_ctx), \
         patch("backend.app.services.mapping_llm.search_candidates", return_value=[]), \
         patch("backend.app.services.mapping_llm.mark_unmappable", mock_mark_unmappable):

        from backend.app.services import mapping_llm
        import importlib
        importlib.reload(mapping_llm)

        result = await mapping_llm.process_single_table(job_id=1, table_registry_id=100)

    assert result["status"] == "unmappable", f"Expected 'unmappable', got: {result}"
    mock_mark_unmappable.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: LLM 调用失败 → 触发 fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_single_table_llm_failure_triggers_fallback():
    """
    SPEC: mapping-service-tests / Fallback path test exists

    GIVEN: llm.ainvoke raises an exception
    WHEN:  process_single_table is called
    THEN:  try_fallback_mapping is called with the original error
    """
    mock_table = make_table_registry()
    mock_candidates = [{"uri": "http://example.com#LoanAccount", "label": "LoanAccount"}]

    mock_db_session = AsyncMock()
    mock_db_session.get = AsyncMock(return_value=mock_table)
    mock_db_ctx = AsyncMock()
    mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_db_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_fallback = AsyncMock(return_value={"status": "success_fallback"})

    with patch("backend.app.services.mapping_llm.async_session_factory", return_value=mock_db_ctx), \
         patch("backend.app.services.mapping_llm.search_candidates", return_value=mock_candidates), \
         patch("backend.app.services.mapping_llm.try_fallback_mapping", mock_fallback):

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("DashScope timeout"))

        with patch("backend.app.services.mapping_llm.get_mapping_llm", return_value=mock_llm):
            from backend.app.services import mapping_llm
            import importlib
            importlib.reload(mapping_llm)

            result = await mapping_llm.process_single_table(job_id=1, table_registry_id=100)

    mock_fallback.assert_called_once()
    # The original error should be passed to fallback
    call_kwargs = mock_fallback.call_args
    assert "DashScope timeout" in str(call_kwargs), (
        f"Expected original error to be passed to fallback. call_args: {call_kwargs}"
    )

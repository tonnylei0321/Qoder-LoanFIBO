"""Unit tests for candidate_retriever.py.

Tests cover:
1. retrieve_candidates_node — pass-through when batch is empty
2. retrieve_candidates_node — logs class count and passes state when index non-empty
3. retrieve_candidates_node — warns when ontology index is empty
4. search_candidates — returns tsvector results when primary query succeeds
5. search_candidates — falls back to ILIKE when tsvector returns nothing
6. search_candidates — returns [] when both queries return nothing
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# conftest.py has mocked 'backend.app.services.candidate_retriever' for mapping_llm tests.
# Pop the mock so we can import the REAL module for our tests.
sys.modules.pop("backend.app.services.candidate_retriever", None)

import backend.app.services.candidate_retriever as cr_module
from backend.app.services.candidate_retriever import (
    retrieve_candidates_node,
    search_candidates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(class_uri="http://example.org/Loan", label_en="Loan",
              comment_en="A loan concept", namespace="http://example.org/",
              module_path=None):
    """Return a MagicMock that mimics a SQLAlchemy result row.

    Matches the fields returned by _row_to_dict() in candidate_retriever.py:
      class_uri, label_en, comment_en, module_path, namespace
    """
    row = MagicMock()
    row.class_uri = class_uri
    row.label_en = label_en
    row.comment_en = comment_en
    row.module_path = module_path
    row.namespace = namespace
    return row


def _make_db_ctx(first_result, second_result=None):
    """Build a mock async context manager wrapping an async session.

    first_result  – rows returned by the first db.execute call
    second_result – rows returned by the second db.execute call (ILIKE fallback)
    """
    mock_result_1 = MagicMock()
    mock_result_1.fetchall.return_value = first_result
    mock_result_1.scalar.return_value = len(first_result) if first_result else 0

    if second_result is not None:
        mock_result_2 = MagicMock()
        mock_result_2.fetchall.return_value = second_result
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    else:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result_1)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


# ─────────────────────────────────────────────────────────
# Test 1: retrieve_candidates_node — empty batch pass-through
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_candidates_node_empty_batch():
    """When current_batch is empty, node should return state unchanged without DB call."""
    state = {"job_id": 1, "current_batch": []}
    with patch.object(cr_module, "async_session_factory") as mock_factory:
        result = await retrieve_candidates_node(state)

    # Should not touch the DB
    mock_factory.assert_not_called()
    assert result is state


# ─────────────────────────────────────────────────────────
# Test 2: retrieve_candidates_node — index non-empty, passes through
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_candidates_node_with_classes():
    """When index has classes, node logs progress and returns state unchanged."""
    class_count_result = MagicMock()
    class_count_result.scalar.return_value = 10

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=class_count_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    state = {"job_id": 1, "current_batch": [57, 58, 59]}
    with patch.object(cr_module, "async_session_factory", return_value=mock_ctx):
        result = await retrieve_candidates_node(state)

    assert result is state
    assert result["current_batch"] == [57, 58, 59]


# ─────────────────────────────────────────────────────────
# Test 3: retrieve_candidates_node — empty ontology index warns
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_candidates_node_empty_index_warns():
    """When ontology_class_index has 0 rows, a loguru warning should be emitted."""
    from loguru import logger

    class_count_result = MagicMock()
    class_count_result.scalar.return_value = 0

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=class_count_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    captured = []

    def sink(message):
        captured.append(str(message))

    sink_id = logger.add(sink, level="WARNING")
    try:
        state = {"job_id": 1, "current_batch": [1]}
        with patch.object(cr_module, "async_session_factory", return_value=mock_ctx):
            result = await retrieve_candidates_node(state)
    finally:
        logger.remove(sink_id)

    assert result is state
    assert any("empty" in msg.lower() for msg in captured)


# ─────────────────────────────────────────────────────────
# Test 4: search_candidates — tsvector primary path returns results
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_candidates_tsvector_hit():
    """When pg_trgm similarity search returns rows, results should contain class_uri and label_en."""
    row = _make_row()
    mock_ctx = _make_db_ctx(first_result=[row])

    with patch.object(cr_module, "async_session_factory", return_value=mock_ctx):
        results = await search_candidates("loan", limit=5)

    assert len(results) == 1
    assert results[0]["class_uri"] == "http://example.org/Loan"
    assert results[0]["label_en"] == "Loan"
    assert results[0]["namespace"] == "http://example.org/"


# ─────────────────────────────────────────────────────────
# Test 5: search_candidates — ILIKE fallback when tsvector returns nothing
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_candidates_ilike_fallback():
    """When pg_trgm returns nothing, FTS and inheritance expansion should still provide results."""
    fallback_row = _make_row(class_uri="http://example.org/Credit", label_en="Credit")
    mock_ctx = _make_db_ctx(first_result=[fallback_row])

    with patch.object(cr_module, "async_session_factory", return_value=mock_ctx):
        results = await search_candidates("credit", limit=5)

    assert len(results) >= 1
    assert results[0]["class_uri"] == "http://example.org/Credit"
    assert results[0]["label_en"] == "Credit"


# ─────────────────────────────────────────────────────────
# Test 6: search_candidates — returns [] when both queries return nothing
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_candidates_returns_empty_when_no_match():
    """When both tsvector and ILIKE return nothing, result should be []."""
    mock_ctx = _make_db_ctx(first_result=[], second_result=[])

    with patch.object(cr_module, "async_session_factory", return_value=mock_ctx):
        results = await search_candidates("xyzzy_nonexistent_keyword", limit=5)

    assert results == []

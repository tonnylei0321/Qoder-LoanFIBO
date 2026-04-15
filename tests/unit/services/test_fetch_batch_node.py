"""Unit tests for fetch_batch_node and routing functions in pipeline_orchestrator.py.

Tests cover:
1. route_after_fetch_batch - returns 'retrieve_candidates' when batch is non-empty
2. route_after_fetch_batch - returns 'critic' when batch is empty/absent
3. route_after_mapping - always returns 'fetch_batch'
4. fetch_batch_node - populates current_batch with DB result rows
5. fetch_batch_node - sets current_batch to [] when no pending tables exist
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Remove any cached orchestrator module so we import the real one
sys.modules.pop("backend.app.services.pipeline_orchestrator", None)


# ---------------------------------------------------------------------------
# Import routing functions — these are pure Python, no DB needed
# ---------------------------------------------------------------------------
from backend.app.services.pipeline_orchestrator import (
    route_after_fetch_batch,
    route_after_mapping,
)


# ─────────────────────────────────────────────────────────
# Test 1: route_after_fetch_batch — non-empty batch
# ─────────────────────────────────────────────────────────

def test_route_after_fetch_batch_with_pending_tables():
    """Non-empty current_batch should route to 'retrieve_candidates'."""
    state = {"job_id": 1, "current_batch": [10, 11, 12]}
    result = route_after_fetch_batch(state)
    assert result == "retrieve_candidates"


# ─────────────────────────────────────────────────────────
# Test 2: route_after_fetch_batch — empty batch (no more pending)
# ─────────────────────────────────────────────────────────

def test_route_after_fetch_batch_with_empty_batch():
    """Empty current_batch should route to 'critic'."""
    state = {"job_id": 1, "current_batch": []}
    result = route_after_fetch_batch(state)
    assert result == "critic"


def test_route_after_fetch_batch_missing_key():
    """Missing current_batch key should route to 'critic' (falsy)."""
    state = {"job_id": 1}
    result = route_after_fetch_batch(state)
    assert result == "critic"


# ─────────────────────────────────────────────────────────
# Test 3: route_after_mapping — always returns 'fetch_batch'
# ─────────────────────────────────────────────────────────

def test_route_after_mapping_always_fetch_batch():
    """After mapping_llm_node, always cycle back to fetch_batch."""
    for batch in [[], [1, 2], None]:
        state = {"job_id": 1, "current_batch": batch}
        assert route_after_mapping(state) == "fetch_batch"


# ─────────────────────────────────────────────────────────
# Test 4: fetch_batch_node — returns IDs from DB
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_batch_node_populates_batch():
    """fetch_batch_node should query pending tables and populate current_batch."""
    from backend.app.services.pipeline_orchestrator import fetch_batch_node

    # Fake DB rows: [(57,), (58,), (59,)]
    fake_rows = [(57,), (58,), (59,)]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = fake_rows

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "backend.app.services.pipeline_orchestrator.async_session_factory",
        return_value=mock_ctx,
    ):
        state = {"job_id": 99, "current_batch": []}
        result = await fetch_batch_node(state)

    assert result["current_batch"] == [57, 58, 59]


# ─────────────────────────────────────────────────────────
# Test 5: fetch_batch_node — empty result → empty batch
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_batch_node_empty_when_no_pending():
    """When no pending tables exist, current_batch should be set to []."""
    from backend.app.services.pipeline_orchestrator import fetch_batch_node

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []  # no rows

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "backend.app.services.pipeline_orchestrator.async_session_factory",
        return_value=mock_ctx,
    ):
        state = {"job_id": 99, "current_batch": [1, 2]}  # old batch should be replaced
        result = await fetch_batch_node(state)

    assert result["current_batch"] == []

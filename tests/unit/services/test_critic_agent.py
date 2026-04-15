"""Unit tests for critic_agent.py.

Tests cover:
1. parse_critic_response - valid JSON with overall_status
2. parse_critic_response - JSON in markdown code block
3. parse_critic_response - invalid JSON returns None
4. parse_critic_response - missing overall_status returns None
5. critic_node - no pending mappings returns state unchanged
6. review_single_mapping - LLM approved path returns 'approved'
"""
import json
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Remove mock of critic_agent if previously set (shouldn't be, but safety net)
sys.modules.pop("backend.app.services.critic_agent", None)

import backend.app.services.critic_agent as critic_agent_module
from backend.app.services.critic_agent import (
    parse_critic_response,
    critic_node,
    review_single_mapping,
)

# ─────────────────────────────────────────────────────────
# Sample data
# ─────────────────────────────────────────────────────────

VALID_CRITIC_RESPONSE = json.dumps({
    "overall_status": "approved",
    "issues": [],
    "summary": "Mapping quality is acceptable."
})

NEEDS_REVISION_RESPONSE = json.dumps({
    "overall_status": "needs_revision",
    "issues": [
        {
            "issue_type": "semantic_mismatch",
            "severity": "P1",
            "is_must_fix": True,
            "issue_description": "Mapped class does not match table semantics",
            "suggested_fix": "Consider using fibo:Loan instead"
        }
    ],
    "summary": "Semantic issues found."
})

MARKDOWN_WRAPPED_RESPONSE = f"```json\n{VALID_CRITIC_RESPONSE}\n```"


# ─────────────────────────────────────────────────────────
# Test 1: parse_critic_response - valid plain JSON
# ─────────────────────────────────────────────────────────

def test_parse_critic_response_valid_json_returns_dict():
    """Valid JSON with required fields should return a dict."""
    result = parse_critic_response(VALID_CRITIC_RESPONSE)

    assert result is not None, "Expected non-None for valid JSON"
    assert result["overall_status"] == "approved"
    assert isinstance(result["issues"], list)


# ─────────────────────────────────────────────────────────
# Test 2: parse_critic_response - JSON in markdown code block
# ─────────────────────────────────────────────────────────

def test_parse_critic_response_extracts_json_from_markdown():
    """JSON wrapped in ```json ... ``` should be extracted and parsed."""
    result = parse_critic_response(MARKDOWN_WRAPPED_RESPONSE)

    assert result is not None, "Expected non-None for markdown-wrapped JSON"
    assert result["overall_status"] == "approved"


# ─────────────────────────────────────────────────────────
# Test 3: parse_critic_response - invalid JSON returns None
# ─────────────────────────────────────────────────────────

def test_parse_critic_response_invalid_json_returns_none():
    """Non-JSON string should return None without raising."""
    result = parse_critic_response("This is definitely not JSON!!!")

    assert result is None, "Expected None for invalid JSON"


# ─────────────────────────────────────────────────────────
# Test 4: parse_critic_response - missing overall_status returns None
# ─────────────────────────────────────────────────────────

def test_parse_critic_response_missing_overall_status_returns_none():
    """Valid JSON without 'overall_status' should return None."""
    bad_json = json.dumps({"issues": [], "summary": "Missing required field"})
    result = parse_critic_response(bad_json)

    assert result is None, "Expected None when 'overall_status' is missing"


# ─────────────────────────────────────────────────────────
# Test 5: critic_node - no pending mappings returns state unchanged
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_critic_node_no_pending_mappings_returns_state():
    """critic_node should return state unchanged when no pending mappings exist."""
    # Mock DB: scalars().all() returns empty list (no pending mappings)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_execute_result

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_cm.__aexit__.return_value = None

    state = {"job_id": 42, "revision_round": 0, "error": None}

    with patch("backend.app.services.critic_agent.async_session_factory", return_value=mock_cm):
        result = await critic_node(state)

    assert result["job_id"] == 42, "state should be returned unchanged"
    assert result.get("error") is None


# ─────────────────────────────────────────────────────────
# Test 6: review_single_mapping - LLM approved path
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_single_mapping_approved_path():
    """When LLM returns approved JSON, review_single_mapping should return 'approved'."""
    # Build mock table_mapping
    mock_table_mapping = MagicMock()
    mock_table_mapping.database_name = "loan_db"
    mock_table_mapping.table_name = "loan_application"
    mock_table_mapping.fibo_class_uri = "http://spec.edmcouncil.org/fibo/ont#Loan"
    mock_table_mapping.id = 1
    mock_table_mapping.job_id = 1

    # Build mock table_registry
    mock_table_registry = MagicMock()
    mock_table_registry.raw_ddl = "CREATE TABLE loan_application (id INT);"
    mock_table_registry.parsed_fields = []

    # Build mock class_info
    mock_class_info = MagicMock()
    mock_class_info.label_zh = "贷款"
    mock_class_info.comment_zh = "表示贷款的概念"

    # Mock DB returns
    def make_execute_result(scalar_value=None, scalars_list=None):
        result = MagicMock()
        result.scalar_one_or_none.return_value = scalar_value
        if scalars_list is not None:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = scalars_list
            result.scalars.return_value = scalars_mock
        return result

    mock_db = AsyncMock()
    # DB calls in order: table_registry, field_mappings, class_info
    mock_db.execute.side_effect = [
        make_execute_result(scalar_value=mock_table_registry),  # table_registry
        make_execute_result(scalars_list=[]),                     # field_mappings
        make_execute_result(scalar_value=mock_class_info),        # class_info
    ]
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = VALID_CRITIC_RESPONSE
    mock_llm_response.usage.total_tokens = 100

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch("backend.app.services.critic_agent.get_critic_llm", return_value=mock_llm):
        with patch("backend.app.services.critic_agent.get_properties_for_class", new_callable=AsyncMock, return_value=[]):
            with patch("backend.app.services.critic_agent.save_review_results", new_callable=AsyncMock) as mock_save:
                result = await review_single_mapping(mock_db, mock_table_mapping, review_round=1)

    assert result == "approved", f"Expected 'approved', got '{result}'"
    mock_save.assert_called_once()

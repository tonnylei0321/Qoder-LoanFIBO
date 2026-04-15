"""Unit tests for ttl_indexer.py.

Tests cover:
1. calculate_file_md5 - deterministic MD5 hash for a file
2. extract_namespace - URI namespace extraction (#-based and /-based)
3. parse_ttl_file - Graph.parse + SPARQL query result extraction (mock Graph)
4. index_ttl_node - error state when TTL dir missing
5. index_ttl_node - idempotency (skip when file already indexed)
"""
import os
import sys
import pytest
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call

# conftest.py has mocked 'backend.app.services.ttl_indexer' for use by mapping_llm tests.
# We remove that mock here so we can import the REAL module for our tests.
sys.modules.pop("backend.app.services.ttl_indexer", None)

import backend.app.services.ttl_indexer as ttl_indexer_module
from backend.app.services.ttl_indexer import (
    calculate_file_md5,
    extract_namespace,
    parse_ttl_file,
    index_ttl_node,
)

# ─────────────────────────────────────────────────────────
# Test 1: calculate_file_md5
# ─────────────────────────────────────────────────────────

def test_calculate_file_md5_deterministic(tmp_path):
    """Same file content should always return the same 32-char hex MD5."""
    content = b"@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    f = tmp_path / "test.ttl"
    f.write_bytes(content)

    result1 = calculate_file_md5(f)
    result2 = calculate_file_md5(f)

    assert len(result1) == 32, f"MD5 should be 32 hex chars, got {len(result1)}"
    assert all(c in "0123456789abcdef" for c in result1), "MD5 should be hex"
    assert result1 == result2, "MD5 should be deterministic"

    # Different content should give different hash
    f2 = tmp_path / "different.ttl"
    f2.write_bytes(b"different content")
    assert calculate_file_md5(f2) != result1


# ─────────────────────────────────────────────────────────
# Test 2: extract_namespace - two URI formats
# ─────────────────────────────────────────────────────────

def test_extract_namespace_hash_separator():
    """URI with # should return everything up to and including #."""
    uri = "http://spec.edmcouncil.org/fibo/ontology#LoanClass"
    result = extract_namespace(uri)
    assert result == "http://spec.edmcouncil.org/fibo/ontology#"


def test_extract_namespace_slash_separator():
    """URI with / (no #) should return everything up to and including last /."""
    uri = "http://example.org/ontology/LoanApplication"
    result = extract_namespace(uri)
    assert result == "http://example.org/ontology/"


# ─────────────────────────────────────────────────────────
# Test 3: parse_ttl_file — mock Graph, verify call chain and output shape
# ─────────────────────────────────────────────────────────

def test_parse_ttl_file_returns_classes_and_properties(tmp_path):
    """parse_ttl_file should call Graph.parse and return (classes, properties) lists."""
    dummy_ttl = tmp_path / "fibo.ttl"
    dummy_ttl.write_text("# minimal stub\n", encoding="utf-8")

    # Build mock row objects for SPARQL class query result
    class MockClassRow:
        def __init__(self, uri, label_zh, label_en):
            self.__dict__['class'] = MagicMock()
            self.__dict__['class'].__str__ = lambda s: uri
            self.label_zh = MagicMock() if label_zh else None
            self.label_en = MagicMock() if label_en else None
            self.comment_zh = None
            self.comment_en = None
            self.parent = None
            self._uri = uri

        def __getitem__(self, key):
            if key == 'class':
                m = MagicMock()
                m.__str__ = lambda s: self._uri
                return m
            return None

    # Build a mock Graph instance
    mock_graph = MagicMock()
    mock_graph.parse.return_value = None
    mock_graph.bind.return_value = None

    # Two classes, zero properties
    class_row1 = MagicMock()
    class_row1.__getitem__ = lambda s, k: MagicMock(__str__=lambda x: "http://example.org/ont#Loan")
    class_row1.label_zh = MagicMock(__str__=lambda x: "贷款")
    class_row1.label_en = MagicMock(__str__=lambda x: "Loan")
    class_row1.comment_zh = None
    class_row1.comment_en = None
    class_row1.parent = None

    class_row2 = MagicMock()
    class_row2.__getitem__ = lambda s, k: MagicMock(__str__=lambda x: "http://example.org/ont#Borrower")
    class_row2.label_zh = MagicMock(__str__=lambda x: "借款人")
    class_row2.label_en = MagicMock(__str__=lambda x: "Borrower")
    class_row2.comment_zh = None
    class_row2.comment_en = None
    class_row2.parent = None

    mock_graph.query.side_effect = [
        [class_row1, class_row2],  # QUERY_CLASSES result
        [],                         # QUERY_PROPERTIES result (empty)
    ]

    # Patch Graph class in the ttl_indexer module namespace
    with patch("backend.app.services.ttl_indexer.Graph", return_value=mock_graph):
        classes, properties = parse_ttl_file(str(dummy_ttl))

    assert isinstance(classes, list), "classes should be a list"
    assert isinstance(properties, list), "properties should be a list"
    assert len(classes) == 2, f"Expected 2 classes, got {len(classes)}"
    assert len(properties) == 0, "Expected 0 properties"

    # Verify Graph.parse was called with the file path
    mock_graph.parse.assert_called_once_with(str(dummy_ttl), format="turtle")

    # Each class entry should have 'class_uri' key
    for cls in classes:
        assert "class_uri" in cls, f"class entry missing 'class_uri': {cls}"


# ─────────────────────────────────────────────────────────
# Test 4: index_ttl_node — error state when TTL dir missing
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_index_ttl_node_missing_dir_returns_error_state():
    """index_ttl_node should set state['error'] when TTL dir does not exist."""
    state = {"job_id": 1, "error": None}

    with patch.dict(os.environ, {"TTL_DIR": "/tmp/__nonexistent_ttl_dir_xyz__"}):
        result = await index_ttl_node(state)

    assert result["error"] is not None, "Expected state['error'] to be set"
    assert "not found" in result["error"].lower() or "__nonexistent" in result["error"]


# ─────────────────────────────────────────────────────────
# Test 5: index_ttl_node — idempotency (skip when already indexed)
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_index_ttl_node_skips_parse_when_already_indexed(tmp_path):
    """When scalar_one_or_none returns a record, parse_ttl_file should NOT be called."""
    # Create a minimal TTL file
    ttl_file = tmp_path / "fibo.ttl"
    ttl_file.write_text("# stub\n", encoding="utf-8")

    # Mock DB: table already indexed (scalar_one_or_none returns non-None)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = MagicMock()

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_execute_result

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_cm.__aexit__.return_value = None

    state = {"job_id": 1, "error": None}

    with patch.dict(os.environ, {"TTL_DIR": str(tmp_path)}):
        with patch("backend.app.services.ttl_indexer.async_session_factory", return_value=mock_cm):
            with patch("backend.app.services.ttl_indexer.parse_ttl_file") as mock_parse:
                result = await index_ttl_node(state)

    mock_parse.assert_not_called()
    assert result.get("error") is None, f"Unexpected error: {result.get('error')}"

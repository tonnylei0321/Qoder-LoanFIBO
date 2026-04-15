"""Unit tests for ddl_parser.py.

Tests cover:
1. sqlglot primary parse path (standard CREATE TABLE)
2. Field-level extraction (field_name, field_type, is_primary_key)
3. regex fallback path (when sqlglot raises)
4. parse_ddl_node returns error state when DDL dir missing
5. DB idempotency: same table second time skips insert
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call

import backend.app.services.ddl_parser as ddl_parser_module
from backend.app.services.ddl_parser import (
    parse_ddl_content,
    parse_ddl_regex,
    parse_ddl_node,
)

# ─────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────

SIMPLE_DDL = """
CREATE TABLE `loan_application` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `applicant_name` VARCHAR(100) NOT NULL COMMENT '申请人姓名',
  `loan_amount` DECIMAL(18,2) COMMENT '贷款金额',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB COMMENT='贷款申请表';
"""

REGEX_FRIENDLY_DDL = """
CREATE TABLE `borrower_info` (
  `id` INT NOT NULL COMMENT '主键',
  `credit_score` INT COMMENT '信用评分'
) ENGINE=InnoDB;
"""


# ─────────────────────────────────────────────────────────
# Test 1: sqlglot primary parse path
# ─────────────────────────────────────────────────────────

def test_parse_ddl_content_sqlglot_primary_path():
    """sqlglot should parse a standard CREATE TABLE and return a table info dict."""
    tables = parse_ddl_content(SIMPLE_DDL, "loan_db")

    assert len(tables) == 1, f"Expected 1 table, got {len(tables)}"
    table = tables[0]
    assert table["table_name"] == "loan_application"
    assert table["database_name"] == "loan_db"
    assert isinstance(table["parsed_fields"], list)
    assert len(table["parsed_fields"]) > 0
    assert table["raw_ddl"] is not None


# ─────────────────────────────────────────────────────────
# Test 2: Field-level info extraction
# ─────────────────────────────────────────────────────────

def test_parse_ddl_content_field_structure():
    """Each parsed field must contain required keys."""
    tables = parse_ddl_content(SIMPLE_DDL, "loan_db")
    assert len(tables) == 1
    fields = tables[0]["parsed_fields"]

    required_keys = {"field_name", "field_type", "is_nullable", "is_primary_key"}
    for field in fields:
        assert required_keys.issubset(field.keys()), (
            f"Field missing keys: {required_keys - field.keys()}, field={field}"
        )

    # 'id' should be primary key
    id_field = next((f for f in fields if f["field_name"] == "id"), None)
    assert id_field is not None
    assert id_field["is_primary_key"] is True


# ─────────────────────────────────────────────────────────
# Test 3: regex fallback when sqlglot raises
# ─────────────────────────────────────────────────────────

def test_parse_ddl_content_falls_back_to_regex_when_sqlglot_fails():
    """When sqlglot.parse raises, parse_ddl_content should fall back to regex."""
    with patch("backend.app.services.ddl_parser.sqlglot.parse", side_effect=Exception("sqlglot exploded")):
        tables = parse_ddl_content(REGEX_FRIENDLY_DDL, "borrow_db")

    assert len(tables) >= 1, "Regex fallback should return at least one table"
    table = tables[0]
    assert table["table_name"] == "borrower_info"
    assert table["database_name"] == "borrow_db"
    # Regex path parses fields that have COMMENT
    commented_fields = [f for f in table["parsed_fields"] if f.get("comment")]
    assert len(commented_fields) >= 1, "Regex should extract at least 1 commented field"


# ─────────────────────────────────────────────────────────
# Test 4: parse_ddl_node returns error state when dir missing
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_ddl_node_missing_dir_returns_error_state():
    """parse_ddl_node should set state['error'] and not raise when DDL dir is missing."""
    state = {"job_id": 1, "error": None}

    with patch.dict(os.environ, {"DDL_DIR": "/tmp/__nonexistent_ddl_dir_xyz__"}):
        result = await parse_ddl_node(state)

    assert result["error"] is not None, "Expected state['error'] to be set"
    assert "not found" in result["error"].lower() or "/tmp/__nonexistent_ddl_dir_xyz__" in result["error"]


# ─────────────────────────────────────────────────────────
# Test 5: DB idempotency — same table skips insert
# ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_ddl_node_skips_insert_for_existing_table(tmp_path):
    """When scalar_one_or_none returns a record, db.add should NOT be called."""
    # Create a temp SQL file
    sql_file = tmp_path / "test_db.sql"
    sql_file.write_text(SIMPLE_DDL, encoding="utf-8")

    # Build mock DB session that reports table already exists
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = MagicMock()  # table exists

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_execute_result
    mock_db.add = MagicMock()

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_cm.__aexit__.return_value = None

    state = {"job_id": 1, "error": None}

    with patch.dict(os.environ, {"DDL_DIR": str(tmp_path)}):
        with patch("backend.app.services.ddl_parser.async_session_factory", return_value=mock_cm):
            # Also mock update_job_stats to avoid second DB call complexity
            with patch("backend.app.services.ddl_parser.update_job_stats", new_callable=AsyncMock):
                result = await parse_ddl_node(state)

    # db.add should NOT have been called since table already exists
    mock_db.add.assert_not_called()
    assert result.get("error") is None, f"Unexpected error: {result.get('error')}"

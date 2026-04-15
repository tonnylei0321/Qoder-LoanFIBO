"""Integration tests for parse_ddl_node.

Prerequisites:
    docker-compose up -d postgres

These tests connect to a real PostgreSQL instance and verify that
parse_ddl_node correctly writes records into table_registry.
Each test is automatically rolled back to keep the DB clean.
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy import text, select

pytestmark = pytest.mark.integration

# Import real modules (no mocks at this layer)
from backend.app.services.ddl_parser import parse_ddl_node
from tests.integration.conftest import make_session_factory


# ---------------------------------------------------------------------------
# Test 1: parse_ddl_node inserts a record into table_registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_ddl_inserts_table_registry(pg_session, ddl_tmp_dir, monkeypatch):
    """
    GIVEN: A SQL file with 1 CREATE TABLE statement in DDL_DIR
    WHEN:  parse_ddl_node is called
    THEN:  table_registry contains the inserted record with non-empty parsed_fields
           and the primary key field is correctly flagged
    """
    monkeypatch.setenv("DDL_DIR", str(ddl_tmp_dir))
    monkeypatch.setattr(
        "backend.app.services.ddl_parser.async_session_factory",
        make_session_factory(pg_session),
    )
    # Patch update_job_stats to avoid second session_factory call
    from unittest.mock import AsyncMock
    monkeypatch.setattr(
        "backend.app.services.ddl_parser.update_job_stats",
        AsyncMock(),
    )

    state = {"job_id": 9999, "error": None}
    result = await parse_ddl_node(state)

    assert result.get("error") is None, f"parse_ddl_node returned error: {result.get('error')}"

    # Verify DB record
    rows = await pg_session.execute(
        text("SELECT table_name, database_name, parsed_fields FROM table_registry WHERE database_name = 'test_db'")
    )
    records = rows.fetchall()

    assert len(records) == 1, f"Expected 1 record in table_registry, got {len(records)}"
    table_name, database_name, parsed_fields = records[0]
    assert table_name == "loan_account"
    assert database_name == "test_db"
    assert isinstance(parsed_fields, list) and len(parsed_fields) > 0, (
        f"parsed_fields should be a non-empty list, got: {parsed_fields}"
    )

    # Verify primary key detection
    id_field = next((f for f in parsed_fields if f.get("field_name") == "id"), None)
    assert id_field is not None, "Field 'id' not found in parsed_fields"
    assert id_field.get("is_primary_key") is True, (
        f"Field 'id' should be marked as primary key. Got: {id_field}"
    )


# ---------------------------------------------------------------------------
# Test 2: parse_ddl_node is idempotent (UNIQUE constraint respected)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_ddl_idempotent(pg_session, ddl_tmp_dir, monkeypatch):
    """
    GIVEN: A SQL file with 1 CREATE TABLE statement
    WHEN:  parse_ddl_node is called twice with the same file
    THEN:  table_registry has exactly 1 record (duplicate silently skipped)
           and no error is raised
    """
    monkeypatch.setenv("DDL_DIR", str(ddl_tmp_dir))
    monkeypatch.setattr(
        "backend.app.services.ddl_parser.async_session_factory",
        make_session_factory(pg_session),
    )
    from unittest.mock import AsyncMock
    monkeypatch.setattr(
        "backend.app.services.ddl_parser.update_job_stats",
        AsyncMock(),
    )

    state = {"job_id": 9999, "error": None}

    # First call
    result1 = await parse_ddl_node(state)
    assert result1.get("error") is None

    # Second call — same file, same table
    result2 = await parse_ddl_node(state)
    assert result2.get("error") is None

    # Should still have exactly 1 record
    rows = await pg_session.execute(
        text("SELECT COUNT(*) FROM table_registry WHERE database_name = 'test_db'")
    )
    count = rows.scalar()
    assert count == 1, (
        f"Expected exactly 1 record after two identical calls, got {count}"
    )

"""Integration tests for index_ttl_node.

Prerequisites:
    docker-compose up -d postgres

These tests connect to a real PostgreSQL instance and verify that
index_ttl_node correctly parses a real TTL file and writes ontology
records into ontology_class_index / ontology_property_index.
Each test is automatically rolled back to keep the DB clean.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

from backend.app.services.ttl_indexer import index_ttl_node
from tests.integration.conftest import make_session_factory


# Expected classes from sasac_gov_sample.ttl
EXPECTED_CLASS_URIS = [
    "https://ontology.mof.gov.cn/sasac/capital/CapitalTransaction",
    "https://ontology.mof.gov.cn/sasac/capital/CapitalInflow",
    "https://ontology.mof.gov.cn/sasac/enterprise/StateOwnedEnterprise",
    "https://ontology.mof.gov.cn/sasac/finance/Voucher",
]


# ---------------------------------------------------------------------------
# Test 1: index_ttl_node inserts classes into ontology_class_index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_ttl_inserts_classes(pg_session, ttl_tmp_dir, monkeypatch):
    """
    GIVEN: A TTL file with owl:Class definitions in TTL_DIR
    WHEN:  index_ttl_node is called
    THEN:  ontology_class_index contains records with non-null class_uri values,
           and at least the expected SASAC classes are present
    """
    monkeypatch.setenv("TTL_DIR", str(ttl_tmp_dir))
    monkeypatch.setattr(
        "backend.app.services.ttl_indexer.async_session_factory",
        make_session_factory(pg_session),
    )

    state = {"job_id": 9999, "error": None}
    result = await index_ttl_node(state)

    assert result.get("error") is None, (
        f"index_ttl_node returned error: {result.get('error')}"
    )

    # Verify class records
    rows = await pg_session.execute(
        text("SELECT class_uri, label_en FROM ontology_class_index")
    )
    records = rows.fetchall()

    assert len(records) > 0, "Expected at least 1 class in ontology_class_index"

    inserted_uris = {r[0] for r in records}
    for expected_uri in EXPECTED_CLASS_URIS:
        assert expected_uri in inserted_uris, (
            f"Expected class URI not found in ontology_class_index: {expected_uri}\n"
            f"Inserted URIs: {sorted(inserted_uris)}"
        )

    # Verify property records
    prop_rows = await pg_session.execute(
        text("SELECT COUNT(*) FROM ontology_property_index")
    )
    prop_count = prop_rows.scalar()
    assert prop_count > 0, "Expected at least 1 property in ontology_property_index"

    # Verify index meta was written
    meta_rows = await pg_session.execute(
        text("SELECT file_name, class_count, property_count FROM ontology_index_meta")
    )
    metas = meta_rows.fetchall()
    assert len(metas) == 1, f"Expected 1 index_meta record, got {len(metas)}"
    file_name, class_count, property_count = metas[0]
    assert file_name == "sasac_gov_sample.ttl"
    assert class_count > 0
    assert property_count > 0


# ---------------------------------------------------------------------------
# Test 2: index_ttl_node is idempotent (already-indexed file is skipped)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_ttl_idempotent(pg_session, ttl_tmp_dir, monkeypatch):
    """
    GIVEN: A TTL file that has already been indexed (same MD5)
    WHEN:  index_ttl_node is called a second time
    THEN:  No exception is raised, and the class count in the DB remains the same
    """
    monkeypatch.setenv("TTL_DIR", str(ttl_tmp_dir))
    monkeypatch.setattr(
        "backend.app.services.ttl_indexer.async_session_factory",
        make_session_factory(pg_session),
    )

    state = {"job_id": 9999, "error": None}

    # First call — indexes the file
    result1 = await index_ttl_node(state)
    assert result1.get("error") is None

    count_after_first = (
        await pg_session.execute(text("SELECT COUNT(*) FROM ontology_class_index"))
    ).scalar()

    # Second call — same file, same MD5 → should be skipped
    result2 = await index_ttl_node(state)
    assert result2.get("error") is None

    count_after_second = (
        await pg_session.execute(text("SELECT COUNT(*) FROM ontology_class_index"))
    ).scalar()

    assert count_after_second == count_after_first, (
        f"Second call should not insert duplicate classes. "
        f"Before: {count_after_first}, After: {count_after_second}"
    )

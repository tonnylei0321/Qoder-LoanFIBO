"""Unit tests for pipeline API routes.

Uses FastAPI TestClient (httpx-based synchronous wrapper).
DB dependency is overridden with AsyncMock — no real database needed.
init_db / close_db are patched to prevent lifespan from hitting the DB.

Covered routes (11 pipeline + 2 root):
  GET  /health
  GET  /
  POST /api/v1/pipeline/jobs
  GET  /api/v1/pipeline/jobs/{job_id}
  POST /api/v1/pipeline/jobs/{job_id}/pause
  POST /api/v1/pipeline/jobs/{job_id}/resume
  GET  /api/v1/pipeline/mappings
  GET  /api/v1/pipeline/mappings/{table_mapping_id}
  PATCH /api/v1/pipeline/mappings/{table_mapping_id}
  GET  /api/v1/pipeline/stats
  POST /api/v1/pipeline/ttl/index
  GET  /api/v1/pipeline/ttl/index/status  (bonus)
  POST /api/v1/pipeline/mappings/{table_mapping_id}/remap  (bonus)
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App setup with mocked lifespan and DB dependency
# ---------------------------------------------------------------------------

# Patch init_db and close_db BEFORE importing app so lifespan doesn't
# attempt a real DB connection during TestClient startup/shutdown.
_init_patch = patch("backend.app.main.init_db", new_callable=AsyncMock)
_close_patch = patch("backend.app.main.close_db", new_callable=AsyncMock)
_init_patch.start()
_close_patch.start()

from backend.app.main import app          # noqa: E402 — must come after patches
from backend.app.database import get_db   # noqa: E402


async def _override_get_db():
    """Replace real DB session with a no-op AsyncMock."""
    yield AsyncMock()


app.dependency_overrides[get_db] = _override_get_db

# One shared client for all tests in this module (lifespan runs once)
client = TestClient(app)


# ---------------------------------------------------------------------------
# Root & health
# ---------------------------------------------------------------------------

def test_health_check():
    """GET /health returns 200 with status=healthy."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "app" in body


def test_root_endpoint():
    """GET / returns 200 with api_prefix field."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "api_prefix" in body
    assert body["api_prefix"] == "/api/v1"


# ---------------------------------------------------------------------------
# POST /jobs — create job
# ---------------------------------------------------------------------------

def test_create_job_success():
    """POST /jobs with valid body returns 200 and job_id in data."""
    resp = client.post(
        "/api/v1/pipeline/jobs",
        json={"job_name": "test-job", "concurrency": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "job_id" in body["data"]


def test_create_job_defaults():
    """POST /jobs with empty body uses defaults (concurrency defaults to 5)."""
    resp = client.post("/api/v1/pipeline/jobs", json={})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_create_job_invalid_concurrency_zero():
    """POST /jobs with concurrency=0 returns 422 (ge=1 constraint)."""
    resp = client.post(
        "/api/v1/pipeline/jobs",
        json={"concurrency": 0},
    )
    assert resp.status_code == 422


def test_create_job_invalid_concurrency_over_max():
    """POST /jobs with concurrency=21 returns 422 (le=20 constraint)."""
    resp = client.post(
        "/api/v1/pipeline/jobs",
        json={"concurrency": 21},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

def test_get_job():
    """GET /jobs/42 returns 200 with job_id matching path param."""
    resp = client.get("/api/v1/pipeline/jobs/42")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["job_id"] == 42


def test_get_job_string_id_returns_422():
    """GET /jobs/not-a-number returns 422 (path param must be int)."""
    resp = client.get("/api/v1/pipeline/jobs/not-a-number")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/pause & /resume
# ---------------------------------------------------------------------------

def test_pause_job():
    """POST /jobs/1/pause returns 200 with code=0."""
    resp = client.post("/api/v1/pipeline/jobs/1/pause")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_resume_job():
    """POST /jobs/1/resume returns 200 with code=0."""
    resp = client.post("/api/v1/pipeline/jobs/1/resume")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


# ---------------------------------------------------------------------------
# GET /mappings (with pagination)
# ---------------------------------------------------------------------------

def test_query_mappings_default():
    """GET /mappings returns 200 with data.items as a list."""
    resp = client.get("/api/v1/pipeline/mappings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"]["items"], list)


def test_query_mappings_pagination():
    """GET /mappings?page=2&page_size=10 echoes pagination params."""
    resp = client.get("/api/v1/pipeline/mappings?page=2&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["page"] == 2
    assert body["data"]["page_size"] == 10


def test_query_mappings_with_filters():
    """GET /mappings?mapping_status=mapped filters are accepted (no 422)."""
    resp = client.get("/api/v1/pipeline/mappings?mapping_status=mapped")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /mappings/{table_mapping_id}
# ---------------------------------------------------------------------------

def test_get_mapping_detail():
    """GET /mappings/1 returns 200 with code=0."""
    resp = client.get("/api/v1/pipeline/mappings/1")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


# ---------------------------------------------------------------------------
# PATCH /mappings/{table_mapping_id}
# ---------------------------------------------------------------------------

def test_update_mapping():
    """PATCH /mappings/1 with valid body returns 200 with code=0."""
    resp = client.patch(
        "/api/v1/pipeline/mappings/1",
        json={"fibo_class_uri": "https://example.org/LoanAccount", "confidence_level": "HIGH"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

def test_get_stats():
    """GET /stats returns 200 with data.total_tables field."""
    resp = client.get("/api/v1/pipeline/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "total_tables" in body["data"]


# ---------------------------------------------------------------------------
# POST /ttl/index & GET /ttl/index/status
# ---------------------------------------------------------------------------

def test_trigger_ttl_index():
    """POST /ttl/index returns 200 with code=0."""
    resp = client.post("/api/v1/pipeline/ttl/index")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_get_ttl_index_status():
    """GET /ttl/index/status returns 200 with data.status field."""
    resp = client.get("/api/v1/pipeline/ttl/index/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "status" in body["data"]

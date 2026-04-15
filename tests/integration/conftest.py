"""Integration test configuration.

Fixtures connect to real PostgreSQL (docker-compose port 5434).
Each test runs inside a transaction that is rolled back after the test,
so the DB state is clean for every test.

Prerequisites:
    docker-compose up -d postgres
"""
import contextlib
import os
import shutil
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = (
    "postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo"
)


# ---------------------------------------------------------------------------
# pg_session — per-test transactional isolation with savepoint
# Creates a fresh engine per test to avoid cross-loop asyncpg issues.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pg_session():
    """Provide an AsyncSession that is automatically rolled back after each test.

    A fresh engine is created per test (function scope) to avoid asyncpg
    cross-event-loop errors that occur when sharing a session-scoped engine.

    Strategy:
    1. Open a connection and BEGIN an outer transaction (never committed).
    2. Bind AsyncSession to that connection.
    3. Start a SAVEPOINT so that node-level commit() releases the savepoint
       without touching the outer transaction.
    4. After the test, ROLLBACK the outer transaction — all writes are undone.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Check connectivity
    try:
        async with engine.connect() as probe:
            await probe.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"PostgreSQL not reachable at localhost:5434 — "
            f"run `docker-compose up -d postgres` first. ({exc})"
        )

    async with engine.connect() as conn:
        await conn.begin()  # outer transaction — never committed

        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        async with session_factory() as session:
            # Create a savepoint; node-level commit() will release it,
            # keeping all writes inside the outer transaction.
            await session.begin_nested()
            yield session

        await conn.rollback()  # undo all writes — DB stays clean

    await engine.dispose()


# ---------------------------------------------------------------------------
# make_session_factory — wraps pg_session into a context-manager factory
# ---------------------------------------------------------------------------

def make_session_factory(session):
    """Return a callable that acts like async_session_factory but yields `session`."""

    @contextlib.asynccontextmanager
    async def _factory():
        # Refresh savepoint before each factory call so commit() doesn't fail
        await session.begin_nested()
        yield session

    return _factory


# ---------------------------------------------------------------------------
# ddl_tmp_dir — minimal SQL fixture for parse_ddl_node tests
# ---------------------------------------------------------------------------

TEST_DDL_SQL = """\
CREATE TABLE `loan_account` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `account_no` VARCHAR(64) NOT NULL COMMENT '借款账户编号',
  `customer_id` BIGINT NOT NULL COMMENT '客户ID',
  `loan_amount` DECIMAL(18,2) NOT NULL COMMENT '贷款金额',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '账户状态',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='贷款账户表';
"""


@pytest.fixture
def ddl_tmp_dir(tmp_path):
    """Create a temp directory with a single test SQL file."""
    sql_file = tmp_path / "test_db.sql"
    sql_file.write_text(TEST_DDL_SQL, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# ttl_tmp_dir — copy real TTL file for index_ttl_node tests
# ---------------------------------------------------------------------------

_REAL_TTL_PATH = (
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "data", "ttl", "sasac_gov_sample.ttl",
    )
)


@pytest.fixture
def ttl_tmp_dir(tmp_path):
    """Create a temp directory with a copy of the real TTL sample file."""
    src = os.path.abspath(_REAL_TTL_PATH)
    dst = tmp_path / "sasac_gov_sample.ttl"
    shutil.copy(src, dst)
    return tmp_path

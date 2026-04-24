"""Unit test configuration — module-level mocks for all unit tests.

Stubs out heavy external dependencies (LangChain, rdflib, asyncpg, etc.)
so unit tests run without a real DB, LLM, or RDF store.

IMPORTANT: We do NOT mock sqlalchemy or ORM models.
Real sqlalchemy select() + real model column definitions are needed
so that query construction works in service/API code under test.

Instead, we mock backend.app.database with a real DeclarativeBase
so models have proper column definitions, but no real DB engine is created.

Scope: tests/unit/ only. Integration tests should NOT inherit these mocks.
"""
import sys
import types
from unittest.mock import MagicMock, AsyncMock

# ---------------------------------------------------------------------------
# Stub out modules that require real infrastructure BEFORE importing project code
# ---------------------------------------------------------------------------

# langchain.schema → langchain_core.messages in newer versions
_langchain_schema = MagicMock()
_langchain_schema.SystemMessage = MagicMock
_langchain_schema.HumanMessage = MagicMock
sys.modules.setdefault("langchain.schema", _langchain_schema)

# langchain_openai
_langchain_openai = MagicMock()
sys.modules.setdefault("langchain_openai", _langchain_openai)

# langgraph (pipeline_state)
sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())

# rdflib (ttl_indexer)
_rdflib = MagicMock()
_rdflib_namespace = MagicMock()
_rdflib_namespace.XSD = MagicMock()
_rdflib_namespace.RDF = MagicMock()
_rdflib_namespace.RDFS = MagicMock()
_rdflib_namespace.OWL = MagicMock()
sys.modules.setdefault("rdflib", _rdflib)
sys.modules.setdefault("rdflib.namespace", _rdflib_namespace)
sys.modules.setdefault("rdflib.term", MagicMock())
sys.modules.setdefault("rdflib.graph", MagicMock())

# asyncpg (database)
sys.modules.setdefault("asyncpg", MagicMock())

# ---------------------------------------------------------------------------
# Mock backend.app.database with a REAL DeclarativeBase
#
# This is the key fix: models inherit from Base, and when select(Model.col)
# is called, SQLAlchemy needs real column descriptors.  By providing a real
# DeclarativeBase (instead of MagicMock), all ORM models get proper column
# definitions without needing a real database connection.
# ---------------------------------------------------------------------------

from sqlalchemy.orm import DeclarativeBase


class _TestBase(DeclarativeBase):
    """Real DeclarativeBase for unit tests — no engine required."""
    pass


# Build a lightweight module that looks like backend.app.database
_db_module = types.ModuleType("backend.app.database")
_db_module.Base = _TestBase
_db_module.async_session_factory = MagicMock()
_db_module.engine = MagicMock()
_db_module.init_db = AsyncMock()
_db_module.close_db = AsyncMock()
_db_module.get_db = AsyncMock()

# Force-set so it always takes effect (setdefault can lose to a prior import)
sys.modules["backend.app.database"] = _db_module

# ---------------------------------------------------------------------------
# Prompts — mocked to avoid pulling in LLM prompt templates
# ---------------------------------------------------------------------------
_prompt_mock = MagicMock()
_prompt_mock.MAPPING_SYSTEM_PROMPT = "You are a FIBO mapping expert."
_prompt_mock.build_mapping_prompt = MagicMock(return_value="mapped prompt")
_prompt_mock.MAPPING_OUTPUT_SCHEMA = {}
sys.modules.setdefault("backend.app.prompts.mapping_prompt", _prompt_mock)

_critic_prompt_mock = MagicMock()
_critic_prompt_mock.CRITIC_SYSTEM_PROMPT = "You are a FIBO critic expert."
_critic_prompt_mock.build_critic_prompt = MagicMock(return_value="critic prompt")
_critic_prompt_mock.CRITIC_OUTPUT_SCHEMA = {}
sys.modules.setdefault("backend.app.prompts.critic_prompt", _critic_prompt_mock)

# Revision prompt mock
_revision_prompt_mock = MagicMock()
_revision_prompt_mock.REVISION_SYSTEM_PROMPT = "You are a FIBO revision expert."
_revision_prompt_mock.build_revision_prompt = MagicMock(return_value="revision prompt")
sys.modules.setdefault("backend.app.prompts.revision_prompt", _revision_prompt_mock)

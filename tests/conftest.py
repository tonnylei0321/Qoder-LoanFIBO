"""Test configuration and shared fixtures.

Provides module-level mocks to isolate tests from heavy external dependencies
(LangChain, SQLAlchemy, etc.) so unit tests run without a real DB or LLM.
"""
import sys
from unittest.mock import MagicMock, AsyncMock

# ---------------------------------------------------------------------------
# Stub out modules that require real infrastructure before importing project code
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

# SQLAlchemy / database stub
_sa_mock = MagicMock()
sys.modules.setdefault("sqlalchemy", _sa_mock)
sys.modules.setdefault("sqlalchemy.ext", MagicMock())
sys.modules.setdefault("sqlalchemy.ext.asyncio", MagicMock())
sys.modules.setdefault("sqlalchemy.orm", MagicMock())
sys.modules.setdefault("sqlalchemy.sql", MagicMock())

# Project models & database — mock entirely so no real DB needed
_db_mock = MagicMock()
_db_mock.Base = MagicMock
_db_mock.async_session_factory = MagicMock()
sys.modules.setdefault("backend.app.database", _db_mock)

_table_mapping_mock = MagicMock()
_table_mapping_mock.TableMapping = MagicMock
_table_mapping_mock.FieldMapping = MagicMock
sys.modules.setdefault("backend.app.models.table_mapping", _table_mapping_mock)

_table_registry_mock = MagicMock()
_table_registry_mock.TableRegistry = MagicMock
sys.modules.setdefault("backend.app.models.table_registry", _table_registry_mock)

_llm_call_log_mock = MagicMock()
_llm_call_log_mock.LLMCallLog = MagicMock
sys.modules.setdefault("backend.app.models.llm_call_log", _llm_call_log_mock)

_mapping_job_mock = MagicMock()
_mapping_job_mock.MappingJob = MagicMock
sys.modules.setdefault("backend.app.models.mapping_job", _mapping_job_mock)

# Pipeline state
sys.modules.setdefault("backend.app.services.pipeline_state", MagicMock())

# TTL indexer
_ttl_mock = MagicMock()
_ttl_mock.search_candidates = AsyncMock(return_value=[])
sys.modules.setdefault("backend.app.services.ttl_indexer", _ttl_mock)

# Prompts
_prompt_mock = MagicMock()
_prompt_mock.MAPPING_SYSTEM_PROMPT = "You are a FIBO mapping expert."
_prompt_mock.build_mapping_prompt = MagicMock(return_value="mapped prompt")
_prompt_mock.MAPPING_OUTPUT_SCHEMA = {}
sys.modules.setdefault("backend.app.prompts.mapping_prompt", _prompt_mock)

"""FastAPI 依赖注入 - 规则引擎服务实例"""
from typing import Optional

from loguru import logger

from backend.app.config import settings

# ---- 单例缓存 ----
_graphdb_client: Optional["GraphDBClient"] = None
_compile_cache: Optional["CompileCache"] = None
_query_engine: Optional["QueryEngine"] = None
_rule_compiler: Optional["RuleCompiler"] = None
_compile_scheduler: Optional["CompileScheduler"] = None
_sql_executor: Optional["SQLExecutor"] = None
_result_assembler: Optional["ResultAssembler"] = None
_ontology_index: Optional["OntologyIndex"] = None


async def get_graphdb_client():
    """获取 GraphDB 客户端单例"""
    global _graphdb_client
    if _graphdb_client is None:
        from backend.app.services.graphdb_client import GraphDBClient
        _graphdb_client = GraphDBClient(
            endpoint=settings.GRAPHDB_ENDPOINT,
            repo=settings.GRAPHDB_REPO,
        )
    return _graphdb_client


async def get_redis_client():
    """获取 Redis 客户端（延迟初始化）

    生产环境使用真实 Redis，开发环境使用 fake-redis 兼容层。
    """
    import redis.asyncio as aioredis
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_compile_cache():
    """获取编译缓存单例"""
    global _compile_cache
    if _compile_cache is None:
        from backend.app.services.compile_cache import CompileCache
        redis = await get_redis_client()
        _compile_cache = CompileCache(redis)
    return _compile_cache


async def get_query_engine():
    """获取查询引擎单例"""
    global _query_engine
    if _query_engine is None:
        from backend.app.services.query.query_engine import QueryEngine
        from backend.app.services.query.intent_classifier import IntentClassifier
        from backend.app.services.query.rule_matcher import RuleMatcher
        from backend.app.services.query.sql_generator import SQLGenerator
        from backend.app.services.query.semantic_mapping import SemanticMapping, TableMapping

        cache = await get_compile_cache()
        # 默认语义映射（后续从 GraphDB 动态加载）
        mapping = SemanticMapping(
            concept_to_table={},
            relation_to_join={},
            table_mappings={},
        )
        classifier = IntentClassifier(templates=[])
        rule_matcher = RuleMatcher()
        sql_generator = SQLGenerator(mapping)

        _query_engine = QueryEngine(
            classifier=classifier,
            rule_matcher=rule_matcher,
            sql_generator=sql_generator,
            cache=cache,
        )
    return _query_engine


async def get_rule_compiler():
    """获取规则编译器单例"""
    global _rule_compiler
    if _rule_compiler is None:
        from backend.app.services.rules.compiler import RuleCompiler
        from backend.app.services.rules.conflict_resolver import ConflictResolver
        from backend.app.services.rules.dsl_parser import DSLParser
        from backend.app.services.rules.dsl_executor import DSLExecutor

        graphdb = await get_graphdb_client()
        cache = await get_compile_cache()

        _rule_compiler = RuleCompiler(
            graphdb_client=graphdb,
            cache=cache,
            conflict_resolver=ConflictResolver(),
            dsl_parser=DSLParser(),
            dsl_executor=DSLExecutor(),
        )
    return _rule_compiler


async def get_compile_scheduler():
    """获取编译调度器单例"""
    global _compile_scheduler
    if _compile_scheduler is None:
        from backend.app.services.rules.compile_scheduler import CompileScheduler
        cache = await get_compile_cache()
        compiler = await get_rule_compiler()

        _compile_scheduler = CompileScheduler(cache=cache, compiler=compiler)
    return _compile_scheduler


async def get_sql_executor():
    """获取 SQL 执行器"""
    global _sql_executor
    if _sql_executor is None:
        from backend.app.services.query.sql_executor import SQLExecutor
        from backend.app.database import async_session_factory
        _sql_executor = SQLExecutor(async_session_factory)
    return _sql_executor


async def get_result_assembler():
    """获取结果组装器"""
    global _result_assembler
    if _result_assembler is None:
        from backend.app.services.query.result_assembler import ResultAssembler
        _result_assembler = ResultAssembler()
    return _result_assembler


async def get_ontology_index():
    """获取本体索引"""
    global _ontology_index
    if _ontology_index is None:
        from backend.app.services.ontology_index import OntologyIndex
        client = await get_graphdb_client()
        _ontology_index = OntologyIndex(client)
    return _ontology_index


async def close_services():
    """关闭所有服务连接"""
    global _graphdb_client
    if _graphdb_client is not None:
        await _graphdb_client.close()
        _graphdb_client = None
        logger.info("GraphDB client closed")

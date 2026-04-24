"""图谱浏览 API - 实体列表/详情/边/搜索，支持多实例选择"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_graphdb_client
from backend.app.services.graphdb_client import GraphDBClient
from backend.app.services.sync.graph_explorer import GraphExplorer
from backend.app.database import get_db
from backend.app.models.graphdb_instance import GraphDBInstance

router = APIRouter()


async def _get_explorer(
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
) -> GraphExplorer:
    """获取 GraphExplorer 实例

    如果指定了 instance_id，则从数据库加载该实例的连接信息
    创建对应的 GraphDBClient；否则使用默认客户端。
    """
    if instance_id:
        result = await db.execute(
            select(GraphDBInstance).where(GraphDBInstance.id == instance_id)
        )
        inst = result.scalar_one_or_none()
        if inst is None:
            raise HTTPException(status_code=404, detail="GraphDB 实例不存在")
        if not inst.is_active:
            raise HTTPException(status_code=400, detail="GraphDB 实例已停用")
        client = GraphDBClient(
            endpoint=inst.server_url,
            repo=inst.repo_id,
        )
        return GraphExplorer(client)
    return GraphExplorer(default_client)


@router.get("/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    instance_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """查询实体列表"""
    explorer = await _get_explorer(instance_id, default_client, db)
    try:
        entities = await explorer.list_entities(entity_type, limit, offset)
        return {"entities": entities, "total": len(entities)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/entity-detail")
async def get_entity(
    uri: str,
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """获取实体详情"""
    explorer = await _get_explorer(instance_id, default_client, db)
    if not uri.startswith("http"):
        uri = f"http://loanfibo.org/ontology/{uri}"
    try:
        return await explorer.get_entity(uri)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/entity-edges")
async def get_entity_edges(
    uri: str,
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """获取实体的边（关系）"""
    explorer = await _get_explorer(instance_id, default_client, db)
    if not uri.startswith("http"):
        uri = f"http://loanfibo.org/ontology/{uri}"
    try:
        edges = await explorer.get_entity_edges(uri)
        return {"edges": edges, "total": len(edges)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/search")
async def search_entities(
    q: str,
    instance_id: Optional[str] = None,
    limit: int = 20,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """搜索实体"""
    explorer = await _get_explorer(instance_id, default_client, db)
    try:
        results = await explorer.search_entities(q, limit)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/facet-tree")
async def get_facet_tree(
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """获取分面树"""
    explorer = await _get_explorer(instance_id, default_client, db)
    try:
        return await explorer.get_facet_tree()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/indicator-detail")
async def get_indicator_detail(
    uri: str,
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """获取指标四Tab详情"""
    explorer = await _get_explorer(instance_id, default_client, db)
    if not uri.startswith("http"):
        uri = f"http://yql.example.com/ontology/credit-risk/{uri}"
    try:
        return await explorer.get_indicator_detail(uri)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/scenario-indicators")
async def get_scenario_indicators(
    scenario: str,
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """按场景查询指标列表（含公式、SQL、数据来源）"""
    explorer = await _get_explorer(instance_id, default_client, db)
    try:
        indicators = await explorer.get_scenario_indicators(scenario)
        return {"indicators": indicators, "total": len(indicators)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")


@router.get("/search-business")
async def search_business(
    q: str,
    facet: Optional[str] = None,
    limit: int = 30,
    instance_id: Optional[str] = None,
    default_client: GraphDBClient = Depends(get_graphdb_client),
    db: AsyncSession = Depends(get_db),
):
    """业务化搜索"""
    explorer = await _get_explorer(instance_id, default_client, db)
    try:
        results = await explorer.search_business(q, facet, limit)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GraphDB 查询失败: {e}")

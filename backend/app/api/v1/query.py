"""NLQ查询API"""
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.query import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_nlq(request: QueryRequest):
    """自然语言查询接口

    接受自然语言查询文本，经过意图分类、规则匹配、SQL生成后返回结果。
    """
    # TODO: 集成 QueryEngine 实例（依赖注入）
    return QueryResponse(
        status="service_unavailable",
        message="查询引擎尚未初始化",
    )

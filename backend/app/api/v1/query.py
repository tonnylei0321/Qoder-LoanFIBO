"""NLQ查询API - 接入QueryEngine"""
from fastapi import APIRouter, HTTPException, Depends

from backend.app.schemas.query import QueryRequest, QueryResponse
from backend.app.dependencies import get_query_engine

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_nlq(
    request: QueryRequest,
    engine=Depends(get_query_engine),
):
    """自然语言查询接口

    接受自然语言查询文本，经过意图分类、规则匹配、SQL生成后返回结果。
    """
    result = await engine.query(
        tenant_id=request.tenant_id,
        query_text=request.query,
        context=request.context,
        options=request.options,
    )
    return QueryResponse(
        status=result.status.value,
        data=result.data,
        sql=result.sql,
        message=result.message,
        retry_after=result.retry_after,
        admin_alert=result.admin_alert,
    )

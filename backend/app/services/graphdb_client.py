"""GraphDB双模式客户端 - 异步(httpx)/同步(httpx同步)"""
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class GraphDBClient:
    """GraphDB客户端 - 双模式（异步/同步）

    架构说明：
    - 异步模式：供FastAPI查询引擎使用（httpx.AsyncClient）
    - 同步模式：供Celery Worker编译器使用（httpx.Client同步接口）
    - 两种模式共享同一配置，但使用不同的HTTP客户端实例
    """

    def __init__(self, endpoint: str = "http://localhost:7200", repo: str = "rules"):
        self.endpoint = endpoint.rstrip("/")
        self.repo = repo

        # 异步客户端配置
        self._async_session: Optional[httpx.AsyncClient] = None
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.limits = httpx.Limits(
            max_connections=50, max_keepalive_connections=10
        )

        # 同步客户端配置（供Celery Worker使用）
        self._sync_session: Optional[httpx.Client] = None

    # ---- 异步模式（FastAPI查询引擎） ----

    async def _get_async_session(self) -> httpx.AsyncClient:
        """获取异步HTTP客户端（延迟初始化）"""
        if self._async_session is None:
            self._async_session = httpx.AsyncClient(
                timeout=self.timeout, limits=self.limits
            )
        return self._async_session

    async def query_rules(
        self, industry: Optional[str] = None, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """查询规则（异步模式）

        适用场景：FastAPI查询引擎、API层调用
        """
        cache_hint = "pragma: cache" if use_cache else "pragma: no-cache"
        industry_filter = (
            f'?rule loanfibo:industry "{industry}" .' if industry else ""
        )

        sparql = f"""
        {cache_hint}
        PREFIX loanfibo: <http://loanfibo.org/ontology/>

        SELECT ?rule ?table ?field ?target
        WHERE {{
            ?rule a loanfibo:MappingRule .
            ?rule loanfibo:sourceTable ?table .
            OPTIONAL {{ ?rule loanfibo:sourceField ?field }}
            OPTIONAL {{ ?rule loanfibo:targetProperty ?target }}
            {industry_filter}
        }}
        """

        session = await self._get_async_session()
        response = await session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        return self._parse_results(response.json())

    # ---- 同步模式（Celery Worker编译器） ----

    def _get_sync_session(self) -> httpx.Client:
        """获取同步HTTP客户端（供Celery Worker使用）"""
        if self._sync_session is None:
            self._sync_session = httpx.Client(
                timeout=self.timeout,
                headers={"Accept": "application/sparql-results+json"},
            )
        return self._sync_session

    def query_rules_sync(
        self, industry: Optional[str] = None, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """查询规则（同步模式）

        适用场景：Celery Worker中的编译任务
        不使用 async/await，纯同步调用
        """
        cache_hint = "pragma: cache" if use_cache else "pragma: no-cache"
        industry_filter = (
            f'?rule loanfibo:industry "{industry}" .' if industry else ""
        )

        sparql = f"""
        {cache_hint}
        PREFIX loanfibo: <http://loanfibo.org/ontology/>

        SELECT ?rule ?table ?field ?target
        WHERE {{
            ?rule a loanfibo:MappingRule .
            ?rule loanfibo:sourceTable ?table .
            OPTIONAL {{ ?rule loanfibo:sourceField ?field }}
            OPTIONAL {{ ?rule loanfibo:targetProperty ?target }}
            {industry_filter}
        }}
        """

        session = self._get_sync_session()
        response = session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
        )
        response.raise_for_status()
        return self._parse_results(response.json())

    # ---- 共享方法 ----

    def _parse_results(self, data: dict) -> List[Dict[str, Any]]:
        """解析SPARQL查询结果"""
        results = []
        for binding in data.get("results", {}).get("bindings", []):
            results.append(
                {
                    "rule": binding.get("rule", {}).get("value"),
                    "table": binding.get("table", {}).get("value"),
                    "field": binding.get("field", {}).get("value"),
                    "target": binding.get("target", {}).get("value"),
                }
            )
        return results

    async def close(self):
        """关闭所有HTTP客户端"""
        if self._async_session:
            await self._async_session.aclose()
            self._async_session = None
        if self._sync_session:
            self._sync_session.close()
            self._sync_session = None

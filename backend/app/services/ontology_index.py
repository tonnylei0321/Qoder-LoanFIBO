"""本体索引服务 - 基于 GraphDB 的 FIBO 本体检索"""
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.graphdb_client import GraphDBClient


class OntologyIndex:
    """本体索引服务

    职责：
    - 从 GraphDB 查询 FIBO 类和属性定义
    - 支持按 URI / 标签 / 命名空间搜索
    - 为映射 Pipeline 提供候选类检索能力
    """

    def __init__(self, graphdb_client: GraphDBClient):
        self.client = graphdb_client

    async def search_classes(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索 FIBO 类

        Args:
            query: 搜索关键词（URI 片段或标签）
            limit: 返回数量限制
        """
        sparql = f"""
        SELECT ?class ?label ?comment ?parent
        WHERE {{
            ?class a owl:Class .
            OPTIONAL {{ ?class rdfs:label ?label }}
            OPTIONAL {{ ?class rdfs:comment ?comment }}
            OPTIONAL {{ ?class rdfs:subClassOf ?parent }}
            FILTER(
                CONTAINS(STR(?class), "{query}")
                || (?label && CONTAINS(LCASE(STR(?label)), LCASE("{query}")))
            )
        }}
        LIMIT {limit}
        """
        try:
            session = await self.client._get_async_session()
            resp = await session.post(
                f"{self.client.endpoint}/repositories/{self.client.repo}",
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
            resp.raise_for_status()
            results = []
            for binding in resp.json().get("results", {}).get("bindings", []):
                results.append({
                    "class_uri": binding.get("class", {}).get("value", ""),
                    "label": binding.get("label", {}).get("value", ""),
                    "comment": binding.get("comment", {}).get("value", ""),
                    "parent_uri": binding.get("parent", {}).get("value", ""),
                })
            return results
        except Exception as e:
            logger.error(f"OntologyIndex search_classes failed: {e}")
            return []

    async def get_class_detail(self, class_uri: str) -> Optional[Dict[str, Any]]:
        """获取类的详细信息（标签、注释、属性、父类）"""
        sparql = f"""
        SELECT ?label ?comment ?parent
        WHERE {{
            <{class_uri}> a owl:Class .
            OPTIONAL {{ <{class_uri}> rdfs:label ?label }}
            OPTIONAL {{ <{class_uri}> rdfs:comment ?comment }}
            OPTIONAL {{ <{class_uri}> rdfs:subClassOf ?parent }}
        }}
        LIMIT 1
        """
        try:
            session = await self.client._get_async_session()
            resp = await session.post(
                f"{self.client.endpoint}/repositories/{self.client.repo}",
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])
            if not bindings:
                return None
            b = bindings[0]
            return {
                "uri": class_uri,
                "label": b.get("label", {}).get("value", ""),
                "comment": b.get("comment", {}).get("value", ""),
                "parent_uri": b.get("parent", {}).get("value", ""),
            }
        except Exception as e:
            logger.error(f"OntologyIndex get_class_detail failed: {e}")
            return None

    async def list_properties_for_class(
        self,
        class_uri: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取类的属性（domain 为该类的属性）"""
        sparql = f"""
        SELECT ?prop ?type ?label ?range
        WHERE {{
            ?prop a ?type .
            FILTER(?type IN (owl:ObjectProperty, owl:DatatypeProperty))
            OPTIONAL {{ ?prop rdfs:label ?label }}
            OPTIONAL {{ ?prop rdfs:range ?range }}
            {{ ?prop rdfs:domain <{class_uri}> }}
        }}
        LIMIT {limit}
        """
        try:
            session = await self.client._get_async_session()
            resp = await session.post(
                f"{self.client.endpoint}/repositories/{self.client.repo}",
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
            resp.raise_for_status()
            results = []
            for binding in resp.json().get("results", {}).get("bindings", []):
                results.append({
                    "property_uri": binding.get("prop", {}).get("value", ""),
                    "property_type": binding.get("type", {}).get("value", ""),
                    "label": binding.get("label", {}).get("value", ""),
                    "range_uri": binding.get("range", {}).get("value", ""),
                })
            return results
        except Exception as e:
            logger.error(f"OntologyIndex list_properties_for_class failed: {e}")
            return []

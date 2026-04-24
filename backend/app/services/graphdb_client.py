"""GraphDB双模式客户端 - 异步(httpx)/同步(httpx同步)"""
import re
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

# SPARQL安全字符白名单：仅允许字母、数字、下划线、连字符
_SPARQL_SAFE_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')


def _validate_sparql_literal(value: str, param_name: str) -> str:
    """校验SPARQL字面量安全性，防止注入"""
    if not _SPARQL_SAFE_PATTERN.match(value):
        raise ValueError(
            f"{param_name} 包含非法字符，仅允许字母/数字/下划线/连字符: {value!r}"
        )
    return value


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
        industry_filter = ""
        if industry:
            safe_industry = _validate_sparql_literal(industry, "industry")
            industry_filter = f'?rule loanfibo:industry "{safe_industry}" .'

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
        industry_filter = ""
        if industry:
            safe_industry = _validate_sparql_literal(industry, "industry")
            industry_filter = f'?rule loanfibo:industry "{safe_industry}" .'

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

    # ---- 融资企业查询 ----

    async def query_applicant_orgs(self) -> List[Dict[str, Any]]:
        """从 GraphDB 查询所有融资企业清单。

        Returns:
            [{"uri": "...", "name": "...", "org_id": "..."}, ...]
            org_id 从 URI 末尾提取（如 Org_a1b2c3d4 中的 a1b2c3d4）
        """
        sparql = """
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?org ?name WHERE {
            ?org a yql:ApplicantOrg ;
                 rdfs:label ?name .
        }
        """

        session = await self._get_async_session()
        response = await session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for binding in data.get("results", {}).get("bindings", []):
            uri = binding.get("org", {}).get("value", "")
            name = binding.get("name", {}).get("value", "")
            # 从 URI 提取 org_id（URI 格式如 .../Org_a1b2c3d4）
            org_id = uri.split("Org_")[-1] if "Org_" in uri else ""
            results.append({"uri": uri, "name": name, "org_id": org_id})
        return results

    # ---- 融资企业→实例→指标SQL 链路查询 ----

    async def query_org_linked_instance(self, org_uri: str) -> Optional[Dict[str, Any]]:
        """查询融资企业关联的 ERP 实例。

        Returns:
            {"instance_uri": "...", "instance_code": "NCC", "instance_name": "用友NCC",
             "erp_agent_datasource": "ncc_erp", "org_key_field": "PK_ORG"}
            或 None（未关联实例）
        """
        sparql = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?instance ?instanceCode ?instanceName ?datasource ?orgKeyField WHERE {{
            <{org_uri}> yql:linkedToInstance ?instance .
            ?instance a yql:ERPInstance ;
                      yql:instanceCode ?instanceCode ;
                      yql:instanceName ?instanceName ;
                      yql:erpAgentDatasource ?datasource ;
                      yql:orgKeyField ?orgKeyField .
        }} LIMIT 1
        """

        session = await self._get_async_session()
        response = await session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return None
        b = bindings[0]
        return {
            "instance_uri": b["instance"]["value"],
            "instance_code": b["instanceCode"]["value"],
            "instance_name": b["instanceName"]["value"],
            "erp_agent_datasource": b["datasource"]["value"],
            "org_key_field": b["orgKeyField"]["value"],
        }

    async def query_instance_indicator_sqls(
        self, instance_uri: Optional[str] = None, scenario: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询 ERP 实例下的所有指标 SQL。

        如果指定 instance_uri，则查该实例关联的指标；
        如果不指定，则查所有 CalculationRule（当前只有一个实例，等效）。

        Args:
            instance_uri: ERP实例URI，可选
            scenario: 场景标识（PreLoanDD / PostLoanMonitoring / SupplyChainFinance），可选

        Returns:
            [{"rule_uri": "...", "rule_label": "...", "indicator_uri": "...",
              "indicator_label": "...", "sql": "...", "scenario_uri": "...",
              "scenario_id": "PreLoanDD", "formula": "...", "notation": "..."}, ...]
        """
        scenario_filter = ""
        if scenario:
            scenario_uri = f"http://yql.example.com/ontology/scenario/{scenario}"
            scenario_filter = f"?rule yql:appliedInScenario <{scenario_uri}> ."

        sparql = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?rule ?ruleLabel ?indicator ?indicatorLabel ?sql ?scenario ?formula ?notation
        WHERE {{
            ?rule a yql:CalculationRule ;
                  yql:computesIndicator ?indicator ;
                  yql:hasSQL ?sql .
            {scenario_filter}
            ?indicator rdfs:label ?indicatorLabel .
            ?rule rdfs:label ?ruleLabel .
            OPTIONAL {{ ?rule yql:appliedInScenario ?scenario }}
            OPTIONAL {{ ?rule yql:hasFormula ?formula }}
            OPTIONAL {{ ?rule skos:notation ?notation }}
        }} ORDER BY ?scenario ?indicatorLabel
        """

        session = await self._get_async_session()
        response = await session.post(
            f"{self.endpoint}/repositories/{self.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for b in data.get("results", {}).get("bindings", []):
            scenario_uri = b.get("scenario", {}).get("value", "")
            scenario_id = scenario_uri.split("/")[-1] if scenario_uri else ""
            results.append({
                "rule_uri": b["rule"]["value"],
                "rule_label": b["ruleLabel"]["value"],
                "indicator_uri": b["indicator"]["value"],
                "indicator_label": b["indicatorLabel"]["value"],
                "sql": b["sql"]["value"],
                "scenario_uri": scenario_uri,
                "scenario_id": scenario_id,
                "formula": b.get("formula", {}).get("value", ""),
                "notation": b.get("notation", {}).get("value", ""),
            })
        return results

    async def query_org_indicator_sqls(
        self, org_uri: str, scenario: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """融资企业→实例→指标SQL 全链路查询。

        通过企业URI查询关联的ERP实例，再获取该实例下所有指标的SQL。
        如果企业未关联实例，则返回空列表。

        Args:
            org_uri: 融资企业在GraphDB中的URI
            scenario: 场景标识，可选

        Returns:
            [{"rule_uri": "...", "sql": "...", "erp_agent_datasource": "ncc_erp",
              "org_key_field": "PK_ORG", ...}, ...]
        """
        # 第一步：查企业关联的ERP实例
        instance_info = await self.query_org_linked_instance(org_uri)
        if not instance_info:
            logger.warning(f"企业 {org_uri} 未关联任何 ERPInstance，无法获取指标SQL")
            return []

        # 第二步：查实例下所有指标的SQL
        rules = await self.query_instance_indicator_sqls(
            instance_uri=instance_info["instance_uri"],
            scenario=scenario,
        )

        # 第三步：将 ERP 实例信息注入每条规则
        for rule in rules:
            rule["erp_agent_datasource"] = instance_info["erp_agent_datasource"]
            rule["org_key_field"] = instance_info["org_key_field"]
            rule["instance_code"] = instance_info["instance_code"]
            rule["instance_uri"] = instance_info["instance_uri"]

        return rules

"""图谱浏览器 - SPARQL 查询实体/属性/边/搜索"""
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.graphdb_client import GraphDBClient


class GraphExplorer:
    """图谱浏览服务

    职责：
    - 查询实体列表（分页）
    - 获取实体详情（属性值）
    - 获取实体的边（关系）
    - 搜索实体（URI/关键词）
    - 支持钻取浏览
    """

    def __init__(self, graphdb_client: GraphDBClient):
        self.client = graphdb_client

    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询实体列表

        过滤系统命名空间（w3.org、rdf/owl/rdfs/xsd），只返回业务实体。
        同一实体的多个类型只保留最具体的一个（非 owl:Class 类型的优先）。
        结果按 label 和 uri 排序，有 label 的排在前面。

        Args:
            entity_type: 可选的实体类型过滤（FIBO 类 URI）
            limit: 分页限制
            offset: 分页偏移
        """
        type_filter = ""
        use_subclass = False
        YQL = "http://yql.example.com/ontology/credit-risk/"
        if entity_type:
            # Indicator 类是 owl:Class, 需要 subClassOf+ 查询
            if entity_type in [f"{YQL}Indicator", f"{YQL}RatioIndicator",
                               f"{YQL}AmountIndicator", f"{YQL}CountIndicator"]:
                type_filter = f"?entity rdfs:subClassOf+ <{entity_type}> ."
                use_subclass = True
            else:
                type_filter = f"?entity a <{entity_type}> ."

        # 两步查询：先取原始结果，再在 Python 层去重
        if use_subclass:
            sparql = f"""
            SELECT DISTINCT ?entity ?label ?subject
            WHERE {{
                {type_filter}
                OPTIONAL {{ ?entity <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
                OPTIONAL {{ ?entity <http://purl.org/dc/terms/subject> ?subject }}
                FILTER(!STRSTARTS(STR(?entity), "http://www.w3.org/"))
            }}
            ORDER BY DESC(BOUND(?label)) ?label ?entity
            LIMIT {min(limit * 5, 500)}
            OFFSET {offset}
            """
        else:
            sparql = f"""
            SELECT DISTINCT ?entity ?type ?label
            WHERE {{
                {type_filter}
                ?entity a ?type .
                OPTIONAL {{ ?entity <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
                FILTER(
                    !STRSTARTS(STR(?entity), "http://www.w3.org/")
                    && !STRSTARTS(STR(?type), "http://www.w3.org/")
                )
            }}
            ORDER BY DESC(BOUND(?label)) ?label ?entity
            LIMIT {min(limit * 5, 500)}
            OFFSET {offset}
            """

        session = await self.client._get_async_session()
        resp = await session.post(
            f"{self.client.endpoint}/repositories/{self.client.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
        raw = self._parse_entity_results(resp.json())

        if use_subclass:
            # Indicator 类查询结果包含 subject，转为统一格式
            results = []
            for item in raw:
                results.append({
                    "uri": item["uri"],
                    "type": entity_type,
                    "label": item.get("label", ""),
                })
            return results[:limit]

        # 去重：同一 entity 只保留最具体的类型（优先非 owl:Class / owl:Property 的业务类型）
        seen_entities: dict = {}
        for item in raw:
            uri = item["uri"]
            typ = item["type"]
            if uri not in seen_entities:
                seen_entities[uri] = item
            else:
                existing_type = seen_entities[uri]["type"]
                # 如果现有类型是元模型类型（owl:Class 等），替换为业务类型
                existing_short = existing_type.split("#")[-1] or existing_type.split("/")[-1]
                new_short = typ.split("#")[-1] or typ.split("/")[-1]
                meta_types = {"Class", "Property", "ObjectProperty", "DatatypeProperty",
                              "TransitiveProperty", "SymmetricProperty", "FunctionalProperty",
                              "InverseFunctionalProperty", "AnnotationProperty", "Ontology"}
                if existing_short in meta_types and new_short not in meta_types:
                    seen_entities[uri] = item

        return list(seen_entities.values())[:limit]

    async def get_entity(self, entity_uri: str) -> Dict[str, Any]:
        """获取实体详情（所有属性值）"""
        sparql = f"""
        SELECT ?property ?value ?valueType
        WHERE {{
            <{entity_uri}> ?property ?value .
            BIND(IF(isIRI(?value), "uri", "literal") AS ?valueType)
        }}
        """

        session = await self.client._get_async_session()
        resp = await session.post(
            f"{self.client.endpoint}/repositories/{self.client.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()

        properties = []
        for binding in resp.json().get("results", {}).get("bindings", []):
            prop = binding.get("property", {}).get("value", "")
            val = binding.get("value", {}).get("value", "")
            val_type = binding.get("valueType", {}).get("value", "literal")
            # 过滤系统属性
            if prop.startswith("http://www.w3.org/"):
                continue
            properties.append({
                "property": prop,
                "value": val,
                "value_type": val_type,
            })

        return {
            "uri": entity_uri,
            "properties": properties,
            "provenance": self._extract_provenance(properties),
        }

    def _extract_provenance(self, properties: List[Dict]) -> Dict[str, Any]:
        """从实体属性中提取映射来源信息

        查找 loanfibo: 命名空间下的来源属性，如 sourceJob, sourceVersion 等。
        """
        provenance: Dict[str, Any] = {}
        prov_keys = {
            "sourceJob": "job_id",
            "sourceVersion": "version_tag",
            "mappedAt": "mapped_at",
            "mappedBy": "mapped_by",
            "sourceTable": "source_table",
        }
        for prop in properties:
            prop_uri = prop.get("property", "")
            val = prop.get("value", "")
            # Check for loanfibo provenance properties
            if "loanfibo.org" in prop_uri:
                for key, out_key in prov_keys.items():
                    if key in prop_uri:
                        provenance[out_key] = val
        return provenance

    async def get_entity_edges(self, entity_uri: str) -> List[Dict[str, Any]]:
        """获取实体的边（出边 + 入边）"""
        sparql = f"""
        SELECT ?direction ?property ?target ?targetLabel ?targetType
        WHERE {{
            {{
                <{entity_uri}> ?property ?target .
                FILTER(isIRI(?target))
                OPTIONAL {{ ?target <http://www.w3.org/2000/01/rdf-schema#label> ?targetLabel }}
                OPTIONAL {{ ?target a ?targetType }}
                BIND("outgoing" AS ?direction)
            }} UNION {{
                ?target ?property <{entity_uri}> .
                FILTER(isIRI(?target))
                OPTIONAL {{ ?target <http://www.w3.org/2000/01/rdf-schema#label> ?targetLabel }}
                OPTIONAL {{ ?target a ?targetType }}
                BIND("incoming" AS ?direction)
            }}
        }}
        LIMIT 100
        """

        session = await self.client._get_async_session()
        resp = await session.post(
            f"{self.client.endpoint}/repositories/{self.client.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()

        edges = []
        for binding in resp.json().get("results", {}).get("bindings", []):
            prop = binding.get("property", {}).get("value", "")
            target = binding.get("target", {}).get("value", "")
            direction = binding.get("direction", {}).get("value", "")
            label = binding.get("targetLabel", {}).get("value", "")
            target_type = binding.get("targetType", {}).get("value", "")
            if prop.startswith("http://www.w3.org/"):
                continue
            edges.append({
                "direction": direction,
                "property": prop,
                "target": target,
                "target_label": label,
                "target_type": target_type,
            })
        return edges

    async def search_entities(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索实体（按 URI 或标签关键词）

        过滤系统命名空间，只搜索业务实体。同一实体多个类型只保留最具体的。
        """
        sparql = f"""
        SELECT ?entity ?type ?label
        WHERE {{
            ?entity a ?type .
            OPTIONAL {{ ?entity <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
            FILTER(
                !STRSTARTS(STR(?entity), "http://www.w3.org/")
                && (
                    CONTAINS(STR(?entity), "{query}")
                    || (?label && CONTAINS(LCASE(STR(?label)), LCASE("{query}")))
                )
            )
        }}
        ORDER BY DESC(BOUND(?label)) ?label ?entity
        LIMIT {min(limit * 5, 200)}
        """

        session = await self.client._get_async_session()
        resp = await session.post(
            f"{self.client.endpoint}/repositories/{self.client.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
        raw = self._parse_entity_results(resp.json())

        # 去重
        seen_entities: dict = {}
        for item in raw:
            uri = item["uri"]
            typ = item["type"]
            if uri not in seen_entities:
                seen_entities[uri] = item
            else:
                existing_type = seen_entities[uri]["type"]
                existing_short = existing_type.split("#")[-1] or existing_type.split("/")[-1]
                new_short = typ.split("#")[-1] or typ.split("/")[-1]
                meta_types = {"Class", "Property", "ObjectProperty", "DatatypeProperty",
                              "TransitiveProperty", "SymmetricProperty", "FunctionalProperty",
                              "InverseFunctionalProperty", "AnnotationProperty", "Ontology"}
                if existing_short in meta_types and new_short not in meta_types:
                    seen_entities[uri] = item

        return list(seen_entities.values())[:limit]

    # ─── 私有方法 ───────────────────────────────────────────────

    # ─── 业务化 API ────────────────────────────────────────────

    async def get_facet_tree(self) -> Dict[str, Any]:
        """获取分面树数据

        返回结构化的分面树，包含各类型实体数量及子分组。
        """
        YQL = "http://yql.example.com/ontology/credit-risk/"
        NCC = "http://yql.example.com/ontology/ncc-mapping/"
        ACC = "http://yql.example.com/ontology/account-code/"

        # 1) 类型数量聚合
        sparql_counts = """
        SELECT ?type (COUNT(DISTINCT ?s) AS ?count) WHERE {
            ?s a ?type .
            FILTER(!STRSTARTS(STR(?type), "http://www.w3.org/"))
        } GROUP BY ?type ORDER BY DESC(?count)
        """
        counts_raw = await self._run_sparql(sparql_counts)
        type_counts = {}
        for b in counts_raw:
            t = b["type"]["value"]
            c = int(b["count"]["value"])
            type_counts[t] = c

        # 2) 指标按主题分组
        sparql_topics = """
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        SELECT ?topic (COUNT(DISTINCT ?c) AS ?count) WHERE {
            ?c rdfs:subClassOf+ yql:Indicator ;
               dcterms:subject ?topic .
        } GROUP BY ?topic ORDER BY DESC(?count)
        """
        topics_raw = await self._run_sparql(sparql_topics)
        indicator_children = []
        for b in topics_raw:
            topic = b["topic"]["value"]
            cnt = int(b["count"]["value"])
            indicator_children.append({
                "id": f"indicator-topic-{topic}",
                "label": f"{topic}({cnt})",
                "topic": topic,
                "count": cnt,
                "isLeaf": False,
            })

        # 3) 数据来源按表分组
        sparql_tables = """
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?table ?tableLabel (COUNT(DISTINCT ?f) AS ?count) WHERE {
            ?f a yql:NCCField ; yql:inTable ?table .
            ?table a yql:NCCTable ; rdfs:label ?tableLabel .
        } GROUP BY ?table ?tableLabel ORDER BY ?tableLabel
        """
        tables_raw = await self._run_sparql(sparql_tables)
        data_source_children = []
        for b in tables_raw:
            tbl_uri = b["table"]["value"]
            tbl_label = b.get("tableLabel", {}).get("value", tbl_uri.split("/")[-1])
            cnt = int(b["count"]["value"])
            data_source_children.append({
                "id": f"table-{tbl_uri}",
                "label": f"{tbl_label}({cnt})",
                "uri": tbl_uri,
                "count": cnt,
                "isLeaf": False,
            })

        # 4) 会计科目按前缀分组
        sparql_acc = """
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?prefix (COUNT(DISTINCT ?a) AS ?count) WHERE {
            ?a a yql:AccountCode ;
               rdfs:label ?label .
            BIND(SUBSTR(?label, 1, 1) AS ?prefix)
        } GROUP BY ?prefix ORDER BY ?prefix
        """
        acc_raw = await self._run_sparql(sparql_acc)
        acc_prefix_map = {"1": "资产类", "2": "负债类", "3": "共同类", "4": "权益类", "5": "成本类", "6": "损益类"}
        account_children = []
        for b in acc_raw:
            prefix = b["prefix"]["value"]
            cnt = int(b["count"]["value"])
            name = acc_prefix_map.get(prefix, f"{prefix}xxx类")
            account_children.append({
                "id": f"account-prefix-{prefix}",
                "label": f"{name}({cnt})",
                "prefix": prefix,
                "count": cnt,
                "isLeaf": False,
            })

        # 组装树
        ncc_table_count = type_counts.get(f"{YQL}NCCTable", 0)
        ncc_field_count = type_counts.get(f"{YQL}NCCField", 0)
        indicator_count = sum(c["count"] for c in indicator_children)
        rule_count = type_counts.get(f"{YQL}CalculationRule", 0)
        value_count = type_counts.get(f"{YQL}IndicatorValue", 0)
        acc_count = type_counts.get(f"{YQL}AccountCode", 0)
        scenario_count = type_counts.get(f"{YQL}Scenario", 0)
        org_count = type_counts.get(f"{YQL}ApplicantOrg", 0)
        authscope_count = type_counts.get(f"{YQL}AuthorizationScope", 0)
        instance_count = type_counts.get(f"{YQL}ERPInstance", 0)

        # ERPInstance 子项
        sparql_instances = """
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?instance ?label ?code ?datasource WHERE {
            ?instance a yql:ERPInstance ;
                      rdfs:label ?label .
            OPTIONAL { ?instance yql:instanceCode ?code }
            OPTIONAL { ?instance yql:erpAgentDatasource ?datasource }
        } ORDER BY ?label
        """
        instances_raw = await self._run_sparql(sparql_instances)
        instance_children = []
        for b in instances_raw:
            inst_uri = b["instance"]["value"]
            inst_label = b.get("label", {}).get("value", inst_uri.split("/")[-1])
            inst_code = b.get("code", {}).get("value", "")
            inst_ds = b.get("datasource", {}).get("value", "")
            instance_children.append({
                "id": f"instance-{inst_uri}",
                "label": f"{inst_label}",
                "uri": inst_uri,
                "code": inst_code,
                "datasource": inst_ds,
                "isLeaf": True,
            })

        return {
            "facets": [
                {
                    "id": "facet-indicator", "label": f"风控指标({indicator_count})",
                    "icon": "indicator", "children": indicator_children,
                },
                {
                    "id": "facet-rule", "label": f"计算口径({rule_count})",
                    "icon": "rule", "children": [],
                },
                {
                    "id": "facet-value", "label": f"历史数据({value_count})",
                    "icon": "value", "children": [],
                },
                {
                    "id": "facet-datasource", "label": f"数据来源({ncc_table_count}表,{ncc_field_count}字段)",
                    "icon": "datasource", "children": data_source_children,
                },
                {
                    "id": "facet-account", "label": f"会计科目({acc_count})",
                    "icon": "account", "children": account_children,
                },
                {
                    "id": "facet-scenario", "label": f"应用场景({scenario_count})",
                    "icon": "scenario", "children": [],
                },
                {
                    "id": "facet-instance", "label": f"ERP实例({instance_count})",
                    "icon": "instance", "children": instance_children,
                },
                {
                    "id": "facet-org", "label": f"融资企业({org_count})",
                    "icon": "org", "children": [],
                },
                {
                    "id": "facet-authscope", "label": f"授权项({authscope_count})",
                    "icon": "authscope", "children": [],
                },
            ]
        }

    async def get_scenario_indicators(self, scenario: str) -> List[Dict[str, Any]]:
        """按场景查询指标列表（含公式、SQL、数据来源），单次 SPARQL。"""
        YQL = "http://yql.example.com/ontology/credit-risk/"
        scenario_uri = "http://yql.example.com/ontology/scenario/" + scenario

        sparql = (
            "PREFIX yql: <" + YQL + ">\n"
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
            "SELECT ?rule ?ruleLabel ?indicator ?indicatorLabel ?formula ?sql "
            "?complexityTier ?notation ?table ?tableLabel WHERE {\n"
            "    ?rule a yql:CalculationRule ;\n"
            "          yql:appliedInScenario <" + scenario_uri + "> ;\n"
            "          yql:computesIndicator ?indicator ;\n"
            "          rdfs:label ?ruleLabel .\n"
            "    ?indicator rdfs:label ?indicatorLabel .\n"
            "    OPTIONAL { ?rule yql:hasFormula ?formula }\n"
            "    OPTIONAL { ?rule yql:hasSQL ?sql }\n"
            "    OPTIONAL { ?rule yql:complexityTier ?complexityTier }\n"
            "    OPTIONAL { ?rule skos:notation ?notation }\n"
            "    OPTIONAL { ?rule yql:usesTable ?table .\n"
            "              OPTIONAL { ?table rdfs:label ?tableLabel } }\n"
            "} ORDER BY ?indicatorLabel"
        )
        raw = await self._run_sparql(sparql)

        # Group by indicator (deduplicate, collect tables)
        ind_map: Dict[str, Dict[str, Any]] = {}
        for b in raw:
            ind_uri = b["indicator"]["value"]
            if ind_uri not in ind_map:
                ind_map[ind_uri] = {
                    "indicatorUri": ind_uri,
                    "indicatorLabel": b["indicatorLabel"]["value"],
                    "ruleUri": b["rule"]["value"],
                    "ruleLabel": b["ruleLabel"]["value"],
                    "formula": b.get("formula", {}).get("value", ""),
                    "sql": b.get("sql", {}).get("value", ""),
                    "complexityTier": b.get("complexityTier", {}).get("value", ""),
                    "notation": b.get("notation", {}).get("value", ""),
                    "tables": [],
                }
            # Add table if present and not duplicate
            table_uri = b.get("table", {}).get("value", "")
            if table_uri:
                existing_uris = {t["uri"] for t in ind_map[ind_uri]["tables"]}
                if table_uri not in existing_uris:
                    ind_map[ind_uri]["tables"].append({
                        "uri": table_uri,
                        "label": b.get("tableLabel", {}).get("value", ""),
                    })

        return list(ind_map.values())

    async def get_indicator_detail(self, entity_uri: str) -> Dict[str, Any]:
        """获取指标详情（四 Tab 数据）

        支持指标概念(Class)和计算规则(Individual)两种 URI。
        """
        YQL = "http://yql.example.com/ontology/credit-risk/"

        # Tab1: 它是什么 — 查概念的描述、主题、FIBO对标
        sparql_what = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?label ?comment ?subject ?closeMatch WHERE {{
            <{entity_uri}> rdfs:label ?label .
            OPTIONAL {{ <{entity_uri}> rdfs:comment ?comment }}
            OPTIONAL {{ <{entity_uri}> dcterms:subject ?subject }}
            OPTIONAL {{ <{entity_uri}> skos:closeMatch ?closeMatch }}
        }}
        """
        what_raw = await self._run_sparql(sparql_what)
        tab1 = {"label": "", "comment": "", "subjects": [], "closeMatches": [], "scenarios": []}
        for b in what_raw:
            if b.get("label", {}).get("value"):
                tab1["label"] = b["label"]["value"]
            if b.get("comment", {}).get("value"):
                tab1["comment"] = b["comment"]["value"]
            if b.get("subject", {}).get("value") and b["subject"]["value"] not in tab1["subjects"]:
                tab1["subjects"].append(b["subject"]["value"])
            if b.get("closeMatch", {}).get("value") and b["closeMatch"]["value"] not in tab1["closeMatches"]:
                tab1["closeMatches"].append(b["closeMatch"]["value"])

        # Tab1 补充: 适用场景（通过 Rule 关联）
        sparql_scenarios = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?scenario ?scenarioLabel WHERE {{
            ?rule yql:computesIndicator <{entity_uri}> ;
                  yql:appliedInScenario ?s .
            ?s rdfs:label ?scenarioLabel .
            BIND(?s AS ?scenario)
        }}
        """
        scenarios_raw = await self._run_sparql(sparql_scenarios)
        for b in scenarios_raw:
            tab1["scenarios"].append({
                "uri": b["scenario"]["value"],
                "label": b["scenarioLabel"]["value"],
            })

        # Tab2: 怎么算 — 查 Rule 的公式/SQL/表/字段/科目
        sparql_how = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?rule ?ruleLabel ?formula ?sql ?table ?tableLabel ?field ?fieldLabel ?account ?accountLabel WHERE {{
            ?rule yql:computesIndicator <{entity_uri}> .
            OPTIONAL {{ ?rule rdfs:label ?ruleLabel }}
            OPTIONAL {{ ?rule yql:hasFormula ?formula }}
            OPTIONAL {{ ?rule yql:hasSQL ?sql }}
            OPTIONAL {{ ?rule yql:usesTable ?table . ?table rdfs:label ?tableLabel }}
            OPTIONAL {{ ?rule yql:mapsToField ?field . ?field rdfs:label ?fieldLabel }}
            OPTIONAL {{ ?rule yql:usesAccount ?account . ?account rdfs:label ?accountLabel }}
        }}
        """
        how_raw = await self._run_sparql(sparql_how)
        tab2 = {"rule": "", "formula": "", "sql": "", "tables": [], "fields": [], "accounts": []}
        seen_tables, seen_fields, seen_accounts = set(), set(), set()
        for b in how_raw:
            if b.get("rule", {}).get("value") and not tab2["rule"]:
                tab2["rule"] = b["rule"]["value"]
                tab2["ruleLabel"] = b.get("ruleLabel", {}).get("value", "")
            if b.get("formula", {}).get("value") and not tab2["formula"]:
                tab2["formula"] = b["formula"]["value"]
            if b.get("sql", {}).get("value") and not tab2["sql"]:
                tab2["sql"] = b["sql"]["value"]
            if b.get("table", {}).get("value") and b["table"]["value"] not in seen_tables:
                seen_tables.add(b["table"]["value"])
                tab2["tables"].append({"uri": b["table"]["value"], "label": b.get("tableLabel", {}).get("value", "")})
            if b.get("field", {}).get("value") and b["field"]["value"] not in seen_fields:
                seen_fields.add(b["field"]["value"])
                tab2["fields"].append({"uri": b["field"]["value"], "label": b.get("fieldLabel", {}).get("value", "")})
            if b.get("account", {}).get("value") and b["account"]["value"] not in seen_accounts:
                seen_accounts.add(b["account"]["value"])
                tab2["accounts"].append({"uri": b["account"]["value"], "label": b.get("accountLabel", {}).get("value", "")})

        # Tab3: 看数据 — 查 IndicatorValue (forOrg is ObjectProperty → ApplicantOrg)
        sparql_data = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        SELECT ?valueUri ?org ?orgLabel ?period ?numericValue ?computedAt WHERE {{
            ?v a yql:IndicatorValue ;
               yql:ofIndicator <{entity_uri}> ;
               yql:forOrg ?org ;
               yql:forPeriod ?period ;
               yql:numericValue ?numericValue .
            OPTIONAL {{ ?v yql:computedAt ?computedAt }}
            OPTIONAL {{ ?org rdfs:label ?orgLabel }}
            BIND(STR(?v) AS ?valueUri)
        }} ORDER BY ?period ?org
        """
        data_raw = await self._run_sparql(sparql_data)
        tab3 = []
        for b in data_raw:
            org_uri = b["org"]["value"]
            org_label = b.get("orgLabel", {}).get("value", "")
            org_short = org_uri.split("/")[-1]
            tab3.append({
                "uri": b.get("valueUri", {}).get("value", ""),
                "org": org_label or org_short,
                "orgUri": org_uri,
                "period": b["period"]["value"],
                "value": b["numericValue"]["value"],
                "computedAt": b.get("computedAt", {}).get("value", ""),
            })

        # Tab4: 关联指标 — 同主题 + 共享字段
        sparql_related = f"""
        PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        SELECT DISTINCT ?related ?relatedLabel ?reason WHERE {{
            {{
                ?related rdfs:subClassOf+ yql:Indicator ;
                         dcterms:subject ?subj .
                <{entity_uri}> dcterms:subject ?subj .
                FILTER(?related != <{entity_uri}>)
                ?related rdfs:label ?relatedLabel .
                BIND("同主题" AS ?reason)
            }} UNION {{
                ?rule1 yql:computesIndicator <{entity_uri}> ; yql:mapsToField ?sharedField .
                ?rule2 yql:computesIndicator ?related ; yql:mapsToField ?sharedField .
                FILTER(?related != <{entity_uri}>)
                ?related rdfs:label ?relatedLabel .
                BIND("共享数据源" AS ?reason)
            }}
        }} LIMIT 30
        """
        related_raw = await self._run_sparql(sparql_related)
        tab4 = {"sameTopic": [], "sharedSource": []}
        for b in related_raw:
            item = {"uri": b["related"]["value"], "label": b["relatedLabel"]["value"]}
            reason = b["reason"]["value"]
            if reason == "同主题" and item not in tab4["sameTopic"]:
                tab4["sameTopic"].append(item)
            elif reason == "共享数据源" and item not in tab4["sharedSource"]:
                tab4["sharedSource"].append(item)

        return {
            "uri": entity_uri,
            "tab1": tab1,
            "tab2": tab2,
            "tab3": tab3,
            "tab4": tab4,
        }

    async def search_business(self, q: str, facet: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """业务化搜索：同时搜索 label/altLabel/notation，按 facet 过滤类型"""
        YQL = "http://yql.example.com/ontology/credit-risk/"
        type_filter = ""
        facet_type_map = {
            "indicator": f"{YQL}Indicator",
            "rule": f"{YQL}CalculationRule",
            "value": f"{YQL}IndicatorValue",
            "datasource": f"{YQL}NCCTable",
            "field": f"{YQL}NCCField",
            "account": f"{YQL}AccountCode",
            "scenario": f"{YQL}Scenario",
            "org": f"{YQL}ApplicantOrg",
            "authscope": f"{YQL}AuthorizationScope",
        }
        if facet and facet in facet_type_map:
            if facet == "indicator":
                type_filter = f"?entity rdfs:subClassOf+ <{facet_type_map[facet]}> ."
            else:
                type_filter = f"?entity a <{facet_type_map[facet]}> ."

        sparql = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        SELECT DISTINCT ?entity ?label ?altLabel ?indicatorType ?individualType WHERE {{
            {type_filter}
            OPTIONAL {{ ?entity rdfs:subClassOf+ ?indicatorType . FILTER(?indicatorType = <{YQL}Indicator> || ?indicatorType = <{YQL}RatioIndicator> || ?indicatorType = <{YQL}AmountIndicator> || ?indicatorType = <{YQL}CountIndicator>) }}
            OPTIONAL {{ ?entity a ?individualType . FILTER(!STRSTARTS(STR(?individualType), "http://www.w3.org/")) }}
            OPTIONAL {{ ?entity rdfs:label ?label }}
            OPTIONAL {{ ?entity skos:altLabel ?altLabel }}
            FILTER(
                !STRSTARTS(STR(?entity), "http://www.w3.org/")
                && (
                    (?label && CONTAINS(LCASE(STR(?label)), LCASE("{q}")))
                    || (?altLabel && CONTAINS(LCASE(STR(?altLabel)), LCASE("{q}")))
                    || CONTAINS(LCASE(STR(?entity)), LCASE("{q}"))
                )
            )
        }} LIMIT {limit}
        """
        results_raw = await self._run_sparql(sparql)
        # 去重
        seen = {}
        for b in results_raw:
            uri = b["entity"]["value"]
            if uri not in seen:
                lbl = b.get("label", {}).get("value", "")
                alt = b.get("altLabel", {}).get("value", "")
                # 判断分面：如果有 indicatorType 则是指标，否则用 individualType
                ind_type = b.get("indicatorType", {}).get("value", "")
                indiv_type = b.get("individualType", {}).get("value", "")
                if ind_type:
                    facet_id = "indicator"
                else:
                    facet_id = self._type_to_facet(indiv_type)
                seen[uri] = {"uri": uri, "type": ind_type or indiv_type, "label": lbl or alt, "facet": facet_id}
        return list(seen.values())

    def _type_to_facet(self, type_uri: str) -> str:
        """将类型 URI 映射为分面标识"""
        YQL = "http://yql.example.com/ontology/credit-risk/"
        short = type_uri.split("#")[-1] or type_uri.split("/")[-1]
        mapping = {
            "Indicator": "indicator", "RatioIndicator": "indicator",
            "AmountIndicator": "indicator", "CountIndicator": "indicator",
            "CalculationRule": "rule", "IndicatorValue": "value",
            "NCCTable": "datasource", "NCCField": "field",
            "AccountCode": "account", "Scenario": "scenario",
            "ApplicantOrg": "org", "AuthorizationScope": "authscope",
        }
        return mapping.get(short, "other")

    # ─── 私有方法 ───────────────────────────────────────────────

    async def _run_sparql(self, sparql: str) -> List[Dict]:
        """执行 SPARQL 查询并返回 bindings 列表"""
        session = await self.client._get_async_session()
        resp = await session.post(
            f"{self.client.endpoint}/repositories/{self.client.repo}",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
        return resp.json().get("results", {}).get("bindings", [])

    def _parse_entity_results(self, data: dict) -> List[Dict[str, Any]]:
        """解析 SPARQL 实体查询结果"""
        results = []
        for binding in data.get("results", {}).get("bindings", []):
            results.append({
                "uri": binding.get("entity", {}).get("value", ""),
                "type": binding.get("type", {}).get("value", ""),
                "label": binding.get("label", {}).get("value", ""),
            })
        return results

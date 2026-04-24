"""将 ERPInstance 本体数据和默认 NCC 实例写入 GraphDB。

执行内容：
1. 插入 ERPInstance 类定义及属性声明
2. 插入默认 NCC 实例个体
3. 为用友融资企业添加 linkedToInstance 关联
4. 验证查询

用法：
    python scripts/seed_erp_instance.py
"""

import httpx
import asyncio
import sys

GRAPHDB_ENDPOINT = "http://localhost:7200"
GRAPHDB_REPO = "loanfibo"
YQL = "http://yql.example.com/ontology/credit-risk/"
INST_NS = "http://yql.example.com/ontology/erp-instance/"
ORG_NS = "http://yql.example.com/ontology/applicant-org/"


async def sparql_update(sparql: str, desc: str = ""):
    """执行 SPARQL UPDATE"""
    url = f"{GRAPHDB_ENDPOINT}/repositories/{GRAPHDB_REPO}/statements"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            content=sparql,
            headers={"Content-Type": "application/sparql-update"},
        )
        status = "OK" if resp.status_code == 204 else f"FAIL({resp.status_code})"
        print(f"  [{status}] {desc}")
        if resp.status_code not in (200, 204):
            print(f"    Response: {resp.text[:200]}")
        return resp.status_code in (200, 204)


async def sparql_query(sparql: str, desc: str = ""):
    """执行 SPARQL QUERY"""
    url = f"{GRAPHDB_ENDPOINT}/repositories/{GRAPHDB_REPO}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            print(f"  [OK] {desc} → {len(bindings)} 条结果")
            return bindings
        else:
            print(f"  [FAIL({resp.status_code})] {desc}")
            return []


async def main():
    print("=" * 60)
    print("Step 1: 插入 ERPInstance 类及属性定义")
    print("=" * 60)

    # 1. 插入 ERPInstance 类定义
    await sparql_update(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{
        yql:ERPInstance a owl:Class ;
            rdfs:label "ERP系统实例"@zh ;
            rdfs:comment "企业使用的ERP系统实例（如用友NCC），是融资企业→指标→SQL链路的桥梁。"@zh .

        yql:instanceCode a owl:DatatypeProperty ;
            rdfs:label "实例编码"@zh ;
            rdfs:domain yql:ERPInstance ;
            rdfs:range xsd:string .

        yql:instanceName a owl:DatatypeProperty ;
            rdfs:label "实例名称"@zh ;
            rdfs:domain yql:ERPInstance ;
            rdfs:range xsd:string .

        yql:erpAgentDatasource a owl:DatatypeProperty ;
            rdfs:label "ERP代理数据源标识"@zh ;
            rdfs:domain yql:ERPInstance ;
            rdfs:range xsd:string .

        yql:orgKeyField a owl:DatatypeProperty ;
            rdfs:label "组织主键字段"@zh ;
            rdfs:domain yql:ERPInstance ;
            rdfs:range xsd:string .

        yql:linkedToInstance a owl:ObjectProperty ;
            rdfs:label "关联ERP实例"@zh ;
            rdfs:domain yql:ApplicantOrg ;
            rdfs:range yql:ERPInstance .
    }}
    """, "ERPInstance 类定义 + linkedToInstance 属性")

    print()
    print("=" * 60)
    print("Step 2: 插入默认 NCC 实例个体")
    print("=" * 60)

    await sparql_update(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX inst: <{INST_NS}>
    INSERT DATA {{
        inst:NCC_Instance a yql:ERPInstance ;
            rdfs:label "用友NCC实例"@zh ;
            yql:instanceCode "NCC" ;
            yql:instanceName "用友NCC" ;
            yql:erpAgentDatasource "NCC" ;
            yql:orgKeyField "PK_ORG" .
    }}
    """, "NCC_Instance 默认实例")

    print()
    print("=" * 60)
    print("Step 3: 为用友融资企业添加 linkedToInstance 关联")
    print("=" * 60)

    # 先查用友企业的 URI
    yonyou_bindings = await sparql_query(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?org ?name WHERE {{
        ?org a yql:ApplicantOrg ;
             rdfs:label ?name .
        FILTER(CONTAINS(?name, "用友"))
    }}
    """, "查找用友融资企业")

    if yonyou_bindings:
        org_uri = yonyou_bindings[0]["org"]["value"]
        org_name = yonyou_bindings[0]["name"]["value"]
        print(f"  找到用友企业: {org_name} → {org_uri}")

        # 检查是否已关联
        existing = await sparql_query(f"""
        PREFIX yql: <{YQL}>
        SELECT ?instance WHERE {{
            <{org_uri}> yql:linkedToInstance ?instance .
        }} LIMIT 1
        """, "检查已有关联")

        if not existing:
            await sparql_update(f"""
            PREFIX yql: <{YQL}>
            INSERT DATA {{
                <{org_uri}> yql:linkedToInstance <{INST_NS}NCC_Instance> .
            }}
            """, f"关联 {org_name} → NCC_Instance")
        else:
            print(f"  已存在关联: {existing[0]['instance']['value']}, 跳过")
    else:
        print("  未找到用友企业，跳过关联")

    # 也为所有已有的 ApplicantOrg 添加默认关联（如果没有的话）
    all_orgs = await sparql_query(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?org ?name WHERE {{
        ?org a yql:ApplicantOrg ;
             rdfs:label ?name .
        FILTER NOT EXISTS {{ ?org yql:linkedToInstance ?inst }}
    }}
    """, "查找未关联实例的企业")

    if all_orgs:
        for b in all_orgs:
            org_uri = b["org"]["value"]
            org_name = b["name"]["value"]
            await sparql_update(f"""
            PREFIX yql: <{YQL}>
            INSERT DATA {{
                <{org_uri}> yql:linkedToInstance <{INST_NS}NCC_Instance> .
            }}
            """, f"关联 {org_name} → NCC_Instance")

    print()
    print("=" * 60)
    print("Step 4: 验证查询")
    print("=" * 60)

    # 验证 ERPInstance 数量
    await sparql_query(f"""
    PREFIX yql: <{YQL}>
    SELECT (COUNT(?i) AS ?count) WHERE {{
        ?i a yql:ERPInstance .
    }}
    """, "ERPInstance 数量")

    # 验证完整链路：融资企业 → 实例 → 指标SQL
    await sparql_query(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?orgName ?instanceCode ?datasource (COUNT(?rule) AS ?ruleCount) WHERE {{
        ?org a yql:ApplicantOrg ;
             rdfs:label ?orgName ;
             yql:linkedToInstance ?instance .
        ?instance a yql:ERPInstance ;
                  yql:instanceCode ?instanceCode ;
                  yql:erpAgentDatasource ?datasource .
        ?rule a yql:CalculationRule ;
              yql:hasSQL ?sql .
    }} GROUP BY ?orgName ?instanceCode ?datasource
    """, "融资企业→实例→指标SQL 完整链路")

    # 验证场景分布
    await sparql_query(f"""
    PREFIX yql: <{YQL}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?scenario (COUNT(?rule) AS ?count) WHERE {{
        ?rule a yql:CalculationRule ;
              yql:appliedInScenario ?scenarioURI ;
              yql:hasSQL ?sql .
        BIND(REPLACE(STR(?scenarioURI), ".*/", "") AS ?scenario)
    }} GROUP BY ?scenario ORDER BY DESC(?count)
    """, "指标SQL按场景分布")

    print()
    print("Done! ERPInstance 数据已写入 GraphDB。")


if __name__ == "__main__":
    asyncio.run(main())

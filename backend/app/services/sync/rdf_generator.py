"""RDF 三元组生成器 - 三层三元组生成（类实例/属性/外键/溯源）"""
from typing import Any, Dict, List, Optional

from loguru import logger


# 命名空间定义
LOANFIBO_NS = "http://loanfibo.org/ontology/"
PROV_NS = "http://www.w3.org/ns/prov#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"


class RDFGenerator:
    """RDF 三元组生成服务

    三层结构：
    1. 类实例层：表 → FIBO 类实例（如 loanfibo:Company_001）
    2. 属性映射层：字段 → DatatypeProperty / 外键 → ObjectProperty
    3. 溯源层：数据来源溯源三元组

    URI 格式：
    - 类实例: urn:loanfibo:source:{proj}:{table}:{id}
    - 字段属性: urn:loanfibo:source:{proj}:{table}:{field}
    - 外键属性: urn:loanfibo:source:{proj}:{table}:{field}_fk
    - proj_ext_uri: {namespace_prefix}:{table}:{field}
    """

    def __init__(self, namespace_prefix: str = "loanfibo", project_code: str = "bipv5"):
        self.namespace_prefix = namespace_prefix
        self.project_code = project_code

    def generate_three_layer_triples(
        self,
        mappings: List[Dict[str, Any]],
        foreign_keys: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """生成三层 RDF 三元组

        Args:
            mappings: 映射数据列表，每项包含 table_name, fibo_class_uri, fields
            foreign_keys: 外键关系列表

        Returns:
            N-Triples 格式的三元组列表
        """
        triples = []

        for mapping in mappings:
            table_name = mapping.get("table_name", "")
            fibo_class_uri = mapping.get("fibo_class_uri", "")
            fields = mapping.get("fields", [])

            if not fibo_class_uri:
                continue

            # 第1层：类实例三元组
            triples.extend(self._generate_class_instance_triples(table_name, fibo_class_uri))

            # 第2层：属性映射三元组
            triples.extend(self._generate_property_triples(table_name, fibo_class_uri, fields))

            # 第2层：外键 ObjectProperty 三元组
            if foreign_keys:
                table_fks = [fk for fk in foreign_keys if fk.get("source_table") == table_name]
                triples.extend(self._generate_foreign_key_triples(table_name, table_fks))

            # 第3层：溯源三元组
            triples.extend(self._generate_provenance_triples(table_name, fibo_class_uri))

        logger.info(f"RDF 三元组生成完成: {len(triples)} 条")
        return triples

    def generate_turtle(self, triples: List[str]) -> str:
        """将 N-Triples 转换为 Turtle 格式"""
        if not triples:
            return ""

        # 收集使用的命名空间
        prefix_lines = [
            f"@prefix loanfibo: <{LOANFIBO_NS}> .",
            f"@prefix prov: <{PROV_NS}> .",
            f"@prefix rdf: <{RDF_NS}> .",
            f"@prefix rdfs: <{RDFS_NS}> .",
            f"@prefix xsd: <{XSD_NS}> .",
            f"@prefix {self.namespace_prefix}: <urn:loanfibo:source:{self.project_code}:> .",
            "",
        ]

        # 直接输出 N-Triples（简化版）
        return "\n".join(prefix_lines + triples)

    # ─── 私有方法 ───────────────────────────────────────────────

    def _make_instance_uri(self, table_name: str, row_id: str = "{id}") -> str:
        """构造类实例 URI"""
        return f"urn:loanfibo:source:{self.project_code}:{table_name}:{row_id}"

    def _make_field_uri(self, table_name: str, field_name: str) -> str:
        """构造源字段 URI（第2层占位）"""
        return f"urn:loanfibo:source:{self.project_code}:{table_name}:{field_name}"

    def _make_proj_ext_uri(self, table_name: str, field_name: str) -> str:
        """构造 proj_ext_uri 命名空间"""
        return f"{self.namespace_prefix}:{table_name}:{field_name}"

    def _generate_class_instance_triples(self, table_name: str, fibo_class_uri: str) -> List[str]:
        """第1层：生成类实例三元组"""
        instance_uri = self._make_instance_uri(table_name)
        return [
            f'<{instance_uri}> <{RDF_NS}type> <{fibo_class_uri}> .',
            f'<{instance_uri}> <{RDFS_NS}label> "{table_name} instance" .',
        ]

    def _generate_property_triples(
        self,
        table_name: str,
        fibo_class_uri: str,
        fields: List[Dict[str, Any]],
    ) -> List[str]:
        """第2层：生成 DatatypeProperty 映射三元组"""
        triples = []
        instance_uri = self._make_instance_uri(table_name)

        for field in fields:
            field_name = field.get("field_name", "")
            fibo_property_uri = field.get("fibo_property_uri", "")

            if not fibo_property_uri:
                continue

            # 源字段 URI（第2层占位）
            field_uri = self._make_field_uri(table_name, field_name)
            proj_ext_uri = self._make_proj_ext_uri(table_name, field_name)

            # DatatypeProperty 映射
            triples.append(
                f'<{instance_uri}> <{fibo_property_uri}> <{field_uri}> .'
            )
            # proj_ext_uri 命名空间标注
            triples.append(
                f'<{field_uri}> <{LOANFIBO_NS}projExtUri> "{proj_ext_uri}" .'
            )

        return triples

    def _generate_foreign_key_triples(
        self,
        table_name: str,
        foreign_keys: List[Dict[str, Any]],
    ) -> List[str]:
        """第2层：生成外键 ObjectProperty 三元组"""
        triples = []
        instance_uri = self._make_instance_uri(table_name)

        for fk in foreign_keys:
            source_column = fk.get("source_column", "")
            target_table = fk.get("target_table", "")
            target_column = fk.get("target_column", "")

            # 外键 URI
            fk_uri = self._make_field_uri(table_name, f"{source_column}_fk")
            target_uri = self._make_instance_uri(target_table)

            # ObjectProperty 映射
            fk_property = f"{LOANFIBO_NS}references{target_table.title().replace('_', '')}"
            triples.append(
                f'<{instance_uri}> <{fk_property}> <{target_uri}> .'
            )
            # 溯源：外键来源
            triples.append(
                f'<{fk_uri}> <{LOANFIBO_NS}sourceColumn> "{source_column}" .'
            )
            triples.append(
                f'<{fk_uri}> <{LOANFIBO_NS}targetColumn> "{target_column}" .'
            )

        return triples

    def _generate_provenance_triples(
        self,
        table_name: str,
        fibo_class_uri: str,
    ) -> List[str]:
        """第3层：生成溯源三元组"""
        instance_uri = self._make_instance_uri(table_name)
        source_entity = f"urn:loanfibo:source:{self.project_code}"

        return [
            f'<{instance_uri}> <{PROV_NS}wasDerivedFrom> <{source_entity}> .',
            f'<{source_entity}> <{PROV_NS}wasAttributedTo> "{self.project_code}" .',
        ]

"""TTL 语法检核服务 - 使用 rdflib 解析 TTL 文件，验证语法并统计类/属性数量"""
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class TTLValidationResult:
    """TTL 检核结果"""
    valid: bool
    error_message: Optional[str] = None
    class_count: int = 0
    property_count: int = 0


def validate_ttl(content: str, file_name: str = "unknown.ttl") -> TTLValidationResult:
    """验证 TTL 文件语法正确性

    Args:
        content: TTL 文件内容字符串
        file_name: 文件名（用于日志）

    Returns:
        TTLValidationResult 包含是否有效、错误信息、类/属性数量
    """
    from rdflib import Graph, OWL, RDF
    from rdflib.namespace import RDFS

    try:
        g = Graph()
        g.parse(data=content, format="turtle")

        # 统计类数量
        class_count = 0
        for _ in g.subjects(RDF.type, OWL.Class):
            class_count += 1

        # 统计属性数量（ObjectProperty + DatatypeProperty）
        property_count = 0
        for _ in g.subjects(RDF.type, OWL.ObjectProperty):
            property_count += 1
        for _ in g.subjects(RDF.type, OWL.DatatypeProperty):
            property_count += 1

        # 也统计 rdfs:subClassOf 关系中出现的类（有些类只有 subClassOf 没有 a owl:Class）
        for s in g.subjects(RDFS.subClassOf, None):
            if (s, RDF.type, OWL.Class) not in g:
                class_count += 1

        logger.info(
            f"TTL 检核通过: {file_name}, "
            f"class_count={class_count}, property_count={property_count}"
        )

        return TTLValidationResult(
            valid=True,
            class_count=class_count,
            property_count=property_count,
        )

    except Exception as e:
        error_msg = str(e)
        # 截断过长的错误信息
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        logger.warning(f"TTL 检核失败: {file_name} - {error_msg}")
        return TTLValidationResult(
            valid=False,
            error_message=error_msg,
        )

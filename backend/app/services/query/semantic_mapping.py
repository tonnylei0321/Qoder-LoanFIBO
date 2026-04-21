"""RDF到SQL语义映射层"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class JoinDefinition:
    """JOIN关系定义"""

    from_table: str
    to_table: str
    from_column: str
    to_column: str
    join_type: str = "INNER"


@dataclass
class TableMapping:
    """表映射定义"""

    table_name: str
    concept: str
    allowed_columns: List[str] = field(default_factory=list)


class SemanticMapping:
    """语义映射定义"""

    def __init__(
        self,
        concept_to_table: Dict[str, str],
        relation_to_join: Dict[str, JoinDefinition],
        table_mappings: Dict[str, TableMapping],
    ):
        self.concept_to_table = concept_to_table
        self.relation_to_join = relation_to_join
        self.table_mappings = table_mappings

    def resolve_concept(self, concept: str) -> Optional[str]:
        return self.concept_to_table.get(concept)

    def resolve_slot(self, slot_name: str, concept: str) -> Optional[str]:
        key = f"{concept}.{slot_name}"
        return self.concept_to_table.get(key)

    def get_join(self, relation: str) -> Optional[JoinDefinition]:
        return self.relation_to_join.get(relation)

    def is_column_allowed(self, table_name: str, column_name: str) -> bool:
        mapping = self.table_mappings.get(table_name)
        if mapping is None:
            return False
        return column_name in mapping.allowed_columns

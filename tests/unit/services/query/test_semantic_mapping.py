"""语义映射单元测试"""
import pytest
from backend.app.services.query.semantic_mapping import SemanticMapping, JoinDefinition, TableMapping


class TestSemanticMapping:
    @pytest.fixture
    def mapping(self):
        return SemanticMapping(
            concept_to_table={
                "loan:LoanContract": "bd_loan_contract",
                "loan:LoanContract.loanAmount": "bd_loan_contract.loan_amount",
                "loan:LoanContract.borrower": "bd_loan_contract.borrower_id",
                "loan:LoanContract.status": "bd_loan_contract.contract_status",
            },
            relation_to_join={
                "loan:hasBorrower": JoinDefinition(
                    from_table="bd_loan_contract",
                    to_table="bd_borrower",
                    from_column="borrower_id",
                    to_column="id",
                    join_type="INNER",
                ),
            },
            table_mappings={
                "bd_loan_contract": TableMapping(
                    table_name="bd_loan_contract",
                    concept="loan:LoanContract",
                    allowed_columns=["loan_amount", "borrower_id", "contract_status"],
                ),
                "bd_borrower": TableMapping(
                    table_name="bd_borrower",
                    concept="loan:Borrower",
                    allowed_columns=["id", "name", "credit_score"],
                ),
            },
        )

    def test_resolve_concept_to_table(self, mapping):
        table = mapping.resolve_concept("loan:LoanContract")
        assert table == "bd_loan_contract"

    def test_resolve_slot_to_column(self, mapping):
        column = mapping.resolve_slot("loanAmount", "loan:LoanContract")
        assert column == "bd_loan_contract.loan_amount"

    def test_resolve_unknown_concept(self, mapping):
        table = mapping.resolve_concept("unknown:Concept")
        assert table is None

    def test_resolve_unknown_slot(self, mapping):
        column = mapping.resolve_slot("nonExistent", "loan:LoanContract")
        assert column is None

    def test_get_join_definition(self, mapping):
        join = mapping.get_join("loan:hasBorrower")
        assert join is not None
        assert join.from_table == "bd_loan_contract"
        assert join.to_table == "bd_borrower"

    def test_is_column_allowed(self, mapping):
        assert mapping.is_column_allowed("bd_loan_contract", "loan_amount") is True
        assert mapping.is_column_allowed("bd_loan_contract", "drop_table") is False

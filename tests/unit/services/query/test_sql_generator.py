"""SQL生成器单元测试"""
import pytest
from backend.app.services.query.sql_generator import SQLGenerator, SecurityError
from backend.app.services.query.semantic_mapping import SemanticMapping, JoinDefinition, TableMapping


@pytest.fixture
def mapping():
    return SemanticMapping(
        concept_to_table={
            "loan:LoanContract": "bd_loan_contract",
            "loan:LoanContract.loanAmount": "bd_loan_contract.loan_amount",
            "loan:LoanContract.status": "bd_loan_contract.contract_status",
        },
        relation_to_join={
            "loan:hasBorrower": JoinDefinition(
                from_table="bd_loan_contract", to_table="bd_borrower",
                from_column="borrower_id", to_column="id"
            ),
        },
        table_mappings={
            "bd_loan_contract": TableMapping(
                table_name="bd_loan_contract", concept="loan:LoanContract",
                allowed_columns=["loan_amount", "contract_status", "borrower_id"]
            ),
        }
    )


@pytest.fixture
def generator(mapping):
    return SQLGenerator(mapping=mapping)


class TestSQLGenerator:
    def test_generate_simple_query(self, generator):
        sql, params = generator.generate_safe(
            table_name="bd_loan_contract",
            select_columns=["loan_amount", "contract_status"],
            conditions={"loanAmount": 1000000},
        )
        assert "SELECT" in sql
        assert "bd_loan_contract" in sql
        assert "%s" in sql
        assert 1000000 in params

    def test_reject_unknown_slot(self, generator):
        with pytest.raises(SecurityError, match="未定义的槽位名"):
            generator.generate_safe(
                table_name="bd_loan_contract",
                select_columns=["loan_amount"],
                conditions={"evil_injection": "drop table"},
            )

    def test_reject_sql_injection_in_column(self, generator):
        with pytest.raises(SecurityError):
            generator.generate_safe(
                table_name="bd_loan_contract",
                select_columns=["; DROP TABLE bd_loan_contract;--"],
                conditions={},
            )

    def test_validate_sql_safety_rejects_insert(self, generator):
        with pytest.raises(SecurityError, match="危险操作"):
            generator._validate_sql_safety("INSERT INTO users VALUES (1)")

    def test_validate_sql_safety_rejects_semicolon_injection(self, generator):
        with pytest.raises(SecurityError):  # DROP keyword or semicolon both raise
            generator._validate_sql_safety("SELECT * FROM t; SELECT * FROM t2")

    def test_quote_identifier(self, generator):
        assert generator._quote_identifier("loan_amount") == '"loan_amount"'
        assert generator._quote_identifier('col"with"quote') == '"col""with""quote"'

"""RDF 三元组生成器单元测试"""
import pytest

from backend.app.services.sync.rdf_generator import RDFGenerator, LOANFIBO_NS, RDF_NS, RDFS_NS, PROV_NS


@pytest.fixture
def generator():
    return RDFGenerator(namespace_prefix="loanfibo", project_code="bipv5")


class TestRDFGeneratorClassInstance:
    def test_generate_class_instance_triples(self, generator):
        """测试第1层类实例三元组生成"""
        triples = generator._generate_class_instance_triples(
            "t_company", "http://loanfibo.org/ontology/Corporation"
        )
        assert len(triples) == 2
        assert "Corporation" in triples[0]
        assert "t_company instance" in triples[1]
        assert RDF_NS in triples[0]
        assert RDFS_NS in triples[1]

    def test_instance_uri_format(self, generator):
        """测试 URI 格式: urn:loanfibo:source:{proj}:{table}:{id}"""
        uri = generator._make_instance_uri("t_company")
        assert uri == "urn:loanfibo:source:bipv5:t_company:{id}"


class TestRDFGeneratorProperty:
    def test_generate_property_triples(self, generator):
        """测试第2层属性映射三元组"""
        fields = [
            {"field_name": "company_name", "fibo_property_uri": "http://loanfibo.org/ontology/hasName"},
            {"field_name": "reg_capital", "fibo_property_uri": "http://loanfibo.org/ontology/hasCapital"},
            {"field_name": "no_mapping", "fibo_property_uri": ""},  # 应跳过
        ]
        triples = generator._generate_property_triples(
            "t_company", "http://loanfibo.org/ontology/Corporation", fields
        )
        # 2个有效映射 x (映射三元组 + proj_ext_uri标注) = 4
        assert len(triples) == 4
        assert any("hasName" in t for t in triples)
        assert any("hasCapital" in t for t in triples)
        assert any("projExtUri" in t for t in triples)

    def test_proj_ext_uri_format(self, generator):
        """测试 proj_ext_uri 格式: {prefix}:{table}:{field}"""
        uri = generator._make_proj_ext_uri("t_company", "company_name")
        assert uri == "loanfibo:t_company:company_name"


class TestRDFGeneratorForeignKey:
    def test_generate_foreign_key_triples(self, generator):
        """测试外键 ObjectProperty 三元组"""
        fks = [
            {
                "source_column": "industry_id",
                "target_table": "t_industry",
                "target_column": "id",
            }
        ]
        triples = generator._generate_foreign_key_triples("t_company", fks)
        # 1个外键 → 3条三元组(ObjectProperty + sourceColumn + targetColumn)
        assert len(triples) == 3
        assert any("references" in t for t in triples)
        assert any("industry_id" in t for t in triples)


class TestRDFGeneratorProvenance:
    def test_generate_provenance_triples(self, generator):
        """测试第3层溯源三元组"""
        triples = generator._generate_provenance_triples(
            "t_company", "http://loanfibo.org/ontology/Corporation"
        )
        assert len(triples) == 2
        assert any("wasDerivedFrom" in t for t in triples)
        assert any("wasAttributedTo" in t for t in triples)


class TestRDFGeneratorFull:
    def test_generate_three_layer_triples(self, generator):
        """测试完整三层三元组生成"""
        mappings = [
            {
                "table_name": "t_company",
                "fibo_class_uri": "http://loanfibo.org/ontology/Corporation",
                "fields": [
                    {"field_name": "name", "fibo_property_uri": "http://loanfibo.org/ontology/hasName"},
                ],
            }
        ]
        triples = generator.generate_three_layer_triples(mappings)
        # 第1层2条 + 第2层2条(属性映射+proj_ext) + 第3层2条 = 6条
        assert len(triples) == 6

    def test_generate_with_no_fibo_class(self, generator):
        """测试无 FIBO 类的映射被跳过"""
        mappings = [
            {"table_name": "t_unknown", "fibo_class_uri": "", "fields": []}
        ]
        triples = generator.generate_three_layer_triples(mappings)
        assert len(triples) == 0

    def test_generate_turtle(self, generator):
        """测试 Turtle 格式输出"""
        triples = ["<s> <p> <o> ."]
        turtle = generator.generate_turtle(triples)
        assert "@prefix loanfibo:" in turtle
        assert "@prefix prov:" in turtle
        assert "<s> <p> <o> ." in turtle

    def test_generate_turtle_empty(self, generator):
        """测试空三元组列表"""
        turtle = generator.generate_turtle([])
        assert turtle == ""

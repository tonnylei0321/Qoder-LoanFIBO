"""图谱浏览器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.sync.graph_explorer import GraphExplorer


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.endpoint = "http://localhost:7200"
    client.repo = "loanfibo"
    return client


@pytest.fixture
def explorer(mock_client):
    return GraphExplorer(mock_client)


@pytest.fixture
def sample_sparql_results():
    return {
        "results": {
            "bindings": [
                {
                    "entity": {"value": "http://loanfibo.org/ontology/Company_001"},
                    "type": {"value": "http://loanfibo.org/ontology/Corporation"},
                    "label": {"value": "测试公司"},
                },
                {
                    "entity": {"value": "http://loanfibo.org/ontology/Company_002"},
                    "type": {"value": "http://loanfibo.org/ontology/Corporation"},
                    "label": {"value": "另一公司"},
                },
            ]
        }
    }


class TestGraphExplorerListEntities:
    @pytest.mark.asyncio
    async def test_list_entities(self, explorer, mock_client, sample_sparql_results):
        """测试列出实体"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_sparql_results
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_client._get_async_session = AsyncMock(return_value=mock_session)

        results = await explorer.list_entities()
        assert len(results) == 2
        assert results[0]["uri"] == "http://loanfibo.org/ontology/Company_001"
        assert results[0]["label"] == "测试公司"

    @pytest.mark.asyncio
    async def test_list_entities_with_type_filter(self, explorer, mock_client, sample_sparql_results):
        """测试按类型过滤实体"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_sparql_results
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_client._get_async_session = AsyncMock(return_value=mock_session)

        results = await explorer.list_entities(entity_type="http://loanfibo.org/ontology/Corporation")
        # 验证 SPARQL 查询包含类型过滤
        call_args = mock_session.post.call_args
        sparql_query = call_args[1]["data"]["query"]
        assert "Corporation" in sparql_query


class TestGraphExplorerGetEntity:
    @pytest.mark.asyncio
    async def test_get_entity_detail(self, explorer, mock_client):
        """测试获取实体详情"""
        detail_results = {
            "results": {
                "bindings": [
                    {
                        "property": {"value": "http://loanfibo.org/ontology/hasName"},
                        "value": {"value": "测试公司"},
                        "valueType": {"value": "literal"},
                    },
                    {
                        "property": {"value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                        "value": {"value": "http://loanfibo.org/ontology/Corporation"},
                        "valueType": {"value": "uri"},
                    },
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = detail_results
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_client._get_async_session = AsyncMock(return_value=mock_session)

        result = await explorer.get_entity("http://loanfibo.org/ontology/Company_001")
        assert result["uri"] == "http://loanfibo.org/ontology/Company_001"
        # 系统属性(w3.org)被过滤
        assert len(result["properties"]) == 1
        assert result["properties"][0]["property"] == "http://loanfibo.org/ontology/hasName"


class TestGraphExplorerSearch:
    @pytest.mark.asyncio
    async def test_search_entities(self, explorer, mock_client, sample_sparql_results):
        """测试搜索实体"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_sparql_results
        mock_response.raise_for_status = MagicMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_client._get_async_session = AsyncMock(return_value=mock_session)

        results = await explorer.search_entities("Company")
        assert len(results) == 2

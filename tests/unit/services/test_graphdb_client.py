"""GraphDB双模式客户端单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.graphdb_client import GraphDBClient


@pytest.fixture
def client():
    return GraphDBClient(endpoint="http://localhost:7200", repo="test-repo")


class TestGraphDBClientInit:
    def test_create_client(self, client):
        assert client.endpoint == "http://localhost:7200"
        assert client.repo == "test-repo"


class TestGraphDBClientAsync:
    @pytest.mark.asyncio
    async def test_query_rules_async(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "bindings": [
                    {
                        "rule": {"value": "http://loanfibo.org/rule1"},
                        "table": {"value": "bd_loan_contract"},
                        "field": {"value": "loan_amount"},
                        "target": {"value": "loan:LoanAmount"},
                    }
                ]
            }
        }

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.aclose = AsyncMock()
        client._async_session = mock_session

        results = await client.query_rules(industry="credit")
        assert len(results) == 1
        assert results[0]["table"] == "bd_loan_contract"

    @pytest.mark.asyncio
    async def test_query_rules_empty(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": {"bindings": []}}

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.aclose = AsyncMock()
        client._async_session = mock_session

        results = await client.query_rules()
        assert results == []


class TestGraphDBClientSync:
    def test_query_rules_sync(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "bindings": [
                    {
                        "rule": {"value": "http://loanfibo.org/rule2"},
                        "table": {"value": "bd_borrower"},
                        "field": {"value": "name"},
                        "target": {"value": "fibo:LegalEntityName"},
                    }
                ]
            }
        }

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        client._sync_session = mock_session

        results = client.query_rules_sync()
        assert len(results) == 1
        assert results[0]["table"] == "bd_borrower"


class TestGraphDBClientParse:
    def test_parse_sparql_results(self, client):
        data = {
            "results": {
                "bindings": [
                    {
                        "rule": {"value": "r1"},
                        "table": {"value": "t1"},
                        "field": {"value": "f1"},
                        "target": {"value": "p1"},
                    },
                    {
                        "rule": {"value": "r2"},
                        "table": {"value": "t2"},
                    },
                ]
            }
        }
        results = client._parse_results(data)
        assert len(results) == 2
        assert results[0]["rule"] == "r1"
        assert results[1]["field"] is None

    def test_parse_empty_results(self, client):
        data = {"results": {"bindings": []}}
        results = client._parse_results(data)
        assert results == []


class TestGraphDBClientClose:
    @pytest.mark.asyncio
    async def test_close_with_sessions(self, client):
        mock_async = AsyncMock()
        mock_async.aclose = AsyncMock()
        mock_sync = MagicMock()
        mock_sync.close = MagicMock()
        client._async_session = mock_async
        client._sync_session = mock_sync

        await client.close()
        mock_async.aclose.assert_called_once()
        mock_sync.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_sessions(self, client):
        client._async_session = None
        client._sync_session = None
        await client.close()  # should not raise

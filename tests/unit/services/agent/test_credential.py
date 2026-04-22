"""单元测试 — 凭证服务 CredentialService。"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.agent.credential import CredentialService


@pytest.fixture
def service():
    return CredentialService()


@pytest.fixture
def mock_db():
    """模拟 AsyncSession，不连接真实数据库。"""
    db = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def fake_org_id():
    return str(uuid.uuid4())


class TestGenerate:
    """generate() 测试：生成 client_id + client_secret + bcrypt 哈希存储。"""

    @pytest.mark.asyncio
    async def test_generate_returns_client_id_and_secret(self, service, mock_db, fake_org_id):
        """generate 应返回 client_id（cid_ 前缀）和 client_secret（sk_ 前缀）。"""
        result = await service.generate(mock_db, fake_org_id, "NCC")

        assert result["client_id"].startswith("cid_")
        assert result["client_secret"].startswith("sk_")
        assert result["org_id"] == fake_org_id
        assert result["datasource"] == "NCC"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_stores_bcrypt_hash(self, service, mock_db, fake_org_id):
        """generate 应存储 bcrypt 哈希而非明文 secret。"""
        result = await service.generate(mock_db, fake_org_id, "NCC")

        # 获取 add 调用传入的 ORM 对象
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.client_secret_hash != result["client_secret"]
        assert added_obj.client_secret_hash.startswith("$2")  # bcrypt hash prefix

    @pytest.mark.asyncio
    async def test_generate_client_id_unique(self, service, mock_db, fake_org_id):
        """每次 generate 应生成不同的 client_id 和 client_secret。"""
        r1 = await service.generate(mock_db, fake_org_id, "NCC")
        r2 = await service.generate(mock_db, fake_org_id, "NCC")
        assert r1["client_id"] != r2["client_id"]
        assert r1["client_secret"] != r2["client_secret"]


class TestVerify:
    """verify() 测试：校验凭证正确性。"""

    @pytest.mark.asyncio
    async def test_verify_success(self, service, mock_db, fake_org_id):
        """正确的 client_id + client_secret 应验证成功。"""
        # 先生成
        result = await service.generate(mock_db, fake_org_id, "NCC")
        added_obj = mock_db.add.call_args[0][0]

        # 模拟数据库查询返回该对象
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = added_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        # 验证
        cred = await service.verify(mock_db, result["client_id"], result["client_secret"])
        assert cred is not None
        assert cred.client_id == result["client_id"]

    @pytest.mark.asyncio
    async def test_verify_wrong_secret(self, service, mock_db, fake_org_id):
        """错误的 client_secret 应验证失败。"""
        result = await service.generate(mock_db, fake_org_id, "NCC")
        added_obj = mock_db.add.call_args[0][0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = added_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        cred = await service.verify(mock_db, result["client_id"], "sk_wrong_secret")
        assert cred is None

    @pytest.mark.asyncio
    async def test_verify_revoked_credential(self, service, mock_db, fake_org_id):
        """已吊销的凭证应验证失败。"""
        result = await service.generate(mock_db, fake_org_id, "NCC")
        added_obj = mock_db.add.call_args[0][0]
        added_obj.revoked_at = datetime.now(timezone.utc)  # 标记已吊销

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = added_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        cred = await service.verify(mock_db, result["client_id"], result["client_secret"])
        assert cred is None

    @pytest.mark.asyncio
    async def test_verify_not_found_no_bcrypt(self, service, mock_db):
        """client_id 不存在时应直接返回 None，不执行 bcrypt（防 CPU 消耗）。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_verify_secret") as mock_verify:
            cred = await service.verify(mock_db, "cid_nonexistent", "sk_whatever")
            assert cred is None
            mock_verify.assert_not_called()


class TestRevoke:
    """revoke() 测试：吊销凭证。"""

    @pytest.mark.asyncio
    async def test_revoke_sets_revoked_at(self, service, mock_db, fake_org_id):
        """revoke 应设置 revoked_at 时间戳。"""
        result = await service.generate(mock_db, fake_org_id, "NCC")
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.revoked_at is None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = added_obj
        mock_db.execute = AsyncMock(return_value=mock_result)

        revoked = await service.revoke(mock_db, result["client_id"])
        assert revoked is not None
        assert revoked.revoked_at is not None
        mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_revoke_not_found(self, service, mock_db):
        """吊销不存在的 client_id 应返回 None。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        revoked = await service.revoke(mock_db, "cid_nonexistent")
        assert revoked is None

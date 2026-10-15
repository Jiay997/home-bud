# -*- coding: utf-8 -*-
"""通道抽象单测：支付/认证通道分发与对账差异检测（spec 通道收口 Task 3）。

不依赖数据库与真实微信服务：
- 通道凭据场景通过 monkeypatch 直接改 settings 单例实例属性（teardown 自动还原）；
- run_reconcile_check 以 SimpleNamespace 假订单 + 假 Session 验证差异判定
  （SQL 过滤条件在真实 ORM 表达式层保证，内存判定逻辑在此覆盖；
  参考 tests/test_admin_perms.py 的纯函数测试风格）。
"""
import base64
import json
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 保证以 tests/ 目录单独运行时也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.crypto import sha256_hex
from app.models.base import utcnow
from app.services.auth_provider import (
    AuthConfigError,
    AuthProvider,
    DevAuthProvider,
    WxAuthProvider,
    get_auth_provider,
)
from app.services.pay_provider import (
    MockPayProvider,
    PayConfigError,
    PayProvider,
    WxPayProvider,
    get_pay_provider,
)
from app.services.reconcile import run_reconcile_check
from app.services.safety_scan import callback_signature


# ---------- MockPayProvider 验签 ----------


class TestMockPayVerify:
    """MockPayProvider.verify_callback 与既有 mock-pay 口径一致性。"""

    def test_correct_sign_passes(self):
        """正确签名（sha256(transaction_id + pay_mock_sign_key)）验签通过。"""
        tid = "TX" + "1" * 16
        sign = sha256_hex(tid + get_settings().pay_mock_sign_key)
        assert MockPayProvider().verify_callback(tid, sign) is True

    def test_wrong_sign_rejected(self):
        """错误签名验签不通过（返回 False，由调用方统一转 1504）。"""
        tid = "TX" + "2" * 16
        assert MockPayProvider().verify_callback(tid, sha256_hex("tampered")) is False

    def test_sign_follows_configured_key(self, monkeypatch):
        """验签密钥动态取自 settings（密钥轮换后旧签名失效）。"""
        monkeypatch.setattr(get_settings(), "pay_mock_sign_key", "rotated-key")
        tid = "TX3"
        assert MockPayProvider().verify_callback(tid, sha256_hex(tid + "rotated-key")) is True
        assert MockPayProvider().verify_callback(tid, sha256_hex(tid + "old-key")) is False

    def test_mock_create_order_and_refund(self):
        """mock 通道下单返回模拟参数（pay_params=None）；退款 no-op 返回 refunded。"""
        provider = MockPayProvider()
        order = provider.create_order({"out_trade_no": "JBTEST1", "amount_micro": 100})
        assert order["channel"] == "mock" and order["pay_params"] is None
        result = provider.refund("JBTEST1", "TX1", 100, "test")
        assert result["status"] == "refunded"


# ---------- 支付通道分发 ----------


class TestPayProviderDispatch:
    """get_pay_provider() 按 settings.pay_provider 分发。"""

    def test_mock_is_default(self, monkeypatch):
        """pay_provider='mock' 返回 MockPayProvider（PayProvider 子类）。"""
        monkeypatch.setattr(get_settings(), "pay_provider", "mock")
        provider = get_pay_provider()
        assert isinstance(provider, MockPayProvider)
        assert isinstance(provider, PayProvider)

    def test_wxpay_missing_credentials_raises(self, monkeypatch):
        """pay_provider='wxpay' 且商户凭据全空：工厂分发处即抛 PayConfigError。"""
        s = get_settings()
        monkeypatch.setattr(s, "pay_provider", "wxpay")
        for attr in ("wxpay_mch_id", "wxpay_serial_no", "wxpay_private_key_path", "wxpay_api_v3_key"):
            monkeypatch.setattr(s, attr, "")
        with pytest.raises(PayConfigError) as excinfo:
            get_pay_provider()
        # 缺失项逐一点名（仅指明缺失，不伪造凭据）
        assert "WXPAY_MCH_ID" in str(excinfo.value)

    def test_wxpay_full_credentials_no_placeholder(self, monkeypatch):
        """凭据齐全时工厂通过；三能力为完整实现（不再抛 waiting for credentials 占位错）。

        本轮（finalize-modules-to-100 Task 3.2）将占位实现补全为 V3 完整协议：
        - create_order/refund：dummy.pem 私钥不可读 → PayConfigError（配置类错误，非占位错）；
        - verify_callback：非法通知信封 → 返回 False 拒绝（不抛占位错、不更新订单）。
        注：此处 wxpay_* 均为测试桩值，仅为走通校验路径，非真实微信凭据。
        """
        s = get_settings()
        monkeypatch.setattr(s, "pay_provider", "wxpay")
        monkeypatch.setattr(s, "wxpay_mch_id", "TEST-MCHID")
        monkeypatch.setattr(s, "wxpay_serial_no", "TEST-SERIAL")
        monkeypatch.setattr(s, "wxpay_private_key_path", "dummy.pem")
        monkeypatch.setattr(s, "wxpay_api_v3_key", "TEST-V3KEY")
        # JSAPI 下单前置配置一并打桩，确保走到「私钥加载」分支验证完整实现路径
        monkeypatch.setattr(s, "wx_appid", "TEST-APPID")
        monkeypatch.setattr(s, "wxpay_notify_url", "https://test.example.com/api/v1/billing/pay/notify")
        provider = get_pay_provider()
        assert isinstance(provider, WxPayProvider)
        # 下单/退款：私钥文件不可读，抛配置类错误且信息不再是占位文案
        with pytest.raises(PayConfigError, match="private key not readable"):
            provider.create_order({"out_trade_no": "JB1", "openid": "oX", "amount_micro": 19_900_00})
        with pytest.raises(PayConfigError, match="private key not readable"):
            provider.refund("JB1", "TX1", 1_000_000, "test")
        # 回调：非法信封验签失败 → 一律 False 拒绝
        assert provider.verify_callback("TX1", "sig") is False

    def test_unknown_provider_raises(self, monkeypatch):
        """未知 pay_provider 取值抛 PayConfigError。"""
        monkeypatch.setattr(get_settings(), "pay_provider", "alipay")
        with pytest.raises(PayConfigError):
            get_pay_provider()


# ---------- 认证通道分发与 DevProvider 幂等 ----------


class TestAuthProviderDispatch:
    """get_auth_provider() 按 settings.auth_provider 分发 + DevProvider 语义。"""

    def test_dev_is_default(self, monkeypatch):
        """auth_provider='dev' 返回 DevAuthProvider（AuthProvider 子类）。"""
        monkeypatch.setattr(get_settings(), "auth_provider", "dev")
        assert isinstance(get_auth_provider(), DevAuthProvider)
        assert isinstance(DevAuthProvider(), AuthProvider)

    def test_wx_missing_credentials_raises(self, monkeypatch):
        """auth_provider='wx' 且 WX_APPID/WX_SECRET 缺失：分发处即抛 AuthConfigError。"""
        s = get_settings()
        monkeypatch.setattr(s, "auth_provider", "wx")
        monkeypatch.setattr(s, "wx_appid", "")
        monkeypatch.setattr(s, "wx_secret", "")
        with pytest.raises(AuthConfigError) as excinfo:
            get_auth_provider()
        assert "WX_APPID/WX_SECRET" in str(excinfo.value)

    def test_wx_with_credentials_returns_provider(self, monkeypatch):
        """凭据齐全时返回 WxAuthProvider（HTTP 调用路径不在单测覆盖）。

        注：wx_appid/wx_secret 为测试桩值，仅走通分发校验，非真实凭据。
        """
        s = get_settings()
        monkeypatch.setattr(s, "auth_provider", "wx")
        monkeypatch.setattr(s, "wx_appid", "TEST-APPID")
        monkeypatch.setattr(s, "wx_secret", "TEST-SECRET")
        assert isinstance(get_auth_provider(), WxAuthProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        """未知 auth_provider 取值抛 AuthConfigError。"""
        monkeypatch.setattr(get_settings(), "auth_provider", "sms")
        with pytest.raises(AuthConfigError):
            get_auth_provider()

    def test_dev_provider_idempotent(self):
        """DevProvider.authenticate 幂等：同 device_id 恒得同 openid。"""
        provider = DevAuthProvider()
        first = provider.authenticate({"device_id": "device-abc"})
        second = provider.authenticate({"device_id": "device-abc"})
        other = provider.authenticate({"device_id": "device-xyz"})
        assert first["openid"] == second["openid"]
        # 与既有 dev-login 口径一致：sha256_hex('dev:' + device_id)
        assert first["openid"] == sha256_hex("dev:device-abc")
        assert first["openid"] != other["openid"]
        assert first["session_key"] is None


# ---------- 对账差异检测 ----------


class _FakeQuery:
    """链式查询假对象：忽略 filter 条件，直接返回预置行集。

    Args:
        rows: 预置订单假行列表。
    """

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        """吞掉过滤条件（SQL 条件由真实 ORM 表达式在调用侧构造）。

        Returns:
            自身（支持链式调用）。
        """
        return self

    def all(self):
        """返回预置行集。

        Returns:
            订单假行列表。
        """
        return self._rows


class _FakeSession:
    """假数据库会话：仅实现 run_reconcile_check 用到的 query/flush。

    Attributes:
        rows: 预置订单假行。
        flush_called: flush 是否被调用。
    """

    def __init__(self, rows):
        self.rows = rows
        self.flush_called = False

    def query(self, model):
        """返回假查询（忽略模型类型）。

        Args:
            model: ORM 模型类（忽略）。

        Returns:
            _FakeQuery 实例。
        """
        return _FakeQuery(self.rows)

    def flush(self):
        """记录 flush 调用（commit 由真实调用方负责）。"""
        self.flush_called = True


def _order(paid_at=None, status="paid", notify_status=None, reconcile_status=None):
    """构造对账判定所需的订单假行（SimpleNamespace）。

    Args:
        paid_at: 支付时间（aware datetime 或 None）。
        status: 订单状态。
        notify_status: 回调状态。
        reconcile_status: 对账状态。

    Returns:
        含 run_reconcile_check 判定所需属性的假行对象。
    """
    return SimpleNamespace(
        status=status,
        paid_at=paid_at,
        notify_status=notify_status,
        reconcile_status=reconcile_status,
    )


class TestReconcileCheck:
    """run_reconcile_check：paid + 回调缺失 + 超宽限期 → reconcile_status='diff'。"""

    def test_paid_missed_beyond_grace_marked_diff(self):
        """超宽限期（>1h）的 paid+missed/回调缺失订单被置 diff 并正确计数。"""
        now = utcnow()
        orders = [
            _order(paid_at=now - timedelta(hours=2), notify_status="missed"),
            _order(paid_at=now - timedelta(hours=3), notify_status=None),
        ]
        db = _FakeSession(orders)
        result = run_reconcile_check(db)
        assert result == {"checked": 2, "diff_count": 2}
        assert all(o.reconcile_status == "diff" for o in orders)
        assert db.flush_called is True

    def test_within_grace_not_marked(self):
        """宽限期内（<=1h）不判差异（容忍渠道回调延迟）。"""
        o = _order(paid_at=utcnow() - timedelta(minutes=30))
        result = run_reconcile_check(_FakeSession([o]))
        assert result == {"checked": 1, "diff_count": 0}
        assert o.reconcile_status is None

    def test_paid_at_none_defensive_skip(self):
        """paid_at 缺失的候选行防御性跳过（不判差异、不报错）。"""
        o = _order(paid_at=None, notify_status="missed")
        result = run_reconcile_check(_FakeSession([o]))
        assert result == {"checked": 1, "diff_count": 0}
        assert o.reconcile_status is None

    def test_empty_candidate_set_returns_zeroes(self):
        """空候选集（真实 SQL 已过滤 received/matched/pending）返回零值。"""
        result = run_reconcile_check(_FakeSession([]))
        assert result == {"checked": 0, "diff_count": 0}


# ---------- WxPayProvider V3 协议内核（本地凭据无关部分） ----------


@pytest.fixture
def rsa_keypair(tmp_path):
    """生成 RSA-2048 测试密钥对并落盘（私钥 PEM + 公钥 PEM）。"""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path = tmp_path / "apiclient_key.pem"
    public_path = tmp_path / "platform_pub.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return key, str(private_path), str(public_path)


class TestWxPayV3Protocol:
    """WxPayProvider V3 协议内核：签名头构造 / 回调验签 / resource 解密。"""

    def _configure_merchant(self, monkeypatch, private_key_path):
        """注入商户凭据（仅本地测试值，非真实凭据）。"""
        s = get_settings()
        monkeypatch.setattr(s, "wxpay_mch_id", "1900000001")
        monkeypatch.setattr(s, "wxpay_serial_no", "TESTSERIAL")
        monkeypatch.setattr(s, "wxpay_private_key_path", private_key_path)

    def test_authorization_header_signature_verifies(self, monkeypatch, rsa_keypair):
        """Authorization 头格式正确，且可用商户公钥复验（RSA-SHA256/PKCS1v15）。"""
        key, private_path, _ = rsa_keypair
        self._configure_merchant(monkeypatch, private_path)
        header = WxPayProvider().build_authorization_header(
            "POST", "/v3/pay/transactions/jsapi", '{"out_trade_no":"O1"}',
            timestamp=1700000000, nonce="NONCE123",
        )
        assert header.startswith("WECHATPAY2-SHA256-RSA2048 ")
        assert 'mchid="1900000001"' in header
        assert 'nonce_str="NONCE123"' in header
        assert 'timestamp="1700000000"' in header
        signature = header.split('signature="', 1)[1].split('"', 1)[0]
        message = "POST\n/v3/pay/transactions/jsapi\n1700000000\nNONCE123\n{\"out_trade_no\":\"O1\"}\n"
        # 私钥签名、公钥复验（模拟微信侧验签链路）
        key.public_key().verify(
            base64.b64decode(signature), message.encode("utf-8"),
            padding.PKCS1v15(), hashes.SHA256(),
        )

    def test_authorization_header_missing_credentials(self, monkeypatch):
        """商户凭据缺失时显式抛 PayConfigError（不伪造）。"""
        s = get_settings()
        monkeypatch.setattr(s, "wxpay_mch_id", "")
        with pytest.raises(PayConfigError):
            WxPayProvider().build_authorization_header("GET", "/v3/certificates", "")

    def test_verify_notification_signature(self, monkeypatch, rsa_keypair):
        """回调通知验签：正确签名通过、篡改返回 False、未配置证书抛错。"""
        key, _, public_path = rsa_keypair
        monkeypatch.setattr(get_settings(), "wxpay_platform_cert_path", public_path)
        ts, nonce, body = "1700000000", "N1", '{"id":"evt-1"}'
        message = f"{ts}\n{nonce}\n{body}\n"
        good_sign = base64.b64encode(
            key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        ).decode()
        provider = WxPayProvider()
        assert provider.verify_notification_signature(ts, nonce, body, good_sign) is True
        # 篡改请求体后签名失效
        assert provider.verify_notification_signature(ts, nonce, body + "x", good_sign) is False
        # 未配置平台证书：显式失败
        monkeypatch.setattr(get_settings(), "wxpay_platform_cert_path", "")
        with pytest.raises(PayConfigError):
            provider.verify_notification_signature(ts, nonce, body, good_sign)

    def test_decrypt_resource(self, monkeypatch):
        """AES-256-GCM resource 解密：正确密钥还原 JSON、错误密钥抛 ValueError。"""
        api_v3_key = "0123456789abcdef0123456789abcdef"  # 32 字节测试密钥
        monkeypatch.setattr(get_settings(), "wxpay_api_v3_key", api_v3_key)
        payload = {"out_trade_no": "JB1", "transaction_id": "TX1", "trade_state": "SUCCESS"}
        nonce, aad = "nonce123456", "transaction"
        ciphertext = base64.b64encode(
            AESGCM(api_v3_key.encode()).encrypt(
                nonce.encode(), json.dumps(payload).encode(), aad.encode()
            )
        ).decode()
        assert WxPayProvider.decrypt_resource(aad, nonce, ciphertext) == payload
        # 密钥不符：解密失败抛 ValueError（调用方转 1901/1504）
        monkeypatch.setattr(get_settings(), "wxpay_api_v3_key", "x" * 32)
        with pytest.raises(ValueError):
            WxPayProvider.decrypt_resource(aad, nonce, ciphertext)

    def test_decrypt_resource_key_must_be_32_bytes(self, monkeypatch):
        """APIv3 密钥缺失/长度非法时显式抛 PayConfigError。"""
        monkeypatch.setattr(get_settings(), "wxpay_api_v3_key", "short")
        with pytest.raises(PayConfigError):
            WxPayProvider.decrypt_resource("", "n", "AAAA")


# ---------- 内容安全回调签名（平台回调闭环协议） ----------


class TestSafetyCallbackSignature:
    """callback_signature：协议单点定义（平台侧与本地验签共用）。"""

    def test_deterministic_and_verdict_sensitive(self):
        """同输入稳定一致；verdict 不同签名不同（防跨裁决重放）。"""
        s1 = callback_signature("secret-a", 42, "pass", 1700000000)
        s2 = callback_signature("secret-a", 42, "pass", 1700000000)
        s3 = callback_signature("secret-a", 42, "reject", 1700000000)
        assert s1 == s2 and len(s1) == 64
        assert s1 != s3

    def test_secret_sensitive(self):
        """密钥不同签名不同（密钥轮换即失效旧签名）。"""
        assert callback_signature("key-1", 7, "manual", 1) != callback_signature(
            "key-2", 7, "manual", 1
        )

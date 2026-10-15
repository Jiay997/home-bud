# -*- coding: utf-8 -*-
"""生产化通道实现单测（spec finalize Task 3：配置即切）。

覆盖范围（不依赖真实微信服务，HTTP 经 httpx.MockTransport 注入）：
- 3.1 WxAuthProvider 生产实现：code2session 成功 / errcode 失败（40029、45011
  映射）/ 网络超时 三路径 mock HTTP + 缺凭据一次性列全报错；
- 3.2 WxPayProvider 生产实现：V3 JSAPI 下单成功（含验签调起参数）、回调
  验签失败拒绝、回调解密成功（自测夹具：测试专用生成的商户/平台 RSA 密钥
  对与 AES-256-GCM 密文）、退款与远程异常、私钥内容形态加载；
- 3.3 CryptoProvider：Local/KMS 两实现加解密往返、配置分发、既有 v{N}:
  密文兼容与跨格式轮换。
"""
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 保证以 tests/ 目录单独运行时也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.crypto import (  # noqa: E402
    CryptoConfigError,
    CryptoProvider,
    KMS_PREFIX,
    LocalFernetProvider,
    decrypt_field,
    encrypt_field,
    get_crypto_provider,
    reencrypt_field,
    sha256_hex,
)
from app.services.auth_provider import (  # noqa: E402
    AuthConfigError,
    DevAuthProvider,
    WxAuthApiError,
    WxAuthNetworkError,
    WxAuthProvider,
    get_auth_provider,
)
from app.services.pay_provider import (  # noqa: E402
    MockPayProvider,
    WxPayProvider,
    WxPayRemoteError,
    get_pay_provider,
)


# ===========================================================================
# 3.1 WxAuthProvider 生产实现
# ===========================================================================
class TestWxAuthProviderFull:
    """WxAuthProvider 生产实现：mock HTTP 三路径 + 缺凭据报错 + dev 零变化。"""

    def _set_credentials(self, monkeypatch) -> None:
        """注入微信登录凭据（测试桩值，非真实凭据）。

        Args:
            monkeypatch: pytest 夹具（teardown 自动还原 settings 单例属性）。

        Returns:
            None。

        Raises:
            无。
        """
        s = get_settings()
        monkeypatch.setattr(s, "auth_provider", "wx")
        monkeypatch.setattr(s, "wx_appid", "wx-test-appid")
        monkeypatch.setattr(s, "wx_secret", "wx-test-secret")

    def test_code2session_success(self, monkeypatch):
        """成功路径：GET 参数齐全，返回 openid + session_key（不落日志口径由调用方保证）。"""
        self._set_credentials(monkeypatch)
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """记录请求参数并返回成功响应。

            Args:
                request: httpx 请求对象。

            Returns:
                模拟微信成功响应（含 openid/session_key）。
            """
            captured["url"] = str(request.url)
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200, json={"openid": "o-openid-1", "session_key": "sk-xyz", "unionid": "u-1"}
            )

        monkeypatch.setattr(WxAuthProvider, "_transport", httpx.MockTransport(handler))
        creds = WxAuthProvider().authenticate({"code": "js-code-1"})
        assert creds["openid"] == "o-openid-1"
        assert creds["session_key"] == "sk-xyz"
        # 端点与参数口径：appid/secret/js_code/grant_type
        assert captured["url"].startswith("https://api.weixin.qq.com/sns/jscode2session")
        assert captured["params"]["appid"] == "wx-test-appid"
        assert captured["params"]["secret"] == "wx-test-secret"
        assert captured["params"]["js_code"] == "js-code-1"
        assert captured["params"]["grant_type"] == "authorization_code"

    def test_errcode_40029_invalid_code(self, monkeypatch):
        """errcode=40029（invalid code）映射为 WxAuthApiError，含明确提示与日志语义。"""
        self._set_credentials(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            """返回 40029 invalid code 错误响应。"""
            return httpx.Response(
                200, json={"errcode": 40029, "errmsg": "invalid code"}
            )

        monkeypatch.setattr(WxAuthProvider, "_transport", httpx.MockTransport(handler))
        with pytest.raises(WxAuthApiError) as excinfo:
            WxAuthProvider().authenticate({"code": "bad-code"})
        assert "40029" in str(excinfo.value)
        assert "invalid code" in str(excinfo.value)
        # 细分异常仍属 AuthConfigError 家族：调用方既有兜底链路（1901/503）零变化
        assert isinstance(excinfo.value, AuthConfigError)

    def test_errcode_45011_rate_limit(self, monkeypatch):
        """errcode=45011（频率限制）映射为 WxAuthApiError，含频控提示。"""
        self._set_credentials(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            """返回 45011 频率限制错误响应。"""
            return httpx.Response(
                200, json={"errcode": 45011, "errmsg": "api minute-quota reach limit"}
            )

        monkeypatch.setattr(WxAuthProvider, "_transport", httpx.MockTransport(handler))
        with pytest.raises(WxAuthApiError) as excinfo:
            WxAuthProvider().authenticate({"code": "any-code"})
        assert "45011" in str(excinfo.value)

    def test_network_timeout_maps_to_network_error(self, monkeypatch):
        """网络超时路径：httpx 超时异常映射为 WxAuthNetworkError（非 errcode 失败）。"""
        self._set_credentials(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            """模拟超时：抛出 httpx.ReadTimeout（httpx.HTTPError 子类）。"""
            raise httpx.ReadTimeout("simulated timeout")

        monkeypatch.setattr(WxAuthProvider, "_transport", httpx.MockTransport(handler))
        with pytest.raises(WxAuthNetworkError) as excinfo:
            WxAuthProvider().authenticate({"code": "any-code"})
        assert isinstance(excinfo.value, AuthConfigError)

    def test_missing_credentials_listed_at_once(self, monkeypatch):
        """缺凭据：一次性列全全部缺失配置项（appid/secret 同报，不逐个报）。"""
        s = get_settings()
        monkeypatch.setattr(s, "auth_provider", "wx")
        monkeypatch.setattr(s, "wx_appid", "")
        monkeypatch.setattr(s, "wx_secret", "")
        with pytest.raises(AuthConfigError) as excinfo:
            get_auth_provider()
        msg = str(excinfo.value)
        assert "WX_APPID" in msg and "WX_SECRET" in msg
        # 双缺失聚合为一条报错（WX_APPID/WX_SECRET 同句），且不泄露具体值
        assert "WX_APPID/WX_SECRET" in msg

    def test_partial_missing_credential_named(self, monkeypatch):
        """部分缺失：仅点名实际缺失项（只缺 secret 时不误报 appid）。"""
        s = get_settings()
        monkeypatch.setattr(s, "auth_provider", "wx")
        monkeypatch.setattr(s, "wx_appid", "wx-have-appid")
        monkeypatch.setattr(s, "wx_secret", "")
        with pytest.raises(AuthConfigError) as excinfo:
            get_auth_provider()
        assert "WX_SECRET" in str(excinfo.value)

    def test_dev_channel_unchanged(self):
        """dev 通道行为零变化：确定性哈希 openid 与既有 dev-login 口径一致。"""
        s = get_settings()
        assert s.auth_provider != "wx"  # 缺省 dev（.env 现值），不因本轮改动漂移
        assert isinstance(get_auth_provider(), DevAuthProvider)
        assert DevAuthProvider().authenticate({"device_id": "d1"})["openid"] == sha256_hex("dev:d1")


# ===========================================================================
# 3.2 WxPayProvider 生产实现
# ===========================================================================
@pytest.fixture
def wxpay_env(monkeypatch, tmp_path):
    """构造微信支付 V3 自测夹具：测试专用生成的商户/平台 RSA 密钥对与凭据。

    Args:
        monkeypatch: pytest 夹具（teardown 自动还原 settings）。
        tmp_path: pytest 临时目录（落盘私钥/平台公钥 PEM）。

    Returns:
        SimpleNamespace：merchant_key（商户私钥对象）、platform_key（平台
        私钥对象）、api_v3_key（32 字符 APIv3 密钥）。

    Raises:
        无。
    """
    # 测试专用密钥对（非真实商户/平台凭据，每次运行重新生成）
    merchant_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    platform_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "apiclient_key.pem"
    private_path.write_bytes(
        merchant_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    platform_pub_path = tmp_path / "platform_pub.pem"
    platform_pub_path.write_bytes(
        platform_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    api_v3_key = "0123456789abcdef0123456789abcdef"  # 32 字节测试密钥

    s = get_settings()
    monkeypatch.setattr(s, "wx_appid", "wx-test-appid")
    monkeypatch.setattr(s, "wxpay_mch_id", "1900000099")
    monkeypatch.setattr(s, "wxpay_serial_no", "TESTSERIAL99")
    monkeypatch.setattr(s, "wxpay_private_key_path", str(private_path))
    monkeypatch.setattr(s, "wxpay_api_v3_key", api_v3_key)
    monkeypatch.setattr(s, "wxpay_platform_cert_path", str(platform_pub_path))
    monkeypatch.setattr(s, "wxpay_notify_url", "https://pay.example.com/api/v1/billing/notify")
    return SimpleNamespace(merchant_key=merchant_key, platform_key=platform_key, api_v3_key=api_v3_key)


def _sign_with(platform_key, timestamp: str, nonce: str, body_text: str) -> str:
    """以平台私钥构造 Wechatpay-Signature（RSA-SHA256 over t\\nn\\nb\\n）。

    Args:
        platform_key: 平台 RSA 私钥对象。
        timestamp: Wechatpay-Timestamp。
        nonce: Wechatpay-Nonce。
        body_text: 回调 body 原文。

    Returns:
        base64 编码签名串。

    Raises:
        无。
    """
    message = f"{timestamp}\n{nonce}\n{body_text}\n"
    return base64.b64encode(
        platform_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    ).decode("utf-8")


def _encrypt_resource(api_v3_key: str, payload: dict, aad: str = "transaction"):
    """以 APIv3 密钥构造回调 resource 密文三要素。

    Args:
        api_v3_key: 32 字符 APIv3 密钥。
        payload: 业务明文字典（解密后应还原）。
        aad: associated_data（微信支付 transaction 通知固定为 "transaction"）。

    Returns:
        (ciphertext_b64, nonce, aad) 三元组。

    Raises:
        无。
    """
    nonce = "nonce123456"
    ciphertext = base64.b64encode(
        AESGCM(api_v3_key.encode("utf-8")).encrypt(
            nonce.encode("utf-8"), json.dumps(payload).encode("utf-8"), aad.encode("utf-8")
        )
    ).decode("utf-8")
    return ciphertext, nonce, aad


class TestWxPayProviderFull:
    """WxPayProvider 生产实现：下单/验签拒绝/解密成功/退款（mock HTTP）。"""

    def test_create_order_success_and_pay_params(self, monkeypatch, wxpay_env):
        """下单成功：JSAPI 报文要素齐全，调起参数可用商户公钥复验 paySign。"""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """校验请求签名头与报文，返回 prepay_id。"""
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("Authorization", "")
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"prepay_id": "wx-prepay-1"})

        monkeypatch.setattr(WxPayProvider, "_transport", httpx.MockTransport(handler))
        result = WxPayProvider().create_order(
            {
                "out_trade_no": "JB20260101TEST01",
                "amount_micro": 1_000_000,  # 1 元 → 100 分
                "description": "测试订单",
                "openid": "o-pay-user",
            }
        )
        assert result["channel"] == "wxpay"
        assert result["prepay_id"] == "wx-prepay-1"
        # JSAPI 下单端点与报文要素
        assert captured["path"] == "/v3/pay/transactions/jsapi"
        assert captured["auth"].startswith("WECHATPAY2-SHA256-RSA2048 ")
        assert captured["body"]["appid"] == "wx-test-appid"
        assert captured["body"]["mchid"] == "1900000099"
        assert captured["body"]["out_trade_no"] == "JB20260101TEST01"
        assert captured["body"]["amount"] == {"total": 100, "currency": "CNY"}
        assert captured["body"]["payer"] == {"openid": "o-pay-user"}
        assert captured["body"]["notify_url"].startswith("https://")
        # 调起参数：五参数齐全，paySign 可用商户公钥复验（二次签名口径）
        pp = result["pay_params"]
        assert pp["appId"] == "wx-test-appid"
        assert pp["signType"] == "RSA"
        assert pp["package"] == "prepay_id=wx-prepay-1"
        message = f"{pp['appId']}\n{pp['timeStamp']}\n{pp['nonceStr']}\n{pp['package']}\n"
        wxpay_env.merchant_key.public_key().verify(
            base64.b64decode(pp["paySign"]),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_verify_callback_reject_on_bad_signature(self, monkeypatch, wxpay_env):
        """验签失败拒绝：签名非平台私钥（伪造）→ verify_callback 返回 False
        （billing_api 现有流程转 1504 且不更新订单，状态机零改动）。"""
        resource_payload = {"out_trade_no": "JB1", "transaction_id": "TXGOOD"}
        ciphertext, nonce, aad = _encrypt_resource(wxpay_env.api_v3_key, resource_payload)
        body_text = json.dumps(
            {"id": "evt-1", "resource": {"ciphertext": ciphertext, "nonce": nonce, "associated_data": aad}}
        )
        ts, nc = "1700000000", "NONCE1"
        # 伪造：用商户私钥（而非平台私钥）签名
        forged_sign = _sign_with(wxpay_env.merchant_key, ts, nc, body_text)
        envelope = base64.b64encode(
            json.dumps({"t": ts, "n": nc, "s": forged_sign, "b": body_text}).encode("utf-8")
        ).decode("utf-8")
        provider = WxPayProvider()
        assert provider.verify_callback("TXGOOD", envelope) is False
        # 纯协议层同样拒绝：handle_notification 抛 ValueError
        with pytest.raises(ValueError):
            provider.handle_notification(ts, nc, body_text, forged_sign)

    def test_verify_callback_decrypt_success(self, monkeypatch, wxpay_env):
        """回调解密成功：平台私钥合法签名 + APIv3 密文 → 放行且交易号一致。"""
        resource_payload = {"out_trade_no": "JB1", "transaction_id": "TXOK", "trade_state": "SUCCESS"}
        ciphertext, nonce, aad = _encrypt_resource(wxpay_env.api_v3_key, resource_payload)
        body_text = json.dumps(
            {"id": "evt-2", "resource": {"ciphertext": ciphertext, "nonce": nonce, "associated_data": aad}}
        )
        ts, nc = "1700000001", "NONCE2"
        good_sign = _sign_with(wxpay_env.platform_key, ts, nc, body_text)
        envelope = base64.b64encode(
            json.dumps({"t": ts, "n": nc, "s": good_sign, "b": body_text}).encode("utf-8")
        ).decode("utf-8")
        provider = WxPayProvider()
        assert provider.verify_callback("TXOK", envelope) is True
        # 交易号与通知明文不一致 → 拒绝（防错配）
        assert provider.verify_callback("TXMISMATCH", envelope) is False
        # 篡改密文 → 解密失败拒绝（验签通过但 resource 损坏）
        tampered_body = body_text.replace(ciphertext[:8], "AAAAAA==", 1)
        tampered_sign = _sign_with(wxpay_env.platform_key, ts, nc, tampered_body)
        with pytest.raises(ValueError):
            provider.handle_notification(ts, nc, tampered_body, tampered_sign)

    def test_refund_success_idempotent_refund_no(self, monkeypatch, wxpay_env):
        """退款成功：确定性退款单号（幂等），报文金额按分、transaction_id 优先。"""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """记录退款报文并返回受理成功。"""
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200, json={"refund_id": "re-1", "out_refund_no": "JB1R", "status": "SUCCESS"}
            )

        monkeypatch.setattr(WxPayProvider, "_transport", httpx.MockTransport(handler))
        result = WxPayProvider().refund("JB1", "TX1", 1_000_000, "用户申请退款")
        assert result["status"] == "SUCCESS"
        assert result["channel"] == "wxpay"
        assert result["out_refund_no"] == "JB1R"
        assert captured["path"] == "/v3/refund/domestic/refunds"
        assert captured["body"]["out_refund_no"] == "JB1R"  # 确定性：重复发起同单号 → 渠道幂等
        assert captured["body"]["transaction_id"] == "TX1"
        assert captured["body"]["amount"]["refund"] == 100

    def test_remote_http_error_maps_to_remote_error(self, monkeypatch, wxpay_env):
        """远程失败归类：渠道 5xx → WxPayRemoteError（区别于本地凭据缺失）。"""

        def handler(request: httpx.Request) -> httpx.Response:
            """返回渠道 500 错误。"""
            return httpx.Response(500, json={"code": "SYSTEM_ERROR", "message": "busy"})

        monkeypatch.setattr(WxPayProvider, "_transport", httpx.MockTransport(handler))
        with pytest.raises(WxPayRemoteError):
            WxPayProvider().create_order(
                {"out_trade_no": "JB2", "amount_micro": 1_000_000, "openid": "o-1"}
            )

    def test_private_key_pem_content_mode(self, monkeypatch, wxpay_env):
        """私钥内容形态：WXPAY_PRIVATE_KEY_PATH 直接放 PEM 内容亦可签名。"""
        pem_content = wxpay_env.merchant_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("utf-8")
        monkeypatch.setattr(get_settings(), "wxpay_private_key_path", pem_content)
        header = WxPayProvider().build_authorization_header("GET", "/v3/certificates", "")
        assert header.startswith("WECHATPAY2-SHA256-RSA2048 ")

    def test_mock_channel_dispatch_unchanged(self, monkeypatch):
        """mock 通道零变化：缺省分发仍为 MockPayProvider（既有验签口径不变）。"""
        monkeypatch.setattr(get_settings(), "pay_provider", "mock")
        assert isinstance(get_pay_provider(), MockPayProvider)


# ===========================================================================
# 3.3 CryptoProvider 抽象 / LocalFernetProvider / KmsEnvelopeProvider
# ===========================================================================
class TestCryptoProvider:
    """字段加密 Provider：两实现往返、配置分发、既有密文兼容。"""

    def test_local_roundtrip_and_format(self):
        """local 实现往返：输出保持 v{N}: 前缀格式（既有密文无需迁移）。"""
        provider = LocalFernetProvider()
        assert isinstance(provider, CryptoProvider)
        ct = provider.encrypt_field("手机号-13800001111")
        assert ct.startswith("v") and ":" in ct
        assert provider.decrypt_field(ct) == "手机号-13800001111"
        # 模块级函数与 Provider 等价（调用点零改动）
        assert decrypt_field(encrypt_field("abc-123")) == "abc-123"

    def test_kms_roundtrip_with_test_kek(self):
        """kms 实现往返（测试专用 KEK 注入）：信封格式带 provider 标记与 DEK id。"""
        from app.core.crypto import EnvVarKekAdapter, KmsEnvelopeProvider

        provider = KmsEnvelopeProvider(kek_adapter=EnvVarKekAdapter(master_key="unit-test-kek"))
        ct = provider.encrypt_field("openai-key-sk-test")
        assert ct.startswith(KMS_PREFIX)
        # 密文头：kms1:{dek_id}:...（dek_id 自包含 wrapped DEK 句柄，句柄无冒号单段安全）
        parts = ct[len(KMS_PREFIX):].split(":")
        assert len(parts) == 3 and parts[0].startswith("env1_")
        assert provider.decrypt_field(ct) == "openai-key-sk-test"
        # reencrypt：往返一致（每次新 DEK，密文变化但明文恒定）
        ct2 = provider.reencrypt_field(ct)
        assert ct2.startswith(KMS_PREFIX) and ct2 != ct
        assert provider.decrypt_field(ct2) == "openai-key-sk-test"

    def test_kms_wrong_master_key_rejected(self):
        """KEK 不匹配（主密钥错误）：解包失败显式报 ValueError，不静默返回。"""
        from app.core.crypto import EnvVarKekAdapter, KmsEnvelopeProvider

        enc = KmsEnvelopeProvider(kek_adapter=EnvVarKekAdapter(master_key="kek-A"))
        dec = KmsEnvelopeProvider(kek_adapter=EnvVarKekAdapter(master_key="kek-B"))
        ct = enc.encrypt_field("secret")
        with pytest.raises(ValueError):
            dec.decrypt_field(ct)

    def test_dispatch_by_config(self, monkeypatch):
        """配置分发：local 默认 / kms 按 CRYPTO_PROVIDER 分发 / 缺失与未知显式报错。"""
        s = get_settings()
        # 默认（local）
        monkeypatch.setattr(s, "crypto_provider", "local")
        assert isinstance(get_crypto_provider(), LocalFernetProvider)
        # kms：需 KMS_MASTER_KEY，缺失时一次性点名
        monkeypatch.setattr(s, "crypto_provider", "kms")
        monkeypatch.setattr(s, "kms_master_key", "")
        with pytest.raises(CryptoConfigError) as excinfo:
            get_crypto_provider()
        assert "KMS_MASTER_KEY" in str(excinfo.value)
        # 配齐后分发为信封实现
        monkeypatch.setattr(s, "kms_master_key", "unit-test-kek")
        assert isinstance(get_crypto_provider(), CryptoProvider)
        ct = encrypt_field("dispatch-check")
        assert ct.startswith(KMS_PREFIX)
        assert decrypt_field(ct) == "dispatch-check"
        # 未知取值
        monkeypatch.setattr(s, "crypto_provider", "vault")
        with pytest.raises(CryptoConfigError):
            get_crypto_provider()

    def test_legacy_v_format_readable_under_kms_config(self, monkeypatch):
        """既有密文兼容：切 kms 后旧 v{N}: 密文仍可解（渐进迁移，无需一次性迁移）。"""
        s = get_settings()
        monkeypatch.setattr(s, "crypto_provider", "local")
        legacy_ct = encrypt_field("legacy-手机号-13900002222")
        assert legacy_ct.startswith("v")
        # 切换 kms：旧格式仍可读；新写入为信封格式
        monkeypatch.setattr(s, "crypto_provider", "kms")
        monkeypatch.setattr(s, "kms_master_key", "unit-test-kek")
        assert decrypt_field(legacy_ct) == "legacy-手机号-13900002222"
        kms_ct = encrypt_field("legacy-手机号-13900002222")
        assert kms_ct.startswith(KMS_PREFIX)
        # 轮换脚本兼容：reencrypt_field 将 v{N}: 迁移为 kms1:（local/kms 两配置均可跑）
        migrated = reencrypt_field(legacy_ct)
        assert migrated.startswith(KMS_PREFIX)
        assert decrypt_field(migrated) == "legacy-手机号-13900002222"

    def test_kms_ciphertext_readable_under_local_config(self, monkeypatch):
        """反向兼容：切回 local 后 kms1: 密文仍可解（跨格式路由，双向安全回退）。"""
        s = get_settings()
        monkeypatch.setattr(s, "crypto_provider", "kms")
        monkeypatch.setattr(s, "kms_master_key", "unit-test-kek")
        kms_ct = encrypt_field("rollback-check-明文")
        monkeypatch.setattr(s, "crypto_provider", "local")
        assert decrypt_field(kms_ct) == "rollback-check-明文"

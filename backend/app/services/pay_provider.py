# -*- coding: utf-8 -*-
"""支付通道抽象模块（spec D1 通道收口：mock / wxpay 统一三能力接口）。

支付能力收口为 PayProvider 抽象（下单参数组装 / 回调验签 / 退款），
billing_api 通过 get_pay_provider() 工厂按配置分发，不再感知具体通道：
- MockPayProvider：模拟支付通道（默认），包装既有 mock-pay 验签语义；
- WxPayProvider：微信支付 V3 生产实现——JSAPI 下单（必要签名）、商户
  私钥加载（PEM 路径/内容均可）、回调验签（平台证书/微信支付公钥双兼容）
  与回调解密（AES-256-GCM）、V3 退款；商户凭据填入 .env 即切换生产。

口径：金额一律 micro 整数（1 元 = 1_000_000，微信 V3 报文按分 = 10_000
micro）；任何微信商户凭据均由环境变量注入，缺凭据时一次性列全缺失项显式
抛 PayConfigError，不伪造凭据；回调验签失败一律拒绝且不更新订单。
"""
import base64
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..core.config import get_settings
from ..core.crypto import sha256_hex

# 通道专用日志器（mock 退款 no-op、V3 回调拒绝等留痕）
logger = logging.getLogger("jiaban.pay")


class PayConfigError(Exception):
    """支付通道配置缺失异常（如商户号/证书未提供）。

    Attributes:
        message: 人类可读的缺失项描述（用于日志与 1901 兜底转换）。
    """

    pass


class WxPayRemoteError(Exception):
    """微信支付远程通道异常（HTTP 失败/渠道返回错误，区别于本地配置缺失）。

    Attributes:
        message: 含接口路径与失败原因的描述（不含密钥与完整凭据）。
    """

    pass


class PayProvider(ABC):
    """支付通道抽象（create_order/verify_callback/refund 三能力）。

    所有通道实现必须保证：
    - verify_callback 为纯校验（不落库、无副作用）；
    - refund 幂等安全（同 transaction_id 重复调用不重复扣款）；
    - 不在任何日志/返回值中泄露密钥与完整敏感凭据。
    """

    @abstractmethod
    def create_order(self, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """组装渠道下单参数。

        Args:
            order_info: 订单要素字典（out_trade_no/amount_micro/description/
                openid 等，由调用方按通道需要提供）。

        Returns:
            渠道下单结果（如 JSAPI 五参数 / Native code_url / mock 占位参数）。

        Raises:
            PayConfigError: 通道凭据缺失或未配置时抛出。
        """

    @abstractmethod
    def verify_callback(self, transaction_id: str, sign: str) -> bool:
        """校验支付回调签名。

        Args:
            transaction_id: 渠道交易号。
            sign: 回调携带的签名（摘要/验签串）。

        Returns:
            验签通过返回 True；不匹配返回 False（调用方统一转 1504）。

        Raises:
            PayConfigError: 验签所需凭据/密钥未配置时抛出。
        """

    @abstractmethod
    def refund(
        self,
        out_trade_no: str,
        transaction_id: Optional[str],
        amount_micro: int,
        reason: str,
    ) -> Dict[str, Any]:
        """发起渠道退款。

        Args:
            out_trade_no: 商户订单号。
            transaction_id: 渠道交易号（可为 None）。
            amount_micro: 退款金额（micro 整数）。
            reason: 退款原因（审计留痕用）。

        Returns:
            渠道退款受理结果（至少含 status 字段）。

        Raises:
            PayConfigError: 退款所需商户凭据未配置时抛出。
        """


class MockPayProvider(PayProvider):
    """模拟支付通道：包装现有 mock-pay 语义为默认实现。

    验签口径与既有 billing_api.mock_pay 完全一致：
    sign = sha256_hex(transaction_id + settings.pay_mock_sign_key)；
    下单仅返回模拟参数（无真实渠道交互）；退款为 no-op 仅记录日志。
    """

    def create_order(self, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """返回模拟支付参数（无真实渠道交互）。

        Args:
            order_info: 订单要素字典（out_trade_no/amount_micro/description）。

        Returns:
            模拟下单结果：{"channel": "mock", "out_trade_no": ..., "pay_params": None}，
            pay_params 恒为 None（模拟支付由 /billing/orders/{no}/mock-pay 直接驱动）。
        """
        # 模拟通道不产生真实支付参数，前端直接走 mock-pay 回调端点
        return {
            "channel": "mock",
            "out_trade_no": order_info.get("out_trade_no", ""),
            "pay_params": None,
        }

    def verify_callback(self, transaction_id: str, sign: str) -> bool:
        """校验模拟支付回调签名（与既有 mock-pay 口径一致）。

        Args:
            transaction_id: 渠道交易号。
            sign: 请求携带的 sha256 摘要。

        Returns:
            sign == sha256_hex(transaction_id + pay_mock_sign_key) 时 True。

        Raises:
            无（mock 密钥为代码内置默认值，恒可获取）。
        """
        expected = sha256_hex(transaction_id + get_settings().pay_mock_sign_key)
        # 直接等值比对，保持既有 mock-pay 行为完全一致
        return sign == expected

    def refund(
        self,
        out_trade_no: str,
        transaction_id: Optional[str],
        amount_micro: int,
        reason: str,
    ) -> Dict[str, Any]:
        """模拟退款：no-op 仅记录日志（模拟环境无真实资金流）。

        Args:
            out_trade_no: 商户订单号。
            transaction_id: 渠道交易号。
            amount_micro: 退款金额（micro 整数）。
            reason: 退款原因。

        Returns:
            {"status": "refunded", "channel": "mock", "out_trade_no": ...}。
        """
        # no-op：仅留痕，供审计与排障追踪
        logger.info(
            "[mock-pay] refund no-op: out_trade_no=%s transaction_id=%s "
            "amount_micro=%d reason=%s",
            out_trade_no,
            transaction_id,
            amount_micro,
            reason,
        )
        return {"status": "refunded", "channel": "mock", "out_trade_no": out_trade_no}


class WxPayProvider(PayProvider):
    """微信支付 V3 生产实现（商户凭据填入 .env 即切换生产）。

    依赖配置（全部由环境变量注入，缺失时一次性列全并显式抛 PayConfigError）：
    - WXPAY_MCH_ID：商户号；
    - WXPAY_SERIAL_NO：商户 API 证书序列号；
    - WXPAY_PRIVATE_KEY_PATH：商户 API 私钥（apiclient_key.pem）——支持
      PEM 文件路径或 PEM 内容两种形态（值以 -----BEGIN 开头按内容处理）；
    - WXPAY_API_V3_KEY：APIv3 回调密钥（32 字符，解密 resource 用）；
    - WXPAY_PLATFORM_CERT_PATH：平台证书或微信支付公钥 PEM（回调验签用，
      两种模式均支持，按 PEM 头自动识别）；
    - WXPAY_NOTIFY_URL：V3 支付结果回调通知地址（JSAPI 下单必填）。

    能力实现：
    1. create_order：POST /v3/pay/transactions/jsapi（Authorization 头为
       WECHATPAY2-SHA256-RSA2048 商户私钥签名），返回 prepay_id 与小程序
       调起参数（appId/timeStamp/nonceStr/package/signType/paySign）；
    2. 回调处理：verify_notification_signature 平台证书/公钥验签 + 
       decrypt_resource（AES-256-GCM）解密；verify_callback 适配既有
       mock-pay 端点签名（transaction_id, sign），任何失败返回 False
       （调用方拒绝并保持订单状态不变，状态机零改动）；
    3. refund：POST /v3/refund/domestic/refunds（确定性退款单号，幂等安全）。

    远程异常归类：HTTP 失败/渠道返回错误抛 WxPayRemoteError（区别于本地
    凭据缺失的 PayConfigError），均不在日志/返回值泄露密钥与凭据。
    """

    # 微信支付 V3 API 基地址（官方固定）
    _API_BASE = "https://api.mch.weixin.qq.com"
    # 请求超时秒数（下单/退款同步等待）
    _TIMEOUT_SECONDS = 5.0
    # micro → 分换算基数（1 元 = 1_000_000 micro = 100 分 → 1 分 = 10_000 micro）
    _MICRO_PER_FEN = 10_000
    # 可注入 HTTP 传输层：生产为 None（真实网络）；测试注入 httpx.MockTransport
    _transport: Optional[httpx.BaseTransport] = None

    def _merchant_sign_credentials(self) -> Dict[str, str]:
        """校验并收集 V3 签名所需凭据（商户号/序列号/私钥）。

        验签与下单签名只依赖此三项；APIv3 密钥仅解密回调 resource 用，
        不在本方法要求内（避免解密凭据缺失阻断签名链路）。

        Returns:
            凭据字典 {mch_id, serial_no, private_key_path}。

        Raises:
            PayConfigError: 任一签名凭据缺失时抛出（信息仅指明缺失项）。
        """
        settings = get_settings()
        missing = []
        if not settings.wxpay_mch_id:
            missing.append("WXPAY_MCH_ID")
        if not settings.wxpay_serial_no:
            missing.append("WXPAY_SERIAL_NO")
        if not settings.wxpay_private_key_path:
            missing.append("WXPAY_PRIVATE_KEY_PATH")
        if missing:
            raise PayConfigError(f"wxpay sign credentials not configured: {', '.join(missing)}")
        return {
            "mch_id": settings.wxpay_mch_id,
            "serial_no": settings.wxpay_serial_no,
            "private_key_path": settings.wxpay_private_key_path,
        }

    def _load_private_key(self):
        """加载商户 API 私钥（PEM，apiclient_key.pem；路径/内容双模式）。

        配置值以 "-----BEGIN" 开头时按 PEM 内容处理（便于容器化场景直接
        注入密文），否则按文件路径读取。

        Returns:
            cryptography 私钥对象。

        Raises:
            PayConfigError: 凭据未配置或私钥内容/文件不可读/非法。
        """
        creds = self._merchant_sign_credentials()
        pem_value = creds["private_key_path"]
        try:
            if "-----BEGIN" in pem_value:
                # PEM 内容形态：直接解析（容器 secret 注入场景）
                return serialization.load_pem_private_key(
                    pem_value.encode("utf-8"), password=None
                )
            with open(pem_value, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        except (OSError, ValueError) as exc:
            raise PayConfigError(f"merchant private key not readable: {exc}") from exc

    def build_authorization_header(
        self,
        method: str,
        url_path: str,
        body_text: str,
        timestamp: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> str:
        """构造 V3 请求 Authorization 头（WECHATPAY2-SHA256-RSA2048）。

        签名字串口径（微信支付 V3 规范）：换行拼接
        "METHOD\\nURL_PATH\\nTIMESTAMP\\nNONCE\\nBODY\\n"，商户私钥
        RSA-SHA256（PKCS1v15）签名后 base64。

        Args:
            method: HTTP 方法（GET/POST）。
            url_path: 接口路径（含 query，如 /v3/pay/transactions/jsapi）。
            body_text: 请求体原文（GET 传空串）。
            timestamp: Unix 秒级时间戳；缺省取当前时间。
            nonce: 随机串（≤32 字符）；缺省取 uuid4 hex。

        Returns:
            Authorization 头完整值。

        Raises:
            PayConfigError: 商户签名凭据/私钥未配置。
        """
        creds = self._merchant_sign_credentials()
        ts = str(timestamp if timestamp is not None else int(time.time()))
        nc = nonce or uuid.uuid4().hex
        message = f"{method}\n{url_path}\n{ts}\n{nc}\n{body_text}\n"
        signature = base64.b64encode(
            self._load_private_key().sign(
                message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
            )
        ).decode("utf-8")
        return (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{creds["mch_id"]}",'
            f'nonce_str="{nc}",signature="{signature}",timestamp="{ts}"'
        )

    @staticmethod
    def _load_platform_public_key(cert_path: str):
        """加载微信支付平台证书或公钥（PEM 双兼容）。

        Args:
            cert_path: 平台证书（BEGIN CERTIFICATE）或公钥（BEGIN PUBLIC KEY）路径。

        Returns:
            平台公钥对象。

        Raises:
            PayConfigError: 文件不可读或非合法 PEM。
        """
        try:
            with open(cert_path, "rb") as f:
                pem = f.read()
            if b"BEGIN CERTIFICATE" in pem:
                return x509.load_pem_x509_certificate(pem).public_key()
            return serialization.load_pem_public_key(pem)
        except (OSError, ValueError) as exc:
            raise PayConfigError(f"platform cert not readable: {exc}") from exc

    def verify_notification_signature(
        self, timestamp: str, nonce: str, body_text: str, signature_b64: str
    ) -> bool:
        """校验回调通知签名（平台证书/微信支付公钥双模式，RSA-SHA256）。

        验签模式说明（二选一，按配置的 PEM 类型自动识别）：
        - 平台证书模式：WXPAY_PLATFORM_CERT_PATH 指向平台证书
          （BEGIN CERTIFICATE），取其内嵌公钥验签（官方经典模式）；
        - 微信支付公钥模式：指向平台公钥 PEM（BEGIN PUBLIC KEY，微信支付
          2024 新模式），直接验签。两种 PEM 均由 _load_platform_public_key
          按头自动识别，无需改代码。
        扩展位：平台证书定期轮换时可在此接入证书序列号（Wechatpay-Serial
        头）→ 证书缓存映射，并经 GET /v3/certificates 自动下载刷新；
        当前单证书/单公钥配置已满足生产最小可用。

        验签串口径：换行拼接 "TIMESTAMP\\nNONCE\\nBODY\\n"（与
        Wechatpay-Signature 头对应）。

        Args:
            timestamp: Wechatpay-Timestamp 头。
            nonce: Wechatpay-Nonce 头。
            body_text: 回调请求体原文。
            signature_b64: Wechatpay-Signature 头（base64）。

        Returns:
            验签通过 True；不匹配 False（调用方统一转 1504）。

        Raises:
            PayConfigError: WXPAY_PLATFORM_CERT_PATH 未配置或证书不可读。
        """
        cert_path = get_settings().wxpay_platform_cert_path
        if not cert_path:
            raise PayConfigError("WXPAY_PLATFORM_CERT_PATH not configured")
        message = f"{timestamp}\n{nonce}\n{body_text}\n"
        public_key = self._load_platform_public_key(cert_path)
        try:
            public_key.verify(
                base64.b64decode(signature_b64),
                message.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except (InvalidSignature, ValueError):
            return False

    @staticmethod
    def decrypt_resource(associated_data: str, nonce: str, ciphertext_b64: str) -> dict:
        """解密回调 resource 字段（AES-256-GCM，APIv3 密钥）。

        Args:
            associated_data: resource.associated_data（可为空串）。
            nonce: resource.nonce。
            ciphertext_b64: resource.ciphertext（base64）。

        Returns:
            解密后的业务 JSON 字典（含 out_trade_no/transaction_id 等）。

        Raises:
            PayConfigError: WXPAY_API_V3_KEY 未配置或长度非 32 字节。
            ValueError: 解密失败（密文被篡改或密钥错误）。
        """
        key = (get_settings().wxpay_api_v3_key or "").encode("utf-8")
        if len(key) != 32:
            raise PayConfigError("WXPAY_API_V3_KEY must be configured as 32 bytes")
        try:
            plaintext = AESGCM(key).decrypt(
                nonce.encode("utf-8"),
                base64.b64decode(ciphertext_b64),
                (associated_data or "").encode("utf-8"),
            )
        except InvalidTag as exc:
            # 统一转 ValueError：调用方不依赖 cryptography 异常类型
            raise ValueError("wxpay resource decrypt failed: invalid tag") from exc
        return json.loads(plaintext.decode("utf-8"))

    def _ensure_credentials(self) -> Dict[str, str]:
        """校验并收集微信支付商户凭据。

        Returns:
            凭据字典 {mch_id, serial_no, private_key_path, api_v3_key}。

        Raises:
            PayConfigError: 任一凭据缺失时抛出（信息仅指明缺失项，不伪造）。
        """
        settings = get_settings()
        missing = []
        if not settings.wxpay_mch_id:
            missing.append("WXPAY_MCH_ID")
        if not settings.wxpay_serial_no:
            missing.append("WXPAY_SERIAL_NO")
        if not settings.wxpay_private_key_path:
            missing.append("WXPAY_PRIVATE_KEY_PATH")
        if not settings.wxpay_api_v3_key:
            missing.append("WXPAY_API_V3_KEY")
        if missing:
            # 待业务方提供凭据：显式失败优于静默降级
            raise PayConfigError(f"wxpay credentials not configured: {', '.join(missing)}")
        return {
            "mch_id": settings.wxpay_mch_id,
            "serial_no": settings.wxpay_serial_no,
            "private_key_path": settings.wxpay_private_key_path,
            "api_v3_key": settings.wxpay_api_v3_key,
        }

    def _post_v3_json(self, url_path: str, body_dict: Dict[str, Any]) -> Dict[str, Any]:
        """发起带商户签名的 V3 JSON POST 请求并解析响应（下单/退款共用）。

        Args:
            url_path: 接口路径（如 /v3/pay/transactions/jsapi）。
            body_dict: 请求体字典（序列化为 JSON 原文参与签名）。

        Returns:
            渠道响应 JSON 字典（HTTP 200 时）。

        Raises:
            WxPayRemoteError: 网络失败、HTTP 非 2xx 或响应体非 JSON。
        """
        body_text = json.dumps(body_dict, ensure_ascii=False, separators=(",", ":"))
        try:
            with httpx.Client(
                timeout=self._TIMEOUT_SECONDS, transport=type(self)._transport
            ) as client:
                resp = client.post(
                    f"{self._API_BASE}{url_path}",
                    content=body_text.encode("utf-8"),
                    headers={
                        "Authorization": self.build_authorization_header(
                            "POST", url_path, body_text
                        ),
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "jiaban-backend/wxpay-v3",
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning("wxpay v3 request failed: %s %s", url_path, exc)
            raise WxPayRemoteError(f"wxpay v3 request failed: {url_path}: {exc}") from exc
        if resp.status_code // 100 != 2:
            # 渠道错误：取响应体 errcode/errmsg（若有）留痕，不含敏感头
            try:
                err = resp.json()
            except ValueError:
                err = {}
            logger.warning(
                "wxpay v3 non-2xx: %s status=%d code=%s",
                url_path,
                resp.status_code,
                err.get("code", ""),
            )
            raise WxPayRemoteError(
                f"wxpay v3 non-2xx: {url_path} status={resp.status_code} "
                f"code={err.get('code', '')} message={err.get('message', '')}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise WxPayRemoteError(f"wxpay v3 non-json response: {url_path}") from exc

    def _micro_to_fen(self, amount_micro: int) -> int:
        """micro 金额换算为分（微信 V3 报文单位），非整分时报错。

        Args:
            amount_micro: micro 整数金额（1 元 = 1_000_000 micro）。

        Returns:
            对应的分数额（整数）。

        Raises:
            ValueError: 金额非正数或不足整分（10_000 micro）时抛出。
        """
        if not isinstance(amount_micro, int) or amount_micro <= 0:
            raise ValueError("amount_micro must be a positive int (micro)")
        total_fen, rem = divmod(amount_micro, self._MICRO_PER_FEN)
        if rem:
            raise ValueError("amount_micro must align to fen (multiple of 10000)")
        return total_fen

    def _build_jsapi_pay_params(self, prepay_id: str) -> Dict[str, str]:
        """构造小程序 requestPayment 调起参数（二次签名）。

        签名串口径（微信支付 V3 规范）：换行拼接
        "appId\\ntimeStamp\\nnonceStr\\npackage\\n"，商户私钥 RSA-SHA256。

        Args:
            prepay_id: 下单接口返回的预支付交易会话标识。

        Returns:
            JSAPI 五参数字典 {appId, timeStamp, nonceStr, package, signType, paySign}。

        Raises:
            PayConfigError: WX_APPID 缺失或商户私钥不可用。
        """
        settings = get_settings()
        if not settings.wx_appid:
            raise PayConfigError("WX_APPID not configured (jsapi order requires it)")
        timestamp = str(int(time.time()))
        nonce_str = uuid.uuid4().hex
        package = f"prepay_id={prepay_id}"
        message = f"{settings.wx_appid}\n{timestamp}\n{nonce_str}\n{package}\n"
        pay_sign = base64.b64encode(
            self._load_private_key().sign(
                message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
            )
        ).decode("utf-8")
        return {
            "appId": settings.wx_appid,
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": pay_sign,
        }

    def create_order(self, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """V3 JSAPI 下单（POST /v3/pay/transactions/jsapi，商户私钥签名）。

        Args:
            order_info: 订单要素（out_trade_no/amount_micro/description/
                openid，openid 为付款用户在 appid 下的 openid，必填）。

        Returns:
            {"channel": "wxpay", "out_trade_no": ..., "prepay_id": ...,
            "pay_params": JSAPI 五参数}。

        Raises:
            PayConfigError: 商户凭据/WX_APPID/WXPAY_NOTIFY_URL 缺失（列全缺失项）。
            ValueError: openid/out_trade_no 缺失或金额非法（非整分）。
            WxPayRemoteError: 网络失败或渠道返回错误。
        """
        creds = self._ensure_credentials()
        openid = order_info.get("openid")
        out_trade_no = order_info.get("out_trade_no")
        if not openid:
            raise ValueError("openid is required for jsapi order")
        if not out_trade_no:
            raise ValueError("out_trade_no is required")
        total_fen = self._micro_to_fen(int(order_info.get("amount_micro") or 0))
        settings = get_settings()
        if not settings.wx_appid:
            raise PayConfigError("WX_APPID not configured (jsapi order requires it)")
        if not settings.wxpay_notify_url:
            raise PayConfigError("WXPAY_NOTIFY_URL not configured")
        body = {
            "appid": settings.wx_appid,
            "mchid": creds["mch_id"],
            "description": str(order_info.get("description") or "jiaban-order"),
            "out_trade_no": str(out_trade_no),
            "notify_url": settings.wxpay_notify_url,
            "amount": {"total": total_fen, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        data = self._post_v3_json("/v3/pay/transactions/jsapi", body)
        prepay_id = data.get("prepay_id")
        if not prepay_id:
            raise WxPayRemoteError("wxpay jsapi order returned no prepay_id")
        return {
            "channel": "wxpay",
            "out_trade_no": str(out_trade_no),
            "prepay_id": prepay_id,
            "pay_params": self._build_jsapi_pay_params(prepay_id),
        }

    def handle_notification(
        self, timestamp: str, nonce: str, body_text: str, signature_b64: str
    ) -> Dict[str, Any]:
        """V3 回调通知完整处理：验签 → 解析 → 解密 resource。

        任何一步失败均抛异常，调用方必须拒绝该回调且不更新订单
        （billing_api 现有流程：验签 False → 1504，订单状态保持不变）。

        Args:
            timestamp: Wechatpay-Timestamp 头。
            nonce: Wechatpay-Nonce 头。
            body_text: 回调请求体原文（JSON，含 resource 密文段）。
            signature_b64: Wechatpay-Signature 头（base64）。

        Returns:
            解密后的业务明文字典（含 out_trade_no/transaction_id 等）。

        Raises:
            ValueError: 验签失败或解密失败（密文被篡改/密钥不符）。
            PayConfigError: 平台证书/APIv3 密钥未配置。
        """
        if not self.verify_notification_signature(timestamp, nonce, body_text, signature_b64):
            logger.warning("wxpay notification signature verify failed, reject")
            raise ValueError("wxpay notification signature verify failed")
        payload = json.loads(body_text)
        resource = payload.get("resource") or {}
        return self.decrypt_resource(
            resource.get("associated_data") or "",
            resource.get("nonce") or "",
            resource.get("ciphertext") or "",
        )

    def verify_callback(self, transaction_id: str, sign: str) -> bool:
        """V3 回调验签适配（对接既有 mock-pay 端点签名 (transaction_id, sign)）。

        sign 参数为本通道约定的「通知信封」：base64(JSON)，
        JSON 含 {"t": Wechatpay-Timestamp, "n": Wechatpay-Nonce,
        "s": Wechatpay-Signature, "b": 回调 body 原文}。真实 V3 通知由
        回调网关/转发层编码为该信封后投递既有端点；后续若新增独立 V3
        回调端点，可直接改走 handle_notification（扩展位，端点契约不变）。

        任何一步失败（信封解析/验签/解密/transaction_id 不一致）一律返回
        False——调用方拒绝回调且不更新订单（状态机与幂等逻辑零改动）。

        Args:
            transaction_id: 渠道交易号（须与解密 resource 内一致才放行）。
            sign: 通知信封（base64(JSON)）。

        Returns:
            全部校验通过 True；任一失败 False。

        Raises:
            PayConfigError: 平台证书/APIv3 密钥未配置（配置缺失与验签失败
            语义不同，向上抛出由调用方按 1901 兜底）。
        """
        try:
            envelope = json.loads(base64.b64decode(sign).decode("utf-8"))
            resource = self.handle_notification(
                envelope["t"], envelope["n"], envelope["b"], envelope["s"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            # 含信封解析失败/验签失败/解密失败：拒绝且不更新订单
            logger.warning("wxpay callback reject: %s", exc)
            return False
        if transaction_id and resource.get("transaction_id") != transaction_id:
            # 交易号与通知明文不一致：拒绝（防伪造/错配）
            logger.warning(
                "wxpay callback transaction_id mismatch: %s", transaction_id
            )
            return False
        return True

    def refund(
        self,
        out_trade_no: str,
        transaction_id: Optional[str],
        amount_micro: int,
        reason: str,
    ) -> Dict[str, Any]:
        """V3 退款（POST /v3/refund/domestic/refunds，商户私钥签名）。

        退款单号口径：out_refund_no = f"{out_trade_no}R"（确定性）——同
        订单重复发起退款为同一退款单号，微信侧幂等，不重复退资金。

        Args:
            out_trade_no: 商户订单号。
            transaction_id: 渠道交易号（提供时优先用作退款定位）。
            amount_micro: 退款金额（micro 整数，须整分且 ≤ 订单金额）。
            reason: 退款原因（审计留痕用）。

        Returns:
            {"status": 渠道退款状态, "channel": "wxpay", "out_trade_no": ...,
            "refund_id": ..., "out_refund_no": ...}。

        Raises:
            PayConfigError: 商户凭据未配置（一次性列全缺失项）。
            ValueError: 金额非法（非整分/非正数）。
            WxPayRemoteError: 网络失败或渠道返回错误。
        """
        creds = self._ensure_credentials()
        refund_fen = self._micro_to_fen(amount_micro)
        out_refund_no = f"{out_trade_no}R"
        body: Dict[str, Any] = {
            "out_refund_no": out_refund_no,
            "reason": (reason or "")[:80],
            "amount": {"refund": refund_fen, "currency": "CNY"},
        }
        if transaction_id:
            body["transaction_id"] = transaction_id
            body["amount"]["total"] = refund_fen
        else:
            body["out_trade_no"] = out_trade_no
            body["amount"]["total"] = refund_fen
        data = self._post_v3_json("/v3/refund/domestic/refunds", body)
        return {
            "status": data.get("status", "PROCESSING"),
            "channel": "wxpay",
            "out_trade_no": out_trade_no,
            "refund_id": data.get("refund_id", ""),
            "out_refund_no": out_refund_no,
        }


def get_pay_provider() -> PayProvider:
    """按 settings.pay_provider 分发支付通道实例（mock/wxpay）。

    Returns:
        PayProvider: 对应通道实现。

    Raises:
        PayConfigError: pay_provider='wxpay' 且商户凭据缺失时抛出；
                        pay_provider 取值未知时抛出。
    """
    settings = get_settings()
    if settings.pay_provider == "mock":
        # 默认通道：与既有 mock-pay 语义完全一致
        return MockPayProvider()
    if settings.pay_provider == "wxpay":
        # 微信通道：分发即校验凭据（缺商户号/证书显式失败，符合"启动明确报错"语义）
        provider = WxPayProvider()
        provider._ensure_credentials()
        return provider
    raise PayConfigError(f"unknown pay_provider: {settings.pay_provider}")
# -*- coding: utf-8 -*-
"""认证通道抽象模块（spec D1 通道收口：dev / wx 统一 authenticate 接口）。

认证能力收口为 AuthProvider 抽象（credentials → {openid, session_key?}），
auth_api 通过 get_auth_provider() 工厂按配置分发，不再感知具体通道：
- DevAuthProvider：开发设备码通道（默认），device_id 确定性哈希为模拟 openid；
- WxAuthProvider：微信 code2session 生产实现——httpx 真实 HTTP 调用（超时与
  网络错误映射）、微信 errcode 明确归类与日志，凭据（WX_APPID/WX_SECRET）
  填入 .env 即切换生产，无需改代码。

口径：openid 明文不落库、不出响应（CG13）；session_key 仅由调用方加密留存
（wx_session_key_enc 列 + core.crypto 加密工具），同样不出响应；凭据缺失时
一次性列全全部缺失配置项显式抛 AuthConfigError，不伪造、不静默回退 dev。
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import get_settings
from ..core.crypto import sha256_hex

# 通道专用日志器（渠道 errcode / 网络失败留痕，不记录 code 与凭据）
logger = logging.getLogger("jiaban.auth")


class AuthConfigError(Exception):
    """认证通道配置缺失异常（如 WX_APPID/WX_SECRET 未提供）。

    Attributes:
        message: 人类可读的缺失项描述（用于日志与启动校验失败输出）。
    """

    pass


class WxAuthNetworkError(AuthConfigError):
    """微信通道网络异常（超时/连接失败/非 200 响应/响应非 JSON）。

    继承 AuthConfigError：调用方（auth_api）既有 except AuthConfigError
    兜底链路（→ 1901/503）无需感知细分类型，行为零变化。

    Attributes:
        message: 含失败原因的人类可读描述（不包含 code 与凭据）。
    """

    pass


class WxAuthApiError(AuthConfigError):
    """微信渠道业务异常（code2session 返回 errcode != 0）。

    继承 AuthConfigError：同上沿用调用方既有兜底链路，不泄露凭据细节。

    Attributes:
        message: 含 errcode/errmsg 与映射提示的描述。
    """

    pass


# 微信 errcode → 人类可读提示（仅列常见码；未收录码按 errmsg 原样透出）
_WX_ERRCODE_HINTS: Dict[int, str] = {
    40029: "invalid code（js_code 无效或已过期）",
    45011: "频率限制（API 配额达限，请稍后重试）",
    40163: "code been used（js_code 已被使用，不可重复兑换）",
    40013: "invalid appid（AppID 错误或与 AppSecret 不匹配）",
    -1: "微信系统繁忙（请稍后重试）",
}


class AuthProvider(ABC):
    """认证通道抽象：authenticate(credentials) -> dict{openid, session_key?}。

    约定：openid 为通道内全局唯一且确定性的明文标识（由实现保证幂等——
    同一用户同一入口反复 authenticate 得到同一 openid）；session_key 可缺失。
    """

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """执行通道认证并换取用户标识。

        Args:
            credentials: 通道凭据（dev: {device_id}；wx: {code}）。

        Returns:
            {"openid": str, "session_key": Optional[str]}。

        Raises:
            AuthConfigError: 通道凭据未配置或渠道返回配置类错误时抛出。
        """
        raise NotImplementedError


class DevAuthProvider(AuthProvider):
    """开发设备码通道（现状语义）：openid = sha256_hex('dev:' + device_id)。

    与既有 /auth/dev-login 完全一致：同一 device_id 恒定映射同一 openid
    （幂等登录），不产生 session_key。
    """

    def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """设备码换取确定性模拟 openid（幂等）。

        Args:
            credentials: {"device_id": 客户端设备唯一标识}。

        Returns:
            {"openid": sha256_hex('dev:'+device_id), "session_key": None}。

        Raises:
            AuthConfigError: 无（dev 通道无外部凭据依赖）。
            ValueError: device_id 缺失时抛出（防御性，正常由 422 拦截）。
        """
        device_id = credentials.get("device_id")
        if not device_id:
            raise ValueError("device_id is required")
        # 确定性哈希：同 device_id 恒得同 openid（幂等登录语义）
        return {"openid": sha256_hex(f"dev:{device_id}"), "session_key": None}


def _wx_missing_credential_names() -> List[str]:
    """收集微信登录通道全部缺失配置项（一次性列全，不逐个报）。

    Returns:
        缺失配置项名称列表（如 ["WX_APPID", "WX_SECRET"]；无缺失为空表）。
    """
    settings = get_settings()
    missing: List[str] = []
    if not settings.wx_appid:
        missing.append("WX_APPID")
    if not settings.wx_secret:
        missing.append("WX_SECRET")
    return missing


class WxAuthProvider(AuthProvider):
    """微信 code2session 生产实现（填入 WX_APPID/WX_SECRET 即切换生产）。

    接入端点：
        GET https://api.weixin.qq.com/sns/jscode2session
            ?appid=&secret=&js_code=&grant_type=authorization_code

    依赖配置（.env 注入，缺失时一次性列全并显式抛 AuthConfigError）：
    - WX_APPID：小程序 AppID；
    - WX_SECRET：小程序 AppSecret。

    异常归类（均为 AuthConfigError 子类，调用方兜底链路不变）：
    - WxAuthNetworkError：超时/连接失败/HTTP 非 200/响应非 JSON；
    - WxAuthApiError：渠道 errcode != 0（40029 invalid code、45011 频率
      限制、40163 code 已用、40013 appid 错误、-1 系统繁忙等明确映射）。
    """

    # code2session 端点（微信官方固定地址）
    _WX_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
    # 请求超时秒数（登录链路同步等待，超时按通道不可用处理）
    _TIMEOUT_SECONDS = 5.0
    # 可注入 HTTP 传输层：生产为 None（真实网络）；测试注入 httpx.MockTransport
    _transport: Optional[httpx.BaseTransport] = None

    def _request_code2session(self, appid: str, secret: str, code: str) -> httpx.Response:
        """发起 code2session GET 请求（transport 可注入，mock HTTP 用）。

        Args:
            appid: 小程序 AppID。
            secret: 小程序 AppSecret（仅作为查询参数发出，不落日志）。
            code: wx.login() 获取的临时登录凭证（仅作为查询参数发出）。

        Returns:
            httpx.Response（HTTP 层成功，状态码由调用方判定）。

        Raises:
            WxAuthNetworkError: 超时/连接失败等 httpx.HTTPError 异常映射。
        """
        try:
            # transport=None 时使用默认真实网络传输；测试注入 MockTransport
            with httpx.Client(
                timeout=self._TIMEOUT_SECONDS, transport=type(self)._transport
            ) as client:
                return client.get(
                    self._WX_CODE2SESSION_URL,
                    params={
                        "appid": appid,
                        "secret": secret,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.HTTPError as exc:
            # 超时（TimeoutException）/连接失败等统一归类为网络异常（→1901 兜底）
            logger.warning("wx code2session network error: %s", exc)
            raise WxAuthNetworkError(f"wx code2session network error: {exc}") from exc

    def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """微信 code 换取 openid + session_key（code2session 生产实现）。

        Args:
            credentials: {"code": wx.login() 获取的临时登录凭证}。

        Returns:
            {"openid": 用户唯一标识, "session_key": 会话密钥（可能为 None，
            由调用方加密留存 wx_session_key_enc，明文不落库不出响应）}。

        Raises:
            AuthConfigError: WX_APPID/WX_SECRET 缺失（一次性列全缺失项）。
            WxAuthNetworkError: 网络超时/连接失败/HTTP 非 200/响应非 JSON。
            WxAuthApiError: 渠道 errcode != 0（含 40029/45011 等明确映射）。
            ValueError: code 缺失时抛出（防御性，正常由 422 拦截）。
        """
        # 凭据缺失检查：一次性列全（WX_APPID/WX_SECRET），不逐个报
        missing = _wx_missing_credential_names()
        if missing:
            raise AuthConfigError("/".join(missing) + " not configured")
        code = credentials.get("code")
        if not code:
            raise ValueError("code is required")

        settings = get_settings()
        resp = self._request_code2session(settings.wx_appid, settings.wx_secret, code)
        if resp.status_code != 200:
            logger.warning(
                "wx code2session http status: %d", resp.status_code
            )
            raise WxAuthNetworkError(
                f"wx code2session http status: {resp.status_code}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            # 非 JSON 响应（网关拦截页等）：按通道不可用处理
            logger.warning("wx code2session non-json response")
            raise WxAuthNetworkError("wx code2session non-json response") from exc

        errcode = data.get("errcode", 0)
        if errcode != 0:
            # 渠道错误：明确映射常见 errcode 并留痕（不含 code 与凭据）
            hint = _WX_ERRCODE_HINTS.get(errcode, "")
            logger.warning(
                "wx code2session failed: errcode=%s errmsg=%s",
                errcode,
                data.get("errmsg", ""),
            )
            detail = f"wx code2session failed: errcode={errcode}"
            if hint:
                detail += f"（{hint}）"
            detail += f" errmsg={data.get('errmsg', '')}"
            raise WxAuthApiError(detail)

        openid = data.get("openid")
        if not openid:
            # errcode=0 但缺 openid：按渠道协议异常处理
            logger.warning("wx code2session returned no openid")
            raise WxAuthApiError("wx code2session returned no openid")
        # openid 明文仅供调用方即时加密，session_key 加密留存，均不落日志
        return {"openid": openid, "session_key": data.get("session_key")}


def get_auth_provider() -> AuthProvider:
    """按 settings.auth_provider 分发认证通道实例（dev/wx）。

    启动校验语义：auth_provider='wx' 但凭据缺失时，在工厂分发处即抛
    AuthConfigError（一次性列全全部缺失配置项，运行期首次调用显式失败，
    符合 spec"配置不完整启动明确报错"要求），不静默回退 dev。

    Returns:
        AuthProvider: 对应通道实现。

    Raises:
        AuthConfigError: 'wx' 缺凭据（列全缺失项），或 auth_provider
                         取值未知时抛出。
    """
    settings = get_settings()
    if settings.auth_provider == "dev":
        # 默认通道：与既有 dev-login 语义完全一致
        return DevAuthProvider()
    if settings.auth_provider == "wx":
        # 微信通道：分发即校验凭据（一次性列全缺失项，显式失败不回退）
        missing = _wx_missing_credential_names()
        if missing:
            raise AuthConfigError("/".join(missing) + " not configured")
        return WxAuthProvider()
    raise AuthConfigError(f"unknown auth_provider: {settings.auth_provider}")

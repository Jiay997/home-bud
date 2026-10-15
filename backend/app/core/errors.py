# -*- coding: utf-8 -*-
"""统一错误码与业务异常模块。

错误码分段遵循架构设计文档 §4.2：
0 成功 / 1000 参数 / 1100 鉴权越权 / 1200 限流额度 / 1300 合规同意 /
1400 问答风险 / 1500 支付 / 1600 后台 / 1900 故障。
"""
from typing import Any, Dict, Optional


class ApiError(Exception):
    """业务异常类。

    服务层与路由层通过抛出本异常终止处理流，
    由全局异常处理器转换为统一包络响应。

    Attributes:
        code: 4 位错误码（见架构文档 §4.2）。
        message: 用户可读的错误描述。
        http_status: HTTP 状态码。
        retryable: 是否可重试。
        retry_after: 建议重试等待秒数（限流场景）。
        details: 附加错误明细。
    """

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        retryable: bool = False,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初始化业务异常。

        Args:
            code: 4 位错误码。
            message: 错误描述。
            http_status: HTTP 状态码，默认 400。
            retryable: 是否可重试，默认 False。
            retry_after: 建议重试等待秒数。
            details: 附加错误明细字典。
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.retry_after = retry_after
        self.details = details or {}


# ---------- 1000 通用与参数 ----------
ERR_PARAM = (1001, "参数校验失败", 422)
ERR_NOT_FOUND = (1002, "资源不存在", 404)
ERR_OPTIMISTIC_LOCK = (1003, "内容已被更新，请刷新", 409)
ERR_IDEMPOTENT_PROCESSING = (1004, "相同请求正在处理中", 409)
ERR_UPSTREAM_TIMEOUT = (1005, "上游服务超时", 504)

# ---------- 1100 鉴权与越权 ----------
ERR_NO_SESSION = (1101, "会话缺失或已失效", 401)
ERR_FORBIDDEN = (1102, "无权访问该资源", 403)
ERR_ADMIN_FORBIDDEN = (1103, "当前角色无此权限", 403)
ERR_MFA_REQUIRED = (1104, "MFA 校验未通过", 403)

# ---------- 1200 限流与配额 ----------
ERR_RATE_LIMITED = (1201, "请求过于频繁", 429)
ERR_QUOTA_EXHAUSTED = (1202, "今日免费额度已用尽", 429)
ERR_ACTIVE_STREAM = (1203, "已有一个进行中的问答会话", 409)
ERR_DAILY_LIMIT = (1204, "超出单日请求上限", 429)

# ---------- 1300 合规与同意 ----------
ERR_BASE_CONSENT = (1301, "请先同意用户协议与免责声明", 403)
ERR_CHILD_CONSENT = (1302, "需先完成儿童信息单独同意", 403)
ERR_CONTENT_AUDIT = (1303, "内容安全送检未通过", 403)
ERR_LEGAL_RETENTION = (1304, "该数据处于法定留存期，无法删除", 403)

# ---------- 1400 问答与风险 ----------
ERR_RISK_BLOCKED = (1401, "该问题已停止生成回答", 200)
ERR_RISK_UNAVAILABLE = (1402, "风险扫描服务暂不可用", 503)
ERR_SAFETY_AGENT_FAILED = (1403, "家庭安全服务暂不可用", 503)
ERR_ALL_AGENT_FAILED = (1404, "回答生成失败，请稍后重试", 503)
ERR_SESSION_ORPHANED = (1405, "会话已失效", 410)

# ---------- 1500 支付与订单 ----------
ERR_ORDER_STATE = (1501, "订单状态不允许该操作", 409)
ERR_PRICE_MISMATCH = (1502, "价格与商品配置不一致", 409)
ERR_DUPLICATE_ORDER = (1503, "重复下单", 409)
ERR_PAY_VERIFY = (1504, "支付回调验签失败", 400)

# ---------- 1600 后台与配置 ----------
ERR_ADMIN_LOCK = (1601, "内容已被更新，请刷新后重试", 409)
ERR_CONFIRM_REQUIRED = (1602, "危险操作需要二次确认", 403)
ERR_DOMAIN_SCOPE = (1603, "超出您的授权领域范围", 403)
ERR_EXPORT_QUEUE = (1604, "导出任务排队中，请稍后查看", 202)

# ---------- 1900 服务端故障 ----------
ERR_DEPENDENCY = (1901, "依赖服务不可用", 503)
ERR_UNKNOWN = (1902, "服务内部错误", 500)


def raise_err(
    spec: tuple, retryable: bool = False, retry_after: int = None, details: dict = None
) -> None:
    """按错误码常量快速抛出业务异常。

    Args:
        spec: (code, message, http_status) 三元组错误码常量。
        retryable: 是否可重试。
        retry_after: 建议重试等待秒数。
        details: 附加错误明细。

    Raises:
        ApiError: 始终抛出对应错误的业务异常。
    """
    code, message, http_status = spec
    raise ApiError(
        code=code,
        message=message,
        http_status=http_status,
        retryable=retryable,
        retry_after=retry_after,
        details=details,
    )

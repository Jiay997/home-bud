# -*- coding: utf-8 -*-
"""统一响应包络模块。

所有非流式接口返回 `{code, message, data, request_id, trace_id}` 结构；
失败时附加 `error: {type, retryable, retry_after, details}`。
request_id/trace_id 从请求上下文变量获取（由中间件注入）。
"""
from contextvars import ContextVar
from typing import Any, Optional

# 请求级上下文变量：逐请求唯一 ID 与贯穿链路的追踪 ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def ok(data: Any = None, message: str = "ok") -> dict:
    """构造成功包络。

    Args:
        data: 业务数据载荷。
        message: 提示消息，默认 "ok"。

    Returns:
        符合统一包络结构的字典。
    """
    return {
        "code": 0,
        "message": message,
        "data": data,
        "request_id": request_id_var.get(),
        "trace_id": trace_id_var.get(),
    }


def fail(
    code: int,
    message: str,
    error: Optional[dict] = None,
) -> dict:
    """构造失败包络。

    Args:
        code: 4 位错误码。
        message: 错误描述。
        error: 附加错误对象 {type, retryable, retry_after, details}。

    Returns:
        符合统一包络结构的字典。
    """
    body: dict = {
        "code": code,
        "message": message,
        "data": None,
        "request_id": request_id_var.get(),
        "trace_id": trace_id_var.get(),
    }
    if error is not None:
        body["error"] = error
    return body

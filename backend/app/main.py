# -*- coding: utf-8 -*-
"""小光景后端 FastAPI 应用入口。

装配职责：
- 全局中间件（request_id/trace_id、CORS）
- 统一异常处理（ApiError / 校验错误 / 未知异常 → 统一包络）
- 路由注册（/api/v1/*）
- /media 静态资源（档案头像/相册文件，uuid 文件名防枚举）
- /health 健康检查（DB 连通 + 模型白名单状态）
- 启动校验：模型白名单硬失败（架构文档 §2.2：未登记 provider 拒绝启动）
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core import envelope
from .core.config import get_settings
from .core.errors import ApiError, ERR_UNKNOWN
from .core.observe import metrics
from .db import check_db_connected
from .services.media_store import media_root

logger = logging.getLogger("jiaban")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时执行模型白名单校验与定时任务装配。

    Args:
        app: FastAPI 应用实例。

    Yields:
        None。

    Raises:
        RuntimeError: 模型白名单校验失败（硬失败，不降级）。
    """
    settings = get_settings()
    # 模型白名单校验：白名单为空即拒绝启动
    if not settings.model_whitelist:
        raise RuntimeError("model whitelist is empty, refusing to start")
    logger.info(
        "model whitelist loaded: %s", [m["model"] for m in settings.model_whitelist]
    )
    # 定时任务（对账示例/断点过期清理/渠道复核提醒）——懒加载，失败不阻断启动
    try:
        from .jobs.scheduler import start_scheduler

        start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler start skipped: %s", exc)
    yield
    try:
        from .jobs.scheduler import stop_scheduler

        stop_scheduler()
    except Exception:  # noqa: BLE001
        pass


# OpenAPI 文档分组标签（12 组，与各路由 tags 对应）
OPENAPI_TAGS = [
    {"name": "系统", "description": "健康检查、合规文案下发、运行指标与告警"},
    {"name": "C端-认证同意", "description": "登录认证与用户协议/儿童信息分层同意、撤回"},
    {"name": "C端-档案", "description": "儿童/宠物档案管理与当前问答对象设置"},
    {"name": "C端-问答", "description": "问答会话创建、SSE 流式问答、风险拦截与申诉、危机渠道"},
    {"name": "C端-测评", "description": "气质测评作答/提交/报告与历史记录查询"},
    {"name": "C端-商业化", "description": "商品、订单与会员权益"},
    {"name": "C端-权利反馈", "description": "个人信息权利请求与意见反馈"},
    {"name": "C端-健康与笔记", "description": "孩子/宠物健康档案、体检报告上传与复查提醒、个人笔记知识手册"},
    {"name": "后台-知识库", "description": "知识条目 CRUD、审核发布、版本回滚与内容追溯"},
    {"name": "后台-词库", "description": "风险/敏感词库维护与规则配置、规则测试器"},
    {"name": "后台-处置", "description": "后台处置类操作（申诉复核、追溯处置等）"},
    {"name": "后台-配置", "description": "系统开关与配置版本管理"},
]

app = FastAPI(
    title="小光景 · 一家人的养育参考 API",
    version="1.0.0",
    description="FastAPI + LangGraph 多智能体后端。统一包络：{code,message,data,request_id,trace_id}。",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# CORS：开发环境全放开（生产收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    """请求追踪中间件：注入 request_id / trace_id 到上下文变量。

    Args:
        request: 当前请求。
        call_next: 下游处理链。

    Returns:
        响应对象。
    """
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:16]}"
    trace_id = request.headers.get("X-Trace-Id") or f"tr_{uuid.uuid4().hex[:16]}"
    envelope.request_id_var.set(request_id)
    envelope.trace_id_var.set(trace_id)
    response = await call_next(request)
    # 请求指标埋点：计数/错误/延迟（进程内聚合，经 GET /metrics 暴露）
    metrics.observe_request(
        response.status_code, (time.perf_counter() - started) * 1000
    )
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """业务异常处理器：转换为统一失败包络。

    Args:
        request: 当前请求。
        exc: 业务异常。

    Returns:
        JSONResponse（包络结构）。
    """
    body = envelope.fail(
        code=exc.code,
        message=exc.message,
        error={
            "type": f"e{exc.code}",
            "retryable": exc.retryable,
            "retry_after": exc.retry_after,
            "details": exc.details,
        },
    )
    return JSONResponse(status_code=exc.http_status, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数校验异常处理器：1001。

    Args:
        request: 当前请求。
        exc: 校验异常。

    Returns:
        JSONResponse（422 包络）。
    """
    # exc.errors() 可能带非可序列化值（multipart 的 loc 含 bytes、ctx 含异常对象），
    # 原样塞进 JSONResponse 会让本处理器抛错，把 422 伪装成 500/1902。
    errors = [
        {
            "loc": [x.decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else str(x)
                    for x in (e.get("loc") or [])],
            "msg": str(e.get("msg", "")),
            "type": str(e.get("type", "")),
        }
        for e in exc.errors()[:5]
    ]
    body = envelope.fail(
        code=1001,
        message="参数校验失败",
        error={"type": "validation", "retryable": False, "details": {"errors": errors}},
    )
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """未知异常兜底处理器：1902。

    Args:
        request: 当前请求。
        exc: 任意未捕获异常。

    Returns:
        JSONResponse（500 包络）。
    """
    logger.exception("unhandled error: %s", exc)
    body = envelope.fail(code=ERR_UNKNOWN[0], message=ERR_UNKNOWN[1])
    return JSONResponse(status_code=500, content=body)


@app.get("/api/v1/health", tags=["系统"])
def health():
    """健康检查端点。

    Returns:
        包络结构：报告 DB 连通与模型白名单状态。

    Raises:
        无（DB 不可达以 degraded 字段表达，不抛异常便于探活）。
    """
    settings = get_settings()
    db_ok = check_db_connected()
    return envelope.ok(
        {
            "service": "jiaban-backend",
            "db_connected": db_ok,
            "model_whitelist": [m["model"] for m in settings.model_whitelist],
            "llm_mock": settings.llm_mock,
        }
    )


# ---- 路由注册（模块化路由在 api 包中定义） ----
def _register_routers() -> None:
    """注册全部业务路由（集中装配，避免循环导入）。"""
    from .api.v1 import (
        admin_api, assessment_api, auth_api, billing_api, consent_api,
        feedback_api, health_api, history_api, kb_api, lexicon_api, metrics_api,
        notes_api, profiles_api, qa_api, rights_api, risk_api, safety_api, texts_api,
    )

    prefix = "/api/v1"
    app.include_router(texts_api.router, prefix=prefix)
    app.include_router(auth_api.router, prefix=prefix)
    app.include_router(consent_api.router, prefix=prefix)
    app.include_router(profiles_api.router, prefix=prefix)
    app.include_router(health_api.router, prefix=prefix)
    app.include_router(qa_api.router, prefix=prefix)
    app.include_router(risk_api.router, prefix=prefix)
    app.include_router(assessment_api.router, prefix=prefix)
    app.include_router(history_api.router, prefix=prefix)
    app.include_router(billing_api.router, prefix=prefix)
    app.include_router(rights_api.router, prefix=prefix)
    app.include_router(feedback_api.router, prefix=prefix)
    app.include_router(notes_api.router, prefix=prefix)
    # 后台路由
    app.include_router(admin_api.router, prefix=prefix)
    app.include_router(kb_api.router, prefix=prefix)
    app.include_router(lexicon_api.router, prefix=prefix)
    # 运行指标（系统观测）
    app.include_router(metrics_api.router, prefix=prefix)
    # 内容安全平台回调（机器对机器，HMAC 验签）
    app.include_router(safety_api.router, prefix=prefix)


_register_routers()

# ---- 静态资源：档案媒体（头像/相册） ----
# 开发/MVP 口径：/media 直出无鉴权，uuid4 文件名防枚举；生产演进切
# OSS + 签名 URL（deploy/README.md 已注明）
_media_dir = media_root()
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

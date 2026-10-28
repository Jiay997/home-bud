# =============================================================================
# Babe宝伴后端镜像 Dockerfile
#
# 构建方式（在仓库根目录执行，context 为仓库根）：
#   docker build -f deploy/backend.Dockerfile -t jiaban-backend .
#
# 说明：
#   - 基于 python:3.12-slim，与本地开发 Python 版本一致
#   - 先 COPY requirements.txt 单独安装依赖，充分利用 Docker 层缓存：
#     代码变更时无需重新下载依赖
#   - 使用非 root 用户 appuser 运行，遵循最小权限原则
# =============================================================================

FROM python:3.12-slim

# --- 基础环境变量 ---
# PYTHONDONTWRITEBYTECODE: 不生成 .pyc，减小镜像体积
# PYTHONUNBUFFERED: 日志实时输出到 stdout，便于 docker logs 查看
# PIP_NO_CACHE_DIR: pip 不留缓存，减小镜像体积
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=2

WORKDIR /app

# --- 第一步：仅复制依赖清单并安装（利用层缓存） ---
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- 第二步：复制后端源码 ---
COPY backend/ /app/

# --- 非 root 用户 ---
# 预创建档案媒体目录（头像/相册：/app/data/uploads）：named volume 首次
# 挂载会继承镜像内目录属主，保证 appuser 可写
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# --- 健康检查：请求 /api/v1/health ---
# 使用 python urllib（标准库），无需额外安装 curl/wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4).status == 200 else 1)" || exit 1

# --- 启动命令：uvicorn，worker 数由 UVICORN_WORKERS 环境变量控制（默认 2） ---
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]

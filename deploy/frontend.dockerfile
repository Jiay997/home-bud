# =============================================================================
# 小光景前端镜像 Dockerfile（多阶段构建）
#
# 构建方式（在仓库根目录执行，context 为仓库根）：
#   docker build -f deploy/frontend.dockerfile -t jiaban-frontend .
#
# 阶段一：node:20-alpine 执行 vite build 产出 dist/
# 阶段二：nginx:1.27-alpine 托管静态文件并反代 /api/
# =============================================================================

# ---------- 阶段一：前端构建 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制依赖清单并安装（利用 Docker 层缓存）
COPY frontend/package*.json /app/
RUN npm install

# 复制前端源码并构建
COPY frontend/ /app/
RUN npm run build

# ---------- 阶段二：nginx 运行时 ----------
FROM nginx:1.27-alpine

# 移除默认站点配置，使用小光景自定义配置
RUN rm -f /etc/nginx/conf.d/default.conf

# 静态资源
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx 配置（前端 history 路由回退 + /api/ 反向代理 + SSE 流式配置）
COPY deploy/nginx.conf /etc/nginx/conf.d/app.conf

EXPOSE 80

# nginx 官方镜像已内置健康检查指令兼容，这里显式声明，便于 compose 依赖判断
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

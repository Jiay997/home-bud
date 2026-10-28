# =============================================================================
# Babe宝伴前端镜像 Dockerfile（多阶段构建）
#
# 产出两个 Web 静态站点，由同一 nginx 容器托管：
#   /app/   → uni-app 跨端工程 client/ 的 H5 产物（与微信小程序同一套源码）
#   /admin/ → 后台管理端 admin-web/ 产物（Element Plus，Web-only）
#
# 构建方式（在仓库根目录执行，context 为仓库根）：
#   docker build -f deploy/frontend.dockerfile -t jiaban-frontend .
# =============================================================================

# ---------- 阶段一：构建 uni-app H5（client） ----------
FROM node:20-alpine AS client-builder

WORKDIR /app

# 先复制依赖清单并安装（利用 Docker 层缓存）
COPY client/package*.json /app/
RUN npm install

# 复制源码并构建 H5 产物（base=/app/ 由 client/vite.config.ts 控制）
COPY client/ /app/
RUN npm run build:h5

# ---------- 阶段二：构建后台管理端（admin-web） ----------
FROM node:20-alpine AS admin-builder

WORKDIR /admin

COPY admin-web/package*.json /admin/
RUN npm install

# 复制源码并构建（base=/admin/ 由 admin-web/vite.config.ts 控制）
COPY admin-web/ /admin/
RUN npm run build

# ---------- 阶段三：nginx 运行时 ----------
FROM nginx:1.27-alpine

# 移除默认站点配置，使用Babe宝伴自定义配置
RUN rm -f /etc/nginx/conf.d/default.conf

# 两个站点的静态产物
COPY --from=client-builder /app/dist/build/h5 /usr/share/nginx/html/app
COPY --from=admin-builder /admin/dist /usr/share/nginx/html/admin

# nginx 配置（双站点 history 路由回退 + /api/ 反向代理 + SSE 流式配置）
COPY deploy/nginx.conf /etc/nginx/conf.d/app.conf

EXPOSE 80

# 健康检查显式使用 127.0.0.1：容器内 localhost 可能解析为 IPv6 ::1，而 nginx 只监听 IPv4
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

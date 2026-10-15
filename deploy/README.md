# 小光景 Docker 部署指南

本目录包含一套开箱即用的容器化部署交付物：PostgreSQL 16 + FastAPI 后端 + nginx 前端，
一条 `docker compose up -d` 即可拉起全栈。

> **说明（2026-10-13）**：品牌名由「家伴」变更为「**小光景**」。数据库名、容器名、JWT 签发者、备份文件名等**内部标识沿用历史代号 `jiaban`**（既有数据卷与凭据依赖，不改动）；仅对外的界面与文档文案使用「小光景」。

## 文件清单

| 文件 | 作用 |
|------|------|
| `docker-compose.yml` | 编排 postgres / backend / frontend 三服务 |
| `backend.Dockerfile` | 后端镜像（python:3.12-slim，非 root 运行） |
| `frontend.dockerfile` | 前端镜像（node:20 构建 → nginx:1.27-alpine 托管） |
| `nginx.conf` | 静态托管 + /api/ 反代 + SSE 无缓冲流式配置 |
| `.env.example` | 环境变量模板（含中文注释与"待业务方提供"标注） |

## 快速启动

```powershell
# 1. 准备环境变量（在本 deploy/ 目录下）
cp .env.example .env
# 按注释修改 DB_PASSWORD / JWT_SECRET / FIELD_ENC_KEY / LLM_API_KEY 等必改项

# 2. 构建并启动（首次会构建镜像，约几分钟）
docker compose up -d

# 3. 查看状态
docker compose ps
```

启动后访问：

- 用户端：`http://localhost/app/`
- 管理端：`http://localhost/admin/`
- API 入口：`http://localhost/api/v1/...`（健康检查 `GET /api/v1/health`）

## 停止与清理

```powershell
docker compose down          # 停止并移除容器（保留数据卷 pgdata）
docker compose down -v       # ⚠️ 危险：同时删除 pgdata 数据卷，数据库数据将全部丢失
```

## 日志查看

```powershell
docker compose logs -f              # 全部服务实时日志
docker compose logs -f backend      # 仅后端
docker compose logs -f postgres     # 仅数据库
docker compose logs --tail 100 backend   # 最近 100 行
```

## 数据库备份与恢复

数据持久化在 named volume `pgdata` 中，`docker compose down` 不会丢失；
`down -v` 或 `docker volume rm` 才会删除。

**备份**（导出为宿主机上的 SQL 文件）：

```powershell
# 自定义格式（推荐，支持 pg_restore 并行/选择性恢复）
docker compose exec -T postgres pg_dump -U postgres -d jiaban -Fc -f /tmp/jiaban.dump
docker compose cp postgres:/tmp/jiaban.dump ./jiaban-$(Get-Date -Format yyyyMMdd).dump

# 纯 SQL 格式（可读，可直接 psql 导入）
docker compose exec -T postgres pg_dump -U postgres -d jiaban > ./jiaban-backup.sql
```

**恢复**：

```powershell
# 自定义格式：先复制进容器，再 pg_restore
docker compose cp ./jiaban-20260101.dump postgres:/tmp/jiaban.dump
docker compose exec -T postgres pg_restore -U postgres -d jiaban --clean --if-exists /tmp/jiaban.dump

# 纯 SQL 格式：
Get-Content ./jiaban-backup.sql -Raw | docker compose exec -T postgres psql -U postgres -d jiaban
```

> 恢复 `--clean --if-exists` 会先删旧表再导入，请确认目标库可被覆盖。

## Redis 缓存

compose 已内置 `redis:7-alpine` 服务（AOF 持久化，数据卷 `redisdata`）：

- **compose 部署自动启用**：backend 的 `environment` 已默认注入
  `REDIS_URL=redis://redis:6379/0`，并在 redis 健康检查通过后才启动
  （`depends_on: condition: service_healthy`），无需任何额外配置。
- **本地开发留空即进程内缓存**：脱离 compose 直接跑 uvicorn 时，
  `REDIS_URL` 留空（backend/.env 不配置）即回退进程内 TTL 缓存，
  单实例部署完全可用。
- **redis 容器停掉不会 500**：backend 启动/请求期通过 `get_cache()`
  工厂访问缓存，Redis 连接失败时自动回退进程内缓存并打告警日志，
  仅首次尝试连接；修复 redis 后重启 backend 容器即可切回。

## 向量库（Milvus 独立向量库）

检索主通道的向量存储后端为 **Milvus standalone 3.0.2**（spec milvus-vector-store，
2026-10-12 起接替 pgvector 主库扩展模式）——compose 编排三件套：

- **三服务**：`etcd(v3.5.25)` + `minio` + `milvus-standalone(v3.0.2)`，数据卷
  etcddata/miniodata/milvusdata；SDK 端口 `19531:19530`（宿主避让映射，compose
  内部走 milvus:19530）、健康检查端口 `9091`（`GET /healthz`）；三容器合计约
  **1~2GB 内存**，资源受限环境可将 `MILVUS_URI` 指向外部已有 Milvus 实例并
  不起三件套（backend env 已按 `${MILVUS_URI:-http://milvus:19530}` 可覆盖）。
- **集合 `jiaban_kb_entries`**：kb_id 主键 + embedding vec(2048)（智谱
  embedding-3）+ 过滤标量（status/kb_kind/domain/age_band/species，空值哨兵
  'any'）；HNSW(M=16, efConstruction=200) COSINE（搜索 ef=128）、集合级
  **Strong 一致性**（写后立读）、原生 upsert；正文不落 Milvus（命中后回主库
  取条目）；`retriever` 回查复核 published/child/pet（防御纵深）。
- **降级链（spec D6）**：`MILVUS_URI` 空 / pymilvus 缺失 / Milvus 不可达 →
  自动回退 hashing JSONB + Python 余弦降级路径（业务无感、无 500）；停
  Milvus 后重新拉起即自动恢复（探测失败不缓存）。
- **迁移/重建**：`python scripts/init_db.py`（ensure_rag_index 建集合）→
  `python scripts/reindex_rag.py`（全量重灌，幂等）；种子一条龙
  `init_db.py` → `seed_data.py`（内置 reindex）。
- **回滚保险**：旧 pgvector 路径全部保留（`data_kb_dense` 表 /
  `kb_entry.embedding_vec` 列 / 旧迁移脚本 deprecated）——恢复 llama-index
  依赖 + 旧版 `rag_index.py` 即回滚。

## 备份与恢复（backup_db.ps1 / restore_db.ps1）

scripts 目录提供宿主机侧数据库备份/恢复脚本（与上文「数据库备份与恢复」的
容器内 pg_dump 互补，适合本地开发与计划任务定时备份）。密码不硬编码：
优先取环境变量 `PGPASSWORD`，否则自动解析 `backend\.env` 的 `DATABASE_URL`。

**手动备份**（`-Fc` 自定义格式，文件名 `<库名>_yyyyMMdd_HHmmss.dump`，
成功后向 `OutDir\backup_log.txt` 留痕并按份数轮转删除最旧）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1
```

| 参数 | 说明 |
|------|------|
| `-DbName` | 目标库名（默认 jiaban） |
| `-OutDir` | 备份输出目录（默认 `d:\HomeBud\backups`，不存在自动创建） |
| `-Keep` | 保留份数（默认 7，超出自动删除最旧） |
| `-PgBin` | pg_dump 所在 bin 目录（可选，缺省按 PATH / 常见安装位置自动探测） |

**手动恢复**（`--clean --if-exists` 覆盖式恢复）。⚠️ 恢复前先停掉后端写入口
（`scripts\stop.ps1` 或 `docker compose stop backend`），避免恢复期间并发写入：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore_db.ps1 -BackupFile d:\HomeBud\backups\jiaban_yyyyMMdd_HHmmss.dump
```

默认交互输入 `y` 确认；自动化场景加 `-Force` 跳过确认。

**定时备份**（Windows 计划任务示例，每日 03:00，路径与时间按需调整）：

```powershell
schtasks /Create /TN "HomeBud-DBBackup" /TR "powershell -ExecutionPolicy Bypass -File d:\HomeBud\scripts\backup_db.ps1" /SC DAILY /ST 03:00
```

> 建议定期做恢复演练：用 `pg_restore -l <dump路径>` 校验备份文件可读，
> 或定期异机执行一次 restore_db.ps1 全量恢复，确保备份真正可用于容灾。

## 微信通道切换清单

认证/支付通道由 `AUTH_PROVIDER` / `PAY_PROVIDER` 控制，缺省走本地模拟实现；
微信凭据均为业务方外部凭据，**缺失时显式抛 `AuthConfigError` /
`PayConfigError`（不伪造、不静默回退）**。切换步骤统一为：
在 `backend\.env`（compose 部署为 `deploy\.env`）填入凭据 → 重启后端生效。

**微信登录（dev → wx）**

1. `.env` 配置：`AUTH_PROVIDER=wx`、`WX_APPID`（小程序 AppID）、
   `WX_SECRET`（小程序 AppSecret）；
2. 重启后端（`scripts\start.ps1` 或 `docker compose restart backend`）；
3. 缺 `WX_APPID`/`WX_SECRET` 时，登录入口在通道工厂分发处显式抛
   `AuthConfigError`（`WX_APPID/WX_SECRET not configured`），不会静默回退 dev。

**微信支付（mock → wxpay）**

1. `.env` 配置：`PAY_PROVIDER=wxpay` 及商户凭据：
   `WXPAY_MCH_ID`（商户号）、`WXPAY_SERIAL_NO`（API 证书序列号）、
   `WXPAY_PRIVATE_KEY_PATH`（商户私钥 apiclient_key.pem 路径）、
   `WXPAY_API_V3_KEY`（APIv3 密钥，32 字符）、
   `WXPAY_PLATFORM_CERT_PATH`（微信支付平台证书/公钥 PEM 路径，回调验签用）；
2. 回调域名要求：需公网可达的后端域名，回调落位 `/api/v1/billing` 路由
   （现 mock 回调端点为 `POST /api/v1/billing/orders/{order_no}/mock-pay`，
   wxpay V3 回调接入后同挂该路由），请在商户平台按此配置回调地址；
3. 重启后端生效；
4. 缺任一商户凭据时，`get_pay_provider()` 分发处显式抛 `PayConfigError`
   （错误信息逐项点名缺失项），下单/回调验签/退款三能力不会半可用。

**回退方式**

将 `AUTH_PROVIDER` 改回 `dev`、`PAY_PROVIDER` 改回 `mock` 后重启后端即可回退；
订单状态机与回调幂等逻辑与通道无关，切换/回退不影响既有订单数据。

## 生产切换清单

五项通道由 `.env` 配置驱动（缺省走本地实现），凭据/地址填入即切换生产、
删除即回退，**均不改代码**。缺凭据时通道工厂分发处显式抛
`AuthConfigError` / `PayConfigError` / `CryptoConfigError`（一次性列全
缺失项，不伪造、不静默回退）。compose 部署改 `deploy/.env` 后
`docker compose up -d backend` 重建生效；本地部署改 `backend/.env` 后
重启 uvicorn 生效。

**① 微信登录（dev → wx）**

1. `AUTH_PROVIDER=wx`，填入 `WX_APPID`（小程序 AppID）、`WX_SECRET`
   （小程序 AppSecret）；
2. 重启后端生效；缺任一项时登录入口抛 `AuthConfigError`
   （`WX_APPID/WX_SECRET not configured`，一次性列全）；
3. 实现要点：code2session 真实 HTTP 调用（5s 超时）、errcode 明确映射
   （40029 code 无效 / 45011 频率限制 / 40163 code 已用 / 40013 appid 错误）、
   session_key 加密留存 `wx_session_key_enc`（明文不落库不出响应）。

**② 微信支付（mock → wxpay）**

1. `PAY_PROVIDER=wxpay`，填入商户凭据：`WXPAY_MCH_ID`（商户号）、
   `WXPAY_SERIAL_NO`（API 证书序列号）、`WXPAY_PRIVATE_KEY_PATH`
   （商户私钥 apiclient_key.pem，**支持 PEM 文件路径或 PEM 内容两种形态**）、
   `WXPAY_API_V3_KEY`（APIv3 密钥，32 字符）、
   `WXPAY_PLATFORM_CERT_PATH`（平台证书/微信支付公钥 PEM 二选一，按
   PEM 头自动识别）、`WXPAY_NOTIFY_URL`（V3 回调通知地址，https 公网
   可达，JSAPI 下单必填）；并确认 `WX_APPID` 已配置（下单报文需要）；
2. 回调域名要求：公网可达，回调落位 `/api/v1/billing` 路由，请在商户
   平台按此配置回调地址；
3. 重启后端生效；实现要点：V3 JSAPI 下单（商户私钥 RSA-SHA256 签名 +
   二次签名调起参数）、回调验签 + resource 解密（AES-256-GCM）、退款
   （确定性退款单号幂等）；验签失败一律拒绝且不更新订单（状态机零改动）。

**③ KMS 信封加密（local → kms）**

1. `CRYPTO_PROVIDER=kms`，填入 `KMS_MASTER_KEY`（本地适配器实现下为
   环境变量主密钥，KEK = SHA-256(本值)；缺该项时显式抛 `CryptoConfigError`）；
2. 存量数据渐进迁移（**非必须**，kms 通道可解密既有 `v{N}:` 本地密文）：
   切换配置后执行轮换脚本，逐行重加密为 `kms1:` 信封格式——
   `cd backend && python scripts/rotate_field_key.py`（幂等，可重复执行）；
3. 回退：`CRYPTO_PROVIDER=local` 后重启即可；`kms1:` 密文无论当前配置
   均可解（跨格式兼容），双向切换均安全；
4. 接云 KMS：实现 `app/core/crypto.py` 的 `KekAdapter`（GenerateDataKey /
   Decrypt 语义）并注入 `KmsEnvelopeProvider` 即可，调用方零改动。

**④ Milvus 向量库（检索主通道，2026-10-12 起替代 pgvector 迁移）**

1. 前置：compose 已编排三件套（etcd/minio/milvus-standalone v3.0.2，
   backend depends_on healthy 自动注入 `MILVUS_URI=http://milvus:19530`）；
   外部已有 Milvus 时直接设 `MILVUS_URI` 指向即可；`.env` 填
   `EMBEDDING_PROVIDER=zhipu` + `ZHIPU_API_KEY`（key 缺失自动降级确定性
   mock，不影响链路验证）；
2. **建集合 + 全量重建（幂等，标准步骤）**：
   - 建集合：`cd backend && python scripts/init_db.py`
     （ensure_rag_index 幂等创建集合 jiaban_kb_entries：2048 维 HNSW
     COSINE + Strong）；
   - 全量重灌：`cd backend && python scripts/reindex_rag.py`
     （drop+重建集合后全部 published child/pet 条目重新向量化写入，输出计数）；
   - 种子重建一条龙：`init_db.py` → `seed_data.py`（内置 reindex）即可；
3. 旧 pgvector 迁移脚本已停用：`migrate_pgvector.sql` /
   `run_pgvector_migration.py`（旧 `kb_entry.embedding_vec` 直连路径）
   保留作回滚保险，**勿再执行**；
4. 验证：`reindex_rag.py` 输出写入计数；发起问答后端日志出现 rag_index
   检索路径即主通道生效；Milvus 不可达时自动回退 hashing 降级链（日志
   warning 留痕），业务无感、无 500。

**⑤ Redis 缓存（进程内 → Redis）**

1. compose 部署：无需配置，backend 已自动注入 `REDIS_URL=redis://redis:6379/0`
   并在 redis 健康检查通过后启动；脱离 compose 本地直连时填
   `REDIS_URL=redis://localhost:6379/0`（两种示例见 `.env.example`）；
2. 重启后端生效；连接失败自动回退进程内缓存并告警（不 500），修复后
   重启 backend 切回；
3. 回退：`REDIS_URL` 留空即回退进程内 TTL 缓存，单实例完全可用。

**回退方式（全部通道）**：将对应 provider 改回默认值（`AUTH_PROVIDER=dev`、
`PAY_PROVIDER=mock`、`CRYPTO_PROVIDER=local`）、`REDIS_URL` 留空，重启后端；
订单状态机与回调幂等逻辑与通道无关，切换/回退不影响既有订单数据。

## 常见问题

**1. AI 问答流式输出（SSE）变成一次性出结果 / 被缓冲？**
检查 `nginx.conf` 中流式路径 location：

```nginx
location ~ ^/api/v1/qa/sessions/.*/stream$ {
    proxy_buffering off; gzip off; proxy_cache off;
    add_header X-Accel-Buffering no; chunked_transfer_encoding on;
    proxy_read_timeout 120s;
}
```

四项关闭缓冲缺一不可（尤其 `proxy_buffering off` 与 `gzip off`，gzip 会攒满一块才发送）。
修改后执行 `docker compose exec frontend nginx -s reload` 或重启 frontend 容器。

**2. 启动日志出现"Redis 未配置，回退进程内缓存"告警？**
compose 部署时 backend 已自动注入 `REDIS_URL` 指向内置 redis 服务，
正常不会出现该告警；若出现，先检查 redis 容器状态（`docker compose ps redis`）。
本地开发（脱离 compose）`REDIS_URL` 留空即回退进程内缓存，属正常行为，
单实例部署完全可用。

**3. 微信登录 / 微信支付报凭据缺失？**
微信 AppID/Secret、支付商户号等均为业务方外部凭据，`.env.example` 中已留位
（标注"待业务方提供"）。凭据未提供前请保持 `AUTH_PROVIDER=dev`、
`PAY_PROVIDER=mock`，走本地模拟实现；填入真实凭据并切换 provider 前不要伪造。

**4. 后端健康检查一直 unhealthy？**
先看日志 `docker compose logs backend`：常见原因是 `.env` 未配置或
`DB_PASSWORD` 与 postgres 初始化时不一致（postgres 卷只认首次初始化时的密码，
改密码后需 `docker compose down -v` 重建，注意会删数据）。

## 与本地启停脚本（scripts/start.ps1）的关系

- `scripts/start.ps1 / stop.ps1 / status.ps1`：**本地开发**用，直接在本机跑
  PostgreSQL + uvicorn + vite dev server，支持热重载，读 backend/.env。
- `deploy/docker-compose.yml`：**部署交付**用，容器化运行，读 deploy/.env。
- 两者独立、可并存；默认均占用 8000/5173 或 80 端口，请勿同时启动同一端口。

## 本地验证容器（生产形态终验，2026-10-12）

本地开发机无 pgvector 扩展（系统 PG 5432）时的生产形态验证环境——镜像与
compose 生产拓扑一致（`pgvector/pgvector:pg16` + `redis:7-alpine`）：

```powershell
# pgvector 验证库（宿主 5433 → 容器 5432，独立数据卷，不触碰本机 5432 主库）
docker run -d --name jiaban-pgvector-verify --restart unless-stopped `
  -e POSTGRES_PASSWORD=<密码> -e POSTGRES_DB=jiaban `
  -p 5433:5432 -v jiaban-pgvector-verify-data:/var/lib/postgresql/data `
  pgvector/pgvector:pg16

# Redis（宿主 6379，AOF 持久化）
docker run -d --name jiaban-redis --restart unless-stopped `
  -p 6379:6379 -v jiaban-redis-data:/data redis:7-alpine redis-server --appendonly yes
```

已完成的终验结论（2026-10-12）：

- **pgvector**：`run_pgvector_migration.py`（`DATABASE_URL` 环境变量覆盖指向
  5433）两遍执行幂等通过；vector 扩展 0.8.7、`kb_entry.embedding_vec`
  vector(512)、ivfflat 索引与 COMMENT 齐全；`PgVectorStore.available()` 探测
  通过，`search` 余弦检索（`<=>`）实测命中（相似度 1.0）——生产库执行迁移
  的 DDL 分支已在同构镜像验证闭环。
- **Redis**：`backend/.env` 填 `REDIS_URL=redis://localhost:6379/0` 后，
  `RedisCacheStore` 生效（送检配额键 `scan:quota:*` 实测写入，TTL 24h）。
  注意：缓存单例经 `get_cache()` 工厂创建（读 `settings.redis_url`），
  REDIS_URL 配置后重启后端生效；连接失败回退进程内（重启后端方可重试）。
- pytest 测试进程强制进程内缓存（tests/conftest.py 显式置空 REDIS_URL），
  与运行中后端（db0）互不串扰；Redis 集成语义由 test_redis_cache.py 显式
  探测覆盖（可达即真实跑）。

## 对外上线前安全检查表（2026-10-12）

> 适用场景：把 compose 拓扑部署到**公网可达的云服务器**并对外提供服务前，
> 逐项核验。每项附操作与验证方法——**打勾后才可放开安全组 80/443**。

### 1. 凭据轮换（全部换强随机，不留开发默认值）

| # | 检查项 | 操作 | 验证方法 |
|---|---|---|---|
| 1.1 | DB 密码 | `deploy/.env` 设强随机 `DB_PASSWORD`（**首次启动前**设定，postgres 卷只认首次初始化密码） | `docker compose exec postgres psql -U postgres -c "select 1"` 用新密码可达；旧密码不可达 |
| 1.2 | JWT_SECRET | `openssl rand -hex 32` 生成（无 openssl 时 PowerShell：`-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })`） | 改密后旧 token 全部失效（401）= 生效 |
| 1.3 | FIELD_ENC_KEY | `openssl rand -base64 32`；**注意**：换钥会使既有密文字段不可解，生产首启即定稿并离线备份 | 抽查 `qa_session.question_text_enc` 可正常解密（问答链路可用即证） |
| 1.4 | SAFETY_SCAN_CALLBACK_SECRET | 同 1.2 强随机 | 回调签名校验拒绝无签名/错签名请求（401/403） |
| 1.5 | KMS_MASTER_KEY | `CRYPTO_PROVIDER=kms` 时为 64 位 hex 强随机；**首启定稿 + 离线备份**（丢失=全库密文不可恢复） | 环境变量注入后加解密链路 e2e 通过 |
| 1.6 | MinIO 凭据 | compose 默认 `minioadmin/minioadmin`，**必须改**：`.env` 覆盖 `MINIO_ACCESS_KEY/SECRET_KEY`（compose 无该变量时先补上再启动） | 旧凭据 `mc alias set` 登录失败 |
| 1.7 | 第三方 API 密钥 | DeepSeek/智谱密钥确认为主通道专用、已设用量限额与告警 | 商户后台可见调用量与限额配置 |

### 2. 暴露面收敛（公网只留 80/443）

| # | 检查项 | 操作 | 验证方法 |
|---|---|---|---|
| 2.1 | compose 端口绑定 | 数据面服务（postgres 5432 / redis 6379 / milvus 19531 / etcd 2379 / minio 9000·9001 / milvus metrics 9091）的 `ports:` 改为 `127.0.0.1:宿主端口:容器端口` 或直接删除映射（容器网络内互通即可） | `docker compose ps` 确认仅 backend/frontend 映射；`netstat -ano | findstr LISTEN`（云上 `ss -tlnp`）核对监听面 |
| 2.2 | 云安全组 | 入方向仅放行 80/443（SSH 建议限源 IP 或走堡垒） | 云控制台核对 + 外网 `Test-NetConnection <IP> -Port 5432` 应 **TcpTestSucceeded: False** |
| 2.3 | 后端直连端口 | backend 8000 不直接对公网，经 nginx/网关反代 443 → 8000 | 外网访问 `:8000` 不通，`https://域名/api/v1/health` 通 |
| 2.4 | Redis 认证 | 生产公网可达性为 0（内网）前提下仍建议 `requirepass`；compose command 追加 `--requirepass <强随机>` 并同步 `REDIS_URL=redis://:<密码>@redis:6379/0` | `redis-cli -h <内网IP> ping` 无密码返回 NOAUTH |

### 3. HTTPS / 域名 / 备案核对

| # | 检查项 | 操作 | 验证方法 |
|---|---|---|---|
| 3.1 | 域名 + ICP 备案 | 域名实名并完成 ICP 备案（小程序 request 合法域名的硬前提，个人主体阶段即需要） | 工信部备案查询可查；`https://域名` 可访问 |
| 3.2 | HTTPS 证书 | 云厂商免费证书或 Let's Encrypt；nginx 强制 301 → https | `curl -I http://域名` 返回 301；证书链完整（`openssl s_client` 无告警） |
| 3.3 | AI 内容合规 | 生成式 AI 备案/算法备案发起；前端 AI 标识与免责声明确认为**服务端注入**（不可裁剪，合规红线） | 抓包确认响应体含 AI 标识字段；备案号回填 PRD §11.11.1 |
| 3.4 | 危机渠道红线 | `crisis_channel` 表号码除 110 外保持留空占位，未核实号码不得上线 | `select channel_code, phone_number from crisis_channel;` 核对 |

### 4. 数据卷备份

| # | 检查项 | 操作 | 验证方法 |
|---|---|---|---|
| 4.1 | 备份三卷 | `pgdata`（主数据）/ `milvusdata`（向量库）/ `redisdata`（AOF）纳入定期备份；pg 用 `backup_db.ps1` 或 `pg_dump`，milvus 停写时打 tar 快照 | 恢复演练：在验证容器用备份卷起一套，问答链路可复现 |
| 4.2 | 备份离线化 | 备份产物推送至对象存储/异地（不与本机同盘） | 抽查远端存在且可下载 |
| 4.3 | 密钥离线托管 | `FIELD_ENC_KEY`/`KMS_MASTER_KEY`/`JWT_SECRET` 纸质或密码管理器离线留存 | 丢失演练：仅凭离线备份可在新机恢复全部数据 |

### 5. 云部署就绪判定结论

| 维度 | 判定 | 依据 |
|---|---|---|
| **工程侧** | ✅ **就绪，可以云部署** | compose 七服务拓扑（postgres/redis/etcd/minio/milvus-standalone/backend/frontend）已在本地验证容器完成生产形态终验；生产切换清单（§生产切换清单）完备；283 项单测 + 63 项真实模式 e2e 全绿。唯一动作：云服务器安装 Docker + Compose v2 → 按 §快速启动 起栈 → **逐项打勾本检查表 §1~§4** |
| **资源要求** | ⚠️ 按需 | Milvus standalone 建议内存 ≥4G（etcd+minio+milvus 三件套合计峰值 ~4G），云服务器 2C4G 为下限、2C8G 稳妥 |
| **微信小程序侧** | ⏳ 取决于外部凭据 | 工程阻塞 0 项；测试号联调当日可做，正式上线需企业化+商户号+备案——见《docs/微信小程序接入判定与准备清单_2026-10-12.md》 |
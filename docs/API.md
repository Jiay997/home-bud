# 小光景后端 API 接口文档

> **生成信息**：由 `backend/scripts/export_api_doc.py` 自动生成（可重复执行，勿手改）
> 生成时间：2026-10-14 20:45:50 ｜ 生成方式：优先抓取运行中服务 `http://127.0.0.1:8000/openapi.json`，失败则本地导入 `app.main.app.openapi()`
> 端点总数：102 ｜ 分组：12 个 tag（11 个正式 tags + history 补充组）

**统一包络**：所有接口返回 `{code, message, data, request_id, trace_id}`；
`code=0` 成功，非 0 为业务错误码（分段：1000 参数 / 1100 鉴权 / 1200 限流额度 / 1300 合规同意 / 1400 问答风险 / 1500 支付 / 1600 后台 / 1900 故障）。

**鉴权方式**：C 端接口携带 `Authorization: Bearer <user_token>`；后台接口携带后台 admin token；
公开接口（登录/文案/健康检查/指标/安全回调）无需会话，安全回调以 HMAC-SHA256 验签。

**通用错误码**（全端点适用，端点小节仅列特有错误码）：

| 错误码 | 含义 | HTTP 状态 |
| --- | --- | --- |
| 1001 | 参数校验失败 | 422 |
| 1002 | 资源不存在（含防枚举的越权场景） | 404 |
| 1003 | 内容已被更新，请刷新（乐观锁，C 端档案） | 409 |
| 1004 | 相同请求正在处理中（幂等冲突） | 409 |
| 1007 | 相册数量已达上限 | 409 |
| 1101 | 会话缺失或已失效 | 401 |
| 1102 | 无权访问该资源 | 403 |
| 1103 | 当前角色无此权限 | 403 |
| 1104 | MFA 校验未通过 | 403 |
| 1201 | 请求过于频繁 | 429 |
| 1202 | 今日免费额度已用尽 | 429 |
| 1301 | 请先同意用户协议与免责声明 | 403 |
| 1302 | 需先完成儿童信息单独同意 | 403 |
| 1303 | 内容安全送检未通过 | 403 |
| 1406 | 该功能维护中（入口开关关闭） | 503 |
| 1601 | 内容已被更新，请刷新后重试（后台乐观锁） | 409 |
| 1602 | 危险操作需要二次确认 | 403 |
| 1603 | 超出您的授权领域范围（专家域绑定） | 403 |
| 1901 | 依赖服务不可用 | 503 |
| 1902 | 服务内部错误 | 500 |

## 目录

- [系统](#系统)（5 个端点）
- [C端-认证同意](#C端-认证同意)（6 个端点）
- [C端-档案](#C端-档案)（14 个端点）
- [C端-问答](#C端-问答)（9 个端点）
- [C端-测评](#C端-测评)（5 个端点）
- [C端-商业化](#C端-商业化)（6 个端点）
- [C端-权利反馈](#C端-权利反馈)（7 个端点）
- [后台-知识库](#后台-知识库)（11 个端点）
- [后台-词库](#后台-词库)（7 个端点）
- [后台-处置](#后台-处置)（14 个端点）
- [后台-配置](#后台-配置)（13 个端点）
- [history](#history)（5 个端点）

# 系统

## GET /api/v1/admin/metrics/alert-history

**Get Alert History**

告警历史：alert_watch 任务留痕最近 50 条（按发生时间倒序）。

- **Tag**：系统
- **鉴权**：需后台角色（get_admin 登录态，无额外权限矩阵）
- **响应 data**：{items:[{id, metric, value, threshold, message, status, started_at}]}（最近 50 条）
- **主要错误码**：1101 未登录（其余见「通用错误码」）

## GET /api/v1/health

**Health**

健康检查端点。

- **Tag**：系统
- **鉴权**：公开
- **响应 data**：{service, db_connected, model_whitelist[], llm_mock}

## GET /api/v1/metrics

**Get Metrics**

运行指标与告警：进程内聚合快照（计数/延迟分位/比率/告警）。

- **Tag**：系统
- **鉴权**：公开（进程内指标快照，运维探查）
- **响应 data**：{counters, latency{p50,p95,samples}, rates, alerts[]}

## POST /api/v1/safety-scan/callback

**内容安全平台回调（HMAC 验签 + 幂等裁决）**

平台异步回调：验签 → 时间窗校验 → 裁决记录并回写业务状态。

- **Tag**：系统
- **鉴权**：公开（机器对机器：HMAC-SHA256 验签 + 时间窗防重放，无会话）
- **请求体**（application/json）：
  - `record_id`（integer，必填）：送检记录主键
  - `verdict`（string，必填）：平台裁决
  - `timestamp`（integer，必填）：Unix 秒级时间戳
  - `signature`（string，必填）：HMAC-SHA256 签名
  - `note`（，可选）：平台备注
- **响应 data**：{record_id, audit_result, idempotent, object_type, object_id}
- **主要错误码**：1901 密钥未配置；1001 时间戳超窗；1102 签名不匹配；1002 记录不存在（其余见「通用错误码」）

## GET /api/v1/texts

**批量下发文案**

按文案 ID 批量查询当前生效版本内容（未登录可访问）

- **Tag**：系统
- **鉴权**：公开（协议文案需在登录/同意前展示）
- **查询参数**：
  - `ids`（string，可选）：逗号分隔的文案 ID 列表，如 DISCLAIMER_V1,AI_GEN_LABEL_V1，默认 ``
- **响应 data**：{texts: {text_id: content}}
- **主要错误码**：1001 ids 为空（其余见「通用错误码」）

# C端-认证同意

## POST /api/v1/auth/dev-login

**开发模式设备码登录**

开发模式设备码登录：device_id 哈希为模拟 openid，按密文查找或创建用户。

- **Tag**：auth、C端-认证同意
- **鉴权**：公开
- **请求体**（application/json）：
  - `device_id`（string，必填）：客户端设备唯一标识
- **响应 data**：令牌对 + {user_uid, member_status}（幂等登录）
- **主要错误码**：1901 落库异常兜底（其余见「通用错误码」）

## POST /api/v1/auth/refresh

**刷新令牌**

刷新令牌：校验 user_refresh 类型 JWT 并签发新的令牌对。

- **Tag**：auth、C端-认证同意
- **鉴权**：公开（校验 user_refresh 类型 JWT）
- **请求体**（application/json）：
  - `refresh_token`（string，必填）：user_refresh 类型 JWT
- **响应 data**：新令牌对 + {user_uid, member_status}
- **主要错误码**：1101 刷新令牌无效/过期/类型不符（其余见「通用错误码」）

## POST /api/v1/auth/wx-login

**微信 code2session 登录（骨架，待凭据）**

微信 code 登录：code2session → openid 加密查/建用户 → 签发令牌对。

- **Tag**：auth、C端-认证同意
- **鉴权**：公开（通道由 settings.auth_provider 控制）
- **请求体**（application/json）：
  - `code`（string，必填）：wx.login 临时登录凭证
- **响应 data**：令牌对 + {user_uid, member_status}
- **主要错误码**：1101 通道未启用；1901 微信服务不可用（其余见「通用错误码」）

## POST /api/v1/consent/agree

**同意协议**

幂等同意；儿童信息类型强制监护人声明留痕

- **Tag**：C端-认证同意
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `consent_type`（string，必填）：同意类型：base / child_personal_info
  - `consent_version`（，可选）：协议版本，默认 V1
  - `guardian_name`（，可选）：监护人声明姓名（儿童信息类型）
- **响应 data**：{consent_type, consent_version, agreed_at, idempotent}
- **主要错误码**：1001 consent_type 非法（其余见「通用错误码」）

## GET /api/v1/consent/status

**查询同意状态**

各 consent_type 最新同意/撤回状态

- **Tag**：C端-认证同意
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{base:{agreed,version,agreed_at,withdraw_at}, child_personal_info:{...}}
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/consent/withdraw

**撤回同意**

写 withdraw_at；撤回儿童信息同意联动禁用全部儿童档案

- **Tag**：C端-认证同意
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `consent_type`（string，必填）：撤回类型：base / child_personal_info
- **响应 data**：{consent_type, withdrawn, withdrawn_at?, impact?}
- **主要错误码**：1001 consent_type 非法（其余见「通用错误码」）

# C端-档案

## GET /api/v1/profiles/children

**儿童档案列表**

解密展示，不含已删除；disabled 档案昵称脱敏

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{children:[档案视图]}（解密展示，disabled 昵称脱敏）
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/profiles/children

**新建儿童档案**

前置校验儿童信息同意与数量上限，加密落库并计算派生列

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `nickname`（string，必填）：儿童昵称
  - `birth_date`（string，必填）：出生日期 YYYY-MM-DD
  - `gender`（，可选）：性别
  - `height_cm`（，可选）：身高 cm
  - `weight_kg`（，可选）：体重 kg
  - `premature_flag`（boolean，可选）：是否早产
  - `allergy`（，可选）：过敏项列表
  - `solid_food_month`（，可选）：辅食添加月龄
- **响应 data**：新建档案视图（含 age_months/age_band/version）
- **主要错误码**：1302 未完成儿童信息同意；1006 档案超上限(409)（其余见「通用错误码」）

## DELETE /api/v1/profiles/children/{profile_uid}

**删除儿童档案**

昵称二次确认后软删；purge_all 返回删除回执

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`profile_uid`（string，必填）
- **请求体**（application/json）：
  - `mode`（string，可选）：删除模式
  - `confirm_nickname`（string，必填）：确认昵称
- **响应 data**：{deleted, mode, deletion_receipt?(purge_all)}
- **主要错误码**：1002 不存在/越权；1001 昵称校验不一致（其余见「通用错误码」）

## PUT /api/v1/profiles/children/{profile_uid}

**更新儿童档案**

乐观锁更新，成功后 version+1 并重算月龄档位

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`profile_uid`（string，必填）
- **请求体**（application/json）：
  - `version`（integer，必填）：乐观锁版本号
  - `nickname`（，可选）
  - `birth_date`（，可选）
  - `gender`（，可选）
  - `height_cm`（，可选）
  - `weight_kg`（，可选）
  - `premature_flag`（，可选）
  - `allergy`（，可选）
  - `solid_food_month`（，可选）
- **响应 data**：更新后档案视图（version+1，重算月龄档位）
- **主要错误码**：1002 不存在/越权；1003 乐观锁冲突(409)（其余见「通用错误码」）

## POST /api/v1/profiles/current

**设置当前问答对象**

多档案场景下 upsert 本次问答对象（按对外 uid 解析，不暴露内部主键）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `profile_type`（string，必填）：档案类型
  - `profile_uid`（string，必填）：档案对外标识
- **响应 data**：{profile_type, profile_uid, updated_at}
- **主要错误码**：1002 档案不存在/越权/已删除（其余见「通用错误码」）

## GET /api/v1/profiles/pets

**宠物档案列表**

不含已删除的宠物档案

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{pets:[宠物视图]}
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/profiles/pets

**新建宠物档案**

数量上限同儿童档案（免费 3 / 会员 10）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `pet_type`（string，必填）：宠物类型
  - `breed`（，可选）
  - `age_band`（string，可选）
  - `neutered_flag`（，可选）
  - `weight_kg`（，可选）
  - `main_food`（，可选）
- **响应 data**：新建宠物视图
- **主要错误码**：1006 档案超上限(409)（其余见「通用错误码」）

## DELETE /api/v1/profiles/pets/{pet_uid}

**删除宠物档案**

软删，保留问答历史引用

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`pet_uid`（string，必填）
- **响应 data**：{deleted: true}
- **主要错误码**：1002 不存在/越权（其余见「通用错误码」）

## PUT /api/v1/profiles/pets/{pet_uid}

**更新宠物档案**

乐观锁更新，版本不一致返回 1003

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`pet_uid`（string，必填）
- **请求体**（application/json）：
  - `pet_type`（string，必填）：宠物类型
  - `breed`（，可选）
  - `age_band`（string，可选）
  - `neutered_flag`（，可选）
  - `weight_kg`（，可选）
  - `main_food`（，可选）
  - `version`（integer，必填）：乐观锁版本号
- **响应 data**：更新后宠物视图（version+1）
- **主要错误码**：1002 不存在/越权；1003 乐观锁冲突(409)（其余见「通用错误码」）

## DELETE /api/v1/profiles/{kind}/{uid}/avatar

**移除档案头像**

置空头像并删除文件；未设置时同样成功（幂等）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`kind`（string，必填）；`uid`（string，必填）
- **响应 data**：{deleted: true}（幂等：未设置时同样成功）
- **主要错误码**：1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)（其余见「通用错误码」）

## POST /api/v1/profiles/{kind}/{uid}/avatar

**上传档案头像**

multipart 单文件（file 字段），服务端规范化 JPEG 存储并返回 avatar_url；覆盖旧的自动删除。用 POST 而非 PUT：微信 uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（2026-10-14 实测）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`kind`（string，必填）；`uid`（string，必填）
- **响应 data**：{avatar_url, width, height, size}（multipart：file 字段单文件；POST 口径见描述）
- **主要错误码**：1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)；1001 图片格式不支持/超 8MB(422)（其余见「通用错误码」）

## GET /api/v1/profiles/{kind}/{uid}/photos

**档案相册列表**

按加入时间升序返回照片 URL 与上限；孩子档案需儿童信息同意有效

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`kind`（string，必填）；`uid`（string，必填）
- **响应 data**：{photos:[{photo_uid, url, size, created_at}], limit}（按加入时间升序）
- **主要错误码**：1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)（其余见「通用错误码」）

## POST /api/v1/profiles/{kind}/{uid}/photos

**添加相册照片**

multipart 单文件（file 字段）；数量上限按配置（默认 30 张），超限返回 1007

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`kind`（string，必填）；`uid`（string，必填）
- **响应 data**：{photo, count, limit}（multipart：file 字段单张上传）
- **主要错误码**：1002 档案不存在/越权；1302 儿童同意缺失或已撤回(403)；1001 图片格式不支持/超 8MB(422)；1007 相册数量已达上限(409)（其余见「通用错误码」）

## DELETE /api/v1/profiles/{kind}/{uid}/photos/{photo_uid}

**删除相册照片**

软删照片行并删除文件；不存在或越权统一 1002（防枚举）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`kind`（string，必填）；`uid`（string，必填）；`photo_uid`（string，必填）
- **响应 data**：{deleted: true}
- **主要错误码**：1002 档案或照片不存在/越权；1302 儿童同意缺失或已撤回(403)（其余见「通用错误码」）

# C端-问答

## POST /api/v1/qa/sessions

**创建问答会话**

校验开关/幂等/申诉放行/活跃限制/额度后落库 pending，返回 session_uid

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `entry`（string，必填）：入口 child/pet/family
  - `question`（string，必填）：问题原文
  - `profile_uid`（，可选）：档案 UID
  - `client_request_id`（string，必填）：幂等键
- **响应 data**：{session_uid, status: pending}；幂等重放附 idempotent_replay/result_ref
- **主要错误码**：1406 入口维护中(503)；1004 同键处理中(409)；1203 已有活跃流(409, retry_after=30)；1202 免费额度用尽(429)；1002 档案不存在；1001 参数/指纹不符（其余见「通用错误码」）

## GET /api/v1/qa/sessions/{session_uid}

**轮询兜底查询会话**

会话元数据 + 分节全量（会员门控裁剪）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **响应 data**：会话元数据 + sections（会员门控裁剪）+ render_order
- **主要错误码**：1002 会话不存在/越权（其余见「通用错误码」）

## POST /api/v1/qa/sessions/{session_uid}/cancel

**取消进行中的会话**

释放活跃会话键；未完成会话置 orphaned

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **请求体**（application/json）：
  - `cancel_token`（，可选）
- **响应 data**：{session_uid, status}
- **主要错误码**：1002 会话不存在/越权；1102 取消凭证不匹配（其余见「通用错误码」）

## POST /api/v1/qa/sessions/{session_uid}/regenerate

**重生成指定分节**

会员专属：重跑整图后替换目标分节（section_version+1）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **请求体**（application/json）：
  - `section`（，可选）：目标分节 child/pet/safety
  - `client_request_id`（string，必填）：幂等键
- **响应 data**：{session_uid, section, section_version, status}
- **主要错误码**：1002 不存在/越权；1102 非会员(403)；1401 风险拦截(HTTP 200)；1001 非法分节（其余见「通用错误码」）

## GET /api/v1/qa/sessions/{session_uid}/stream

**断线续发**

已完成会话从落库分节重发 section_done 与 completed 帧

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **查询参数**：
  - `from_sequence`（integer，可选），默认 `0`
- **响应 data**：SSE 续发：section_done*→completed（blocked 单帧）
- **主要错误码**：1002 不存在/越权；1004 会话未完成(409)（其余见「通用错误码」）

## POST /api/v1/qa/sessions/{session_uid}/stream

**SSE 流式问答**

风险扫描→缓存→LangGraph 逐节下发，帧序 started→section_*→completed

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **响应 data**：SSE 流：started→section_delta/section_done→completed（blocked 单帧）
- **主要错误码**：1002 会话不存在/越权（其余见「通用错误码」）

## POST /api/v1/risk/appeals

**提交误报申诉**

备注再过一级流水线；同会话上限 2 次，SLA 24h

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `session_uid`（string，必填）：会话 UID
  - `appeal_note`（string，必填）：申诉说明
- **响应 data**：{appeal_no, sla_due_at, status}（命中硬类别 status=abandoned）
- **主要错误码**：1002 会话/事件不存在或无权限；1001 申诉次数已达上限(400)（其余见「通用错误码」）

## GET /api/v1/risk/appeals/{appeal_no}

**查询申诉进度**

限本人；approved 返回重提放行窗口

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`appeal_no`（string，必填）
- **响应 data**：{appeal_no, status, sla_due_at, review_result, resubmit_allowed?, allow_expire_at?}
- **主要错误码**：1002 申诉单不存在/无权限（其余见「通用错误码」）

## GET /api/v1/risk/channels

**危机干预渠道列表**

按风险类别过滤的渠道卡（服务端下发）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `category`（，可选）：风险类别过滤
- **响应 data**：{channels:[渠道卡]}
- **主要错误码**：1001 类别参数非法（其余见「通用错误码」）

# C端-测评

## GET /api/v1/assessment/questions

**下发测评题目**

16 题列表，题干按 age_band 选择；入口开关校验

- **Tag**：C端-测评
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `age_band`（string，可选）：0-6m/6-12m 用婴幼儿题干，其余用 1-6 岁题干，默认 `1-3y`
- **响应 data**：{question_version, age_band, demo_note, questions[]}
- **主要错误码**：1406 入口维护中(503)；1002 题库未初始化（其余见「通用错误码」）

## POST /api/v1/assessment/start

**开始/续填测评**

有未过期断点直接续填（含已答明细）

- **Tag**：C端-测评
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `profile_id`（，可选）：关联档案：整型主键（向后兼容）或档案 UID 字符串（可选）
  - `profile_uid`（，可选）：档案对外 UID（可选，uid 优先）
- **响应 data**：测评断点视图（resumed=True 表示续填）
- **主要错误码**：1101（其余见「通用错误码」）

## PUT /api/v1/assessment/{assessment_uid}/answer

**单题作答**

upsert 即存即返；raw_score=null 表示跳题

- **Tag**：C端-测评
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`assessment_uid`（string，必填）
- **请求体**（application/json）：
  - `q_no`（integer，必填）：题号 1-16
  - `raw_score`（，可选）：李克特分值 1-5；null 表示跳题
- **响应 data**：{answered_count, skipped_count, draft_expire_at}
- **主要错误码**：1002 不存在/越权；1001 已提交(409)；1002 断点过期(410)（其余见「通用错误码」）

## GET /api/v1/assessment/{assessment_uid}/report

**查询测评报告**

统一报告装配 + 会员门控裁剪 content

- **Tag**：C端-测评
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`assessment_uid`（string，必填）
- **响应 data**：报告视图（blocks 按会员状态裁剪 content，readonly 标记）
- **主要错误码**：1002 不存在/越权/报告未生成（其余见「通用错误码」）

## POST /api/v1/assessment/{assessment_uid}/submit

**提交测评**

幂等提交：计分→落库→生成 13 区块报告；不计问答额度

- **Tag**：C端-测评
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`assessment_uid`（string，必填）
- **请求体**（application/json）：
  - `client_request_id`（string，必填）：客户端幂等 ID
- **响应 data**：{assessment_uid, report_uid, type_code, idempotent_replay}
- **主要错误码**：1002 不存在/越权；1004 并发同键(409)；1001 缺答过多(422)/同键不同指纹(409)（其余见「通用错误码」）

# C端-商业化

## GET /api/v1/billing/orders

**订单列表**

当前用户订单列表（创建时间倒序，含状态与商品编码）。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{orders:[订单视图]}（创建时间倒序）
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/billing/orders

**创建订单（幂等）**

幂等下单：退款政策确认 + 价格快照 + 幂等键落库。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `product_code`（string，必填）：商品编码
  - `platform`（string，必填）：下单平台
  - `contract_confirm`（boolean，必填）：是否已确认退款政策
  - `client_request_id`（string，必填）：客户端幂等 ID
- **响应 data**：订单视图 + idempotent_replay
- **主要错误码**：1004 同键处理中(409)；1001 同键不同指纹(409)/未确认退款政策；1002 商品不存在或未上架（其余见「通用错误码」）

## POST /api/v1/billing/orders/{order_no}/mock-pay

**模拟支付回调（验签+幂等+权益发放）**

模拟支付回调：验签 → 幂等 → 状态机 pending→paid → 发放会员订阅。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`order_no`（string，必填）
- **请求体**（application/json）：
  - `transaction_id`（string，必填）：渠道交易号
  - `sign`（string，必填）：验签摘要
- **响应 data**：{order_no, status, transaction_id, member_expire_at, already_processed}
- **主要错误码**：1504 验签失败(400)；1002 订单不存在/越权；1501 状态不允许(409)（其余见「通用错误码」）

## GET /api/v1/billing/product

**商品查询（iOS 不返回可购）**

商品列表下发（仅 status='on'）；iOS 平台不展示购买入口。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `platform`（string，可选）：下单平台 android / ios，默认 `android`
- **响应 data**：iOS：{purchasable:false, reason_code}；其他：{purchasable:true, products[]}
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/billing/quota

**免费额度查询**

查询今日免费额度用量（biz_date 按 Asia/Shanghai 时区的今天）。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{used, limit, remaining, is_member, biz_date, unlimited?}
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/billing/subscription

**会员订阅状态**

当前有效订阅 + 会员状态；member_expire_at 已过期则惰性置 expired。

- **Tag**：billing、C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{member_status, member_expire_at, subscription?}
- **主要错误码**：1101（其余见「通用错误码」）

# C端-权利反馈

## POST /api/v1/feedback

**提交反馈（内容安全送检闭环）**

提交反馈：敏感词前置检查 → 配额检查 → 送检闭环 → 反馈落库（正文加密）。

- **Tag**：feedback、C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `content`（string，必填）：反馈正文
  - `linked_session_id`（，可选）
  - `linked_report_id`（，可选）
  - `image_count`（integer，可选）：附图数量 ≤3
- **响应 data**：{feedback_no, receipt_hours, audit_result}
- **主要错误码**：1303 敏感词/送检未通过(403)/送检配额超限(429)（其余见「通用错误码」）

## GET /api/v1/me

**我的信息**

当前用户信息：user_uid、会员状态与到期时间、档案计数。

- **Tag**：feedback、C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{user_uid, member_status, member_expire_at, child_profile_count, pet_profile_count, register_at}
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/me/consents

**我的同意状态**

当前用户同意状态简版（各类型是否处于已同意状态）。

- **Tag**：feedback、C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{consents: {base: bool, child_personal_info: bool}}
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/reports

**一键举报（四分类/涉未成年加急）**

提交内容举报：涉未成年人 24h SLA 加急，其余 72h。

- **Tag**：feedback、C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `object_type`（string，必填）：对象类型
  - `object_id`（string，必填）：对象标识
  - `category`（string，必填）：举报分类
  - `description`（，可选）：举报说明
- **响应 data**：{report_no, sla_due_at}（涉未成年 24h，其余 72h）
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/rights/requests

**权利请求列表**

当前用户请求，创建时间倒序

- **Tag**：C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{requests:[请求视图]}（创建时间倒序）
- **主要错误码**：1101（其余见「通用错误码」）

## POST /api/v1/rights/requests

**提交权利请求**

六类请求，15 天 SLA；export 类标记下载交付

- **Tag**：C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `request_type`（string，必填）：请求类型
  - `scope`（，可选）：请求范围
- **响应 data**：{request_no, request_type, status, sla_due_at}
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/rights/requests/{request_no}/download

**下载导出文件**

仅 export 请求且未过期未下载过（一次有效）

- **Tag**：C端-权利反馈
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`request_no`（string，必填）
- **响应 data**：FileResponse 或纯文本下载地址（链接一次有效）
- **主要错误码**：1002 不存在/越权/非导出类/未生成/已下载/已过期（其余见「通用错误码」）

# 后台-知识库

## GET /api/v1/admin/kb/entries

**知识条目列表**

分页查询（专家域隔离），含待审核角标计数

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `kb_kind`（，可选）
  - `domain`（，可选）
  - `status`（，可选）
  - `keyword`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size, pending_badge}（专家域隔离）
- **主要错误码**：1103 缺少 kb:view（其余见「通用错误码」）

## POST /api/v1/admin/kb/entries

**创建知识条目**

初始 draft 态；专家仅可创建绑定领域条目

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `kb_kind`（string，必填）：child / pet / assessment_pool / risk_lexicon / sensitive_lexicon
  - `domain`（string，必填）：领域：child / pet
  - `topic_key`（string，必填）：主题键
  - `topic_category`（string，必填）：主题类目
  - `title`（string，必填）：标题
  - `content`（string，必填）：正文
  - `preconditions`（string，必填）：适用前提（一票否决项，必填）
  - `source_type`（string，必填）：来源类型
  - `source_ref`（string，必填）：来源引用（必填，可溯源）
  - `age_band`（，可选）：年龄段
  - `pet_stage`（，可选）：宠物生命周期
  - `species`（，可选）：物种（cat/dog）
  - `stance`（，可选）：立场：support / neutral / against
  - `is_high_risk`（boolean，可选）：高危类目（100% 审核 + 合格线 90 分）
- **响应 data**：{kb_id, status: draft}
- **主要错误码**：1103 缺少 kb:edit；1603 专家跨领域（其余见「通用错误码」）

## PUT /api/v1/admin/kb/entries/{kb_id}

**更新知识条目**

乐观锁；命中敏感词返回 warnings；改后回草稿

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **请求体**（application/json）：
  - `version`（integer，必填）：客户端持有的版本号（乐观锁比对）
  - `title`（，可选）：标题
  - `content`（，可选）：正文
  - `preconditions`（，可选）：适用前提
  - `topic_category`（，可选）：主题类目
  - `source_type`（，可选）：来源类型
  - `source_ref`（，可选）：来源引用
  - `age_band`（，可选）：年龄段
  - `pet_stage`（，可选）：宠物生命周期
  - `species`（，可选）：物种
  - `stance`（，可选）：立场
  - `is_high_risk`（，可选）：高危类目标记
- **响应 data**：{kb_id, version, status, warnings[]}
- **主要错误码**：1002 不存在；1103 kb:edit；1601 乐观锁(409)；1603 跨领域（其余见「通用错误码」）

## POST /api/v1/admin/kb/entries/{kb_id}/review

**审核知识条目**

pass 发布新版本（需二次确认）；reject 驳回留回滚目标

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **请求体**（application/json）：
  - `verdict`（string，必填）：审核结论：pass / reject
  - `score`（，可选）：审核评分
  - `reject_code`（，可选）：驳回理由码（reject 必填）
  - `confirm_token`（，可选）：二次确认凭证（pass 必填）
- **响应 data**：{kb_id, status, version}
- **主要错误码**：1002 不存在/无待审工单；1001 reject 缺理由码(422)；1103 kb:review；1602 缺二次确认；1603 跨领域（其余见「通用错误码」）

## POST /api/v1/admin/kb/entries/{kb_id}/rollback

**回滚条目版本**

记录式回滚（version+1 回草稿），触发专家驳回追溯

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **请求体**（application/json）：
  - `target_version`（integer，必填）：回滚目标版本号（审计留档）
  - `version`（integer，必填）：客户端持有的当前版本号（乐观锁）
  - `reason`（string，必填）：回滚原因（审计必填）
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{kb_id, version, status: draft}
- **主要错误码**：1002 不存在；1103 kb:rollback；1601 乐观锁(409)；1602 缺二次确认；1603 跨领域（其余见「通用错误码」）

## POST /api/v1/admin/kb/entries/{kb_id}/submit

**提交条目送审**

draft → pending_review，创建审核工单

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **响应 data**：{kb_id, status, review_no}
- **主要错误码**：1002 不存在；1001 非 draft 状态(409)；1103 kb:edit；1603 跨领域（其余见「通用错误码」）

## POST /api/v1/admin/kb/entries/{kb_id}/unpublish

**下架知识条目**

触发内容追溯任务（violation），统计影响会话数

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **请求体**（application/json）：
  - `reason`（string，必填）：下架原因（审计必填）
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{kb_id, status, affected_sessions}
- **主要错误码**：1002 不存在；1103 kb:publish；1602 缺二次确认；1603 跨领域（其余见「通用错误码」）

## GET /api/v1/admin/kb/entries/{kb_id}/versions

**条目版本历史**

从审计日志聚合版本历史（不建历史版本表）

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`kb_id`（string，必填）
- **响应 data**：{kb_id, items[]}（审计聚合版本历史）
- **主要错误码**：1002 不存在；1103 kb:view（其余见「通用错误码」）

## GET /api/v1/admin/kb/reviews

**审核工单列表**

分页查询，status=pending 映射 verdict 为空

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `status`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}
- **主要错误码**：1103 缺少 kb:view（其余见「通用错误码」）

## GET /api/v1/admin/trace-tasks

**追溯任务列表**

内容追溯任务分页查询（pending/done）

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `status`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}（追溯任务列表）
- **主要错误码**：1103 缺少 kb:view（其余见「通用错误码」）

## POST /api/v1/admin/trace-tasks/{task_id}/dispose

**追溯任务分级处置**

A/B/C 分级处置，处置数=影响会话数

- **Tag**：后台-知识库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`task_id`（integer，必填）
- **请求体**（application/json）：
  - `disposal_level`（string，必填）：处置等级：A / B / C
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{task_id, disposal_level, status}
- **主要错误码**：1002 任务不存在；1001 处置等级非法(422)；1103 kb:review；1602 缺二次确认（其余见「通用错误码」）

# 后台-词库

## GET /api/v1/admin/lexicon/config

**风险规则配置列表**

全部 RiskRuleConfig（two_level_threshold 等）

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{items[]}
- **主要错误码**：1103 缺少 lex:view（其余见「通用错误码」）

## PUT /api/v1/admin/lexicon/config/{config_key}

**更新风险规则配置**

upsert 配置并删词库快照缓存（1 分钟内生效）

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`config_key`（string，必填）
- **请求体**（application/json）：
  - `config_value`（object，必填）：配置值（JSON 全量）
  - `reason`（，可选）：变更原因（审计）
- **响应 data**：{config_key, config_value}（upsert + 版本留痕）
- **主要错误码**：1103 缺少 lex:edit（其余见「通用错误码」）

## GET /api/v1/admin/lexicon/terms

**词条列表**

分页查询（term 解密展示，含策略/分数带/生效态）

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `type`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}（term 解密展示）
- **主要错误码**：1103 缺少 lex:view（其余见「通用错误码」）

## POST /api/v1/admin/lexicon/terms

**新增词条**

term_hash 去重，明文加密落库，删词库缓存快照

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `term`（string，必填）：词条明文（服务端加密落库）
  - `lexicon_type`（string，必填）：词库类型：risk / sensitive
  - `strategy`（string，必填）：处置策略：block / rewrite / degrade
  - `threshold_band`（，可选）：分数带
  - `category_code`（，可选）：类目编码
  - `effective`（boolean，可选）：是否生效
- **响应 data**：{id, term_hash, lexicon_type, strategy}
- **主要错误码**：1001 词条已存在(409)；1103 lex:edit（其余见「通用错误码」）

## DELETE /api/v1/admin/lexicon/terms/{term_id}

**删除词条**

危险操作需二次确认（缺凭证 1602 无副作用）

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`term_id`（integer，必填）
- **请求体**（application/json）：
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{id, deleted: true}
- **主要错误码**：1002 不存在；1103 lex:edit；1602 缺二次确认（其余见「通用错误码」）

## PUT /api/v1/admin/lexicon/terms/{term_id}

**更新词条**

部分更新；term 变更时重算密文与哈希

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`term_id`（integer，必填）
- **请求体**（application/json）：
  - `term`（，可选）：词条明文（变更时重算哈希）
  - `strategy`（，可选）：处置策略
  - `threshold_band`（，可选）：分数带
  - `category_code`（，可选）：类目编码
  - `effective`（，可选）：是否生效
- **响应 data**：词条视图（term 重算密文与哈希）
- **主要错误码**：1002 不存在；1103 lex:edit（其余见「通用错误码」）

## POST /api/v1/admin/lexicon/test

**规则匹配测试**

一级引擎只读测试：词库包含匹配 + 正则规则

- **Tag**：后台-词库
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `text`（string，必填）：待检测文本
- **响应 data**：{hit, matched_terms[], matched_patterns[]}
- **主要错误码**：1103 缺少 lex:view（其余见「通用错误码」）

# 后台-处置

## GET /api/v1/admin/agent-logs

**Agent 调用日志列表（脱敏）**

分页查询 Agent 调用日志（脱敏列表：不还原输入，仅返回分节 title）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（log:view）
- **查询参数**：
  - `session_id`（，可选）
  - `agent_id`（，可选）
  - `status`（，可选）
  - `date`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}（脱敏）
- **主要错误码**：1103 缺少 log:view（其余见「通用错误码」）

## GET /api/v1/admin/agent-logs/export

**导出 Agent 日志 CSV（仅超管+二次确认）**

导出 Agent 调用日志 CSV（仅 super_admin，需二次确认）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（log:view + 仅超管 + 二次确认）
- **查询参数**：
  - `confirm_token`（，可选）
- **响应 data**：CSV 文件流（StreamingResponse）
- **主要错误码**：1103 缺少 log:view/非超管；1602 缺二次确认（其余见「通用错误码」）

## GET /api/v1/admin/agent-logs/{log_id}

**Agent 调用日志详情**

查询 Agent 调用日志详情（详情抽屉：完整输出/证据引用/耗时）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（log:view）
- **路径参数**：`log_id`（integer，必填）
- **响应 data**：日志详情（脱敏）
- **主要错误码**：1002 不存在；1103 log:view（其余见「通用错误码」）

## GET /api/v1/admin/feedback

**用户反馈列表（正文按权限解密）**

分页查询用户反馈（正文密文，仅 super_admin/support 解密展示）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（fb:view）
- **查询参数**：
  - `status`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}（正文按权限解密）
- **主要错误码**：1103 缺少 fb:view（其余见「通用错误码」）

## PUT /api/v1/admin/feedback/{feedback_id}

**处置用户反馈（回复并写审计）**

处置用户反馈：填写回复内容后置 replied 并写审计。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（fb:handle）
- **路径参数**：`feedback_id`（integer，必填）
- **请求体**（application/json）：
  - `reply_content`（string，必填）：回复内容（必填）
  - `reply_template_id`（，可选）：命中的回复模板 ID
- **响应 data**：{feedback_id, status, reply}
- **主要错误码**：1002 不存在；1001 已回复(409)；1103 fb:handle（其余见「通用错误码」）

## GET /api/v1/admin/reports

**举报列表（涉未成年优先）**

分页查询举报列表：涉未成年人优先，其次按 SLA 截止时间升序。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（fb:view）
- **查询参数**：
  - `handled`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}（涉未成年优先）
- **主要错误码**：1103 缺少 fb:view（其余见「通用错误码」）

## PUT /api/v1/admin/reports/{report_no}

**举报处置（四动作，上报须附证据）**

处置举报：reject/unpublish/escalate/no_action 四类动作。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（fb:handle（escalate 须附证据））
- **路径参数**：`report_no`（string，必填）
- **请求体**（application/json）：
  - `action`（string，必填）：处置动作：reject / unpublish / escalate / no_action
  - `basis`（string，必填）：处置依据（必填）
  - `evidence`（，可选）：上报证据（escalate 必填）
- **响应 data**：{report_no, status}
- **主要错误码**：1002 不存在；1001 action 非法(422)；1602 escalate 缺证据/确认；1103 fb:handle（其余见「通用错误码」）

## GET /api/v1/admin/rights

**个人信息权利请求列表**

分页查询个人信息权利请求列表。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（rights:view）
- **查询参数**：
  - `status`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}
- **主要错误码**：1103 缺少 rights:view（其余见「通用错误码」）

## GET /api/v1/admin/rights/{request_no}/export-file

**下载权利请求导出文件（24h 有效）**

下载权利请求数据导出文件（24h 内有效，标记已下载）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（rights:view）
- **路径参数**：`request_no`（string，必填）
- **响应 data**：FileResponse（24h 有效）
- **主要错误码**：1002 不存在/文件未生成；1004 链接过期(410)；1103 rights:view（其余见「通用错误码」）

## POST /api/v1/admin/rights/{request_no}/process

**处理权利请求（导出/办结/拒绝）**

处理权利请求：生成数据导出文件 / 标记办结 / 拒绝。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（rights:handle）
- **路径参数**：`request_no`（string，必填）
- **请求体**（application/json）：
  - `action`（string，必填）：处理动作：generate_export / mark_done / reject
  - `reject_reason_code`（，可选）：拒绝理由码（reject 必填）
  - `format`（，可选）：导出格式：json / csv（默认 json）
- **响应 data**：{request_no, status, export_file_url?}
- **主要错误码**：1002 不存在；1001 已处置(409)/action 非法(422)/拒绝缺理由码(422)；1103 rights:handle（其余见「通用错误码」）

## GET /api/v1/admin/risk-events

**高风险事件列表**

分页查询高风险事件列表（user_id_hash 展示，含处置结果与 SLA）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（risk:view）
- **查询参数**：
  - `level`（，可选）
  - `disposal_result`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}
- **主要错误码**：1103 缺少 risk:view（其余见「通用错误码」）

## GET /api/v1/admin/risk-events/{event_no}

**高风险事件详情**

查询高风险事件详情。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（risk:view）
- **路径参数**：`event_no`（string，必填）
- **响应 data**：事件详情
- **主要错误码**：1002 不存在；1103 risk:view（其余见「通用错误码」）

## POST /api/v1/admin/risk-events/{event_no}/report-authority

**上报高风险事件至监管主体（先复核后上报）**

上报高风险事件至监管主体（复核结论未录入前禁止上报）。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（risk:review（须先复核））
- **路径参数**：`event_no`（string，必填）
- **请求体**（application/json）：
  - `reported_target`（string，必填）：上报对象（如属地网信部门）
- **响应 data**：上报结果
- **主要错误码**：1002 不存在；1103 未复核先上报/缺 risk:review（其余见「通用错误码」）

## POST /api/v1/admin/risk-events/{event_no}/review

**复核高风险事件（误报联动放行）**

复核高风险事件：upheld / misreport / need_more。

- **Tag**：admin、后台-处置
- **鉴权**：需后台角色（risk:review）
- **路径参数**：`event_no`（string，必填）
- **请求体**（application/json）：
  - `conclusion`（string，必填）：复核结论：upheld / misreport / need_more
  - `reason_code`（string，必填）：结论理由码（必填）
- **响应 data**：{event_no, conclusion, resubmit_allowed?}
- **主要错误码**：1002 不存在；1001 conclusion 非法(422)；1103 risk:review（其余见「通用错误码」）

# 后台-配置

## GET /api/v1/admin/audit-logs

**审计日志分页查询（快照仅返回键名，仅超管）**

分页查询后台审计日志（脱敏：不返回快照全文，仅返回键名）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（仅超管 super_admin）
- **查询参数**：
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
  - `action`（，可选）
  - `object_type`（，可选）
  - `operator_id`（，可选）
- **响应 data**：{items, total, page, page_size}（快照仅返回键名）
- **主要错误码**：1103 非超管（其余见「通用错误码」）

## GET /api/v1/admin/configs

**配置键最新版本列表（仅超管）**

查询全部配置键的最新版本列表。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（仅超管 super_admin）
- **响应 data**：{items[]}（每 config_type+key 最新版）
- **主要错误码**：1103 非超管（其余见「通用错误码」）

## PUT /api/v1/admin/configs/{config_key}

**更新系统配置（仅超管+二次确认）**

更新系统配置（仅 super_admin）：写新版本 + 缓存热更新。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（cfg:write（仅超管）+ 二次确认）
- **路径参数**：`config_key`（string，必填）
- **请求体**（application/json）：
  - `snapshot`（object，必填）：配置快照（全量）
  - `reason`（string，必填）：变更原因（审计必填）
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{config_key, version, status}（版本留痕 + 缓存热更新）
- **主要错误码**：1002 键不存在；1103 非超管；1602 缺二次确认（其余见「通用错误码」）

## GET /api/v1/admin/configs/{config_key}/history

**配置版本历史查询（仅超管）**

查询配置键的版本历史（版本号倒序）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（仅超管 super_admin）
- **路径参数**：`config_key`（string，必填）
- **响应 data**：{items[]}（版本历史）
- **主要错误码**：1103 非超管（其余见「通用错误码」）

## POST /api/v1/admin/configs/{config_key}/rollback

**回滚系统配置至指定版本**

回滚系统配置至指定历史版本（仅 super_admin + 二次确认）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（cfg:write（仅超管）+ 二次确认）
- **路径参数**：`config_key`（string，必填）
- **请求体**（application/json）：
  - `target_version`（integer，必填）：回滚目标版本号
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{config_key, version}（回滚至指定版本）
- **主要错误码**：1002 版本不存在；1103 非超管；1602 缺二次确认（其余见「通用错误码」）

## POST /api/v1/admin/login

**后台登录（账密校验，失败锁定，下发 MFA 票据）**

后台登录第一步：账密校验 + 失败锁定 + 下发 MFA 票据。

- **Tag**：admin、后台-配置
- **鉴权**：公开（账密 + 失败锁定）
- **请求体**（application/json）：
  - `username`（string，必填）：后台用户名
  - `password`（string，必填）：明文密码
- **响应 data**：{mfa_required: true, mfa_ticket}
- **主要错误码**：1101 用户名或密码错误(401)；1103 账号已锁定(403)（其余见「通用错误码」）

## GET /api/v1/admin/me

**当前后台账号信息与可访问菜单**

获取当前登录账号信息与可访问菜单。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（get_admin 登录态）
- **响应 data**：{admin_uid, username, display_name, role, domain_scope, phone_masked, menus}
- **主要错误码**：1101 未登录（其余见「通用错误码」）

## POST /api/v1/admin/mfa/verify

**MFA 校验并签发后台令牌**

后台登录第二步：MFA 校验并签发正式 admin token。

- **Tag**：admin、后台-配置
- **鉴权**：公开（MFA 票据校验）
- **请求体**（application/json）：
  - `mfa_ticket`（string，必填）：login 返回的临时票据
  - `code`（string，必填）：验证码（开发模式固定 123456）
- **响应 data**：{token, role, display_name, domain_scope, menus}
- **主要错误码**：1104 票据无效/过期或验证码错误(403)（其余见「通用错误码」）

## POST /api/v1/admin/orders/{order_no}/reconcile-resolve

**对账差异闭环处置（人工确认/转退款）**

对账差异闭环处置：仅 reconcile_status='diff' 订单可处理 → 'resolved'。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（rights:handle + 二次确认）
- **路径参数**：`order_no`（string，必填）
- **请求体**（application/json）：
  - `resolution`（string，必填）：处置结论：manual_matched / refund_required
  - `confirm_token`（string，必填）：二次确认凭证
  - `reason`（，可选）：处置备注（审计用）
- **响应 data**：{order_no, reconcile_status}
- **主要错误码**：1002 订单不存在；1001 resolution 非法(422)；1501 非差异订单(409)；1103 rights:handle；1602 缺二次确认（其余见「通用错误码」）

## GET /api/v1/admin/products

**商品列表（价格配置卡数据源）**

查询商品列表（价格配置卡数据源，直读 product 表）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（get_admin 登录态，价格配置卡数据源）
- **响应 data**：{items[]}（价格配置卡数据源）
- **主要错误码**：1101（其余见「通用错误码」）

## PUT /api/v1/admin/products/{product_code}

**更新商品价格（仅超管+二次确认）**

更新商品价格（仅 super_admin，写审计留痕；下单按新价快照）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（cfg:write（仅超管）+ 二次确认）
- **路径参数**：`product_code`（string，必填）
- **请求体**（application/json）：
  - `price_micro`（integer，必填）：价格（micro，1 元 = 1_000_000）
  - `reason`（，可选）：变更原因（审计留痕）
  - `confirm_token`（，可选）：二次确认凭证
- **响应 data**：{product_code, price_micro}
- **主要错误码**：1002 商品不存在；1103 非超管；1602 缺二次确认（其余见「通用错误码」）

## GET /api/v1/admin/refunds

**退款工单列表**

分页查询退款工单列表（关联订单号展示）。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `status`（，可选）
  - `page`（integer，可选），默认 `1`
  - `page_size`（integer，可选），默认 `20`
- **响应 data**：{items, total, page, page_size}
- **主要错误码**：1103 缺少 rights:handle（其余见「通用错误码」）

## PUT /api/v1/admin/refunds/{request_no}

**处置退款工单（approve 回收权益 / reject 驳回）**

处置退款工单：approve 退款并回收订阅权益；reject 必填驳回理由码。

- **Tag**：admin、后台-配置
- **鉴权**：需后台角色（rights:handle）
- **路径参数**：`request_no`（string，必填）
- **请求体**（application/json）：
  - `action`（string，必填）：处置动作：approve / reject
  - `reject_reason_code`（，可选）：驳回理由码（reject 必填）
  - `reason`（，可选）：处置备注（审计用）
- **响应 data**：{request_no, status, entitlement_recycled}
- **主要错误码**：1002 工单不存在；1001 已处置(409)/驳回缺理由码(422)/action 非法(422)；1103 rights:handle（其余见「通用错误码」）

# history

> 补充分组：4 个历史端点在 OpenAPI 中使用独立 `history` tag（未列入 11 个正式 tags），建议后续任务归并至 C端-问答 或补登正式 tag。

## GET /api/v1/history

**List History**

当前用户历史联合列表：问答会话（done/degraded）+ 报告，时间倒序分页。

- **Tag**：history
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `type`（string，可选）：列表类型，默认 `all`
  - `profile_type`（，可选）：按观察对象过滤
  - `record_date`（，可选）：按上海时区的记录日期筛选
  - `page`（integer，可选）：页码，从 1 开始，默认 `1`
  - `page_size`（integer，可选）：每页条数，默认 `20`
- **响应 data**：{total, page, page_size, items[]}（问答+报告联合列表）
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/history/qa/{session_uid}

**Get Qa Detail**

问答会话详情：sections 全量下发，会员分节按会员状态裁剪。

- **Tag**：history
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **响应 data**：会话详情（sections 全量、非会员裁剪、readonly、content_updated）
- **主要错误码**：1002 不存在/越权/未完成（其余见「通用错误码」）

## GET /api/v1/history/report/{report_uid}

**Get Report Detail**

报告详情（与测评报告同一装配与门控裁剪逻辑）。

- **Tag**：history
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`report_uid`（string，必填）
- **响应 data**：报告视图（blocks 按会员裁剪）
- **主要错误码**：1002 不存在或越权（其余见「通用错误码」）

## GET /api/v1/history/summary

**近七日观察记录概览**

汇总近七日的有效问答与报告记录，并按观察对象统计问答记录数。

- **Tag**：history
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：统一包络 data（详见端点 docstring）

## GET /api/v1/history/{item_type}/{uid}/image

**Get Item Image**

报告长图渲染数据（分享图与免费视图一致，仅含免费区块）。

- **Tag**：history
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`item_type`（string，必填）；`uid`（string，必填）
- **响应 data**：{report_uid, sections, disclaimer_ratio, disclaimer_count, qr_placeholder, scale}
- **主要错误码**：1001 非 report 类型(422)；1002 不存在或越权（其余见「通用错误码」）

---
*本文档由脚本自动生成于 2026-10-14 20:45:50，共 102 个端点。*

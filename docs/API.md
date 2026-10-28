# Babe宝伴后端 API 接口文档

> **生成信息**：由 `backend/scripts/export_api_doc.py` 自动生成（可重复执行，勿手改）
> 生成时间：2026-10-20 20:57:18 ｜ 生成方式：优先抓取运行中服务 `http://127.0.0.1:8000/openapi.json`，失败则本地导入 `app.main.app.openapi()`
> 端点总数：153 ｜ 分组：13 个 tag（12 个正式 tags + history 补充组）

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

- [系统](#系统)（9 个端点）
- [C端-认证同意](#C端-认证同意)（6 个端点）
- [C端-档案](#C端-档案)（20 个端点）
- [C端-问答](#C端-问答)（18 个端点）
- [C端-测评](#C端-测评)（5 个端点）
- [C端-商业化](#C端-商业化)（9 个端点）
- [C端-权利反馈](#C端-权利反馈)（7 个端点）
- [C端-健康与笔记](#C端-健康与笔记)（14 个端点）
- [后台-知识库](#后台-知识库)（11 个端点）
- [后台-词库](#后台-词库)（7 个端点）
- [后台-处置](#后台-处置)（14 个端点）
- [后台-配置](#后台-配置)（28 个端点）
- [history](#history)（5 个端点）

# 系统

## GET /api/v1/admin/metrics/alert-history

**Get Alert History**

告警历史：alert_watch 任务留痕最近 50 条（按发生时间倒序）。

- **Tag**：系统
- **鉴权**：需后台角色（get_admin 登录态，无额外权限矩阵）
- **响应 data**：{items:[{id, metric, value, threshold, message, status, started_at}]}（最近 50 条）
- **主要错误码**：1101 未登录（其余见「通用错误码」）

## GET /api/v1/compliance/ai-label

**AI 生成标识组件下发**

返回标识可见性、文案 text_id、页面固定位与备案号；前端只渲染 text_id 对应文案

- **Tag**：系统
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `page`（string，可选），默认 `answer`
- **响应 data**：{visible, text_id, position, fallback_text, filing_no, pages, min_ratio, min_count}

## GET /api/v1/compliance/copy-checklist

**文案合规检查清单**

RQ-02 §3.2.3 五项检查清单（发布流程勾选留痕）与禁用表述词表

- **Tag**：系统
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{checklist[5 项], forbidden_phrases[], replacements{}, scope[]}

## POST /api/v1/compliance/png-metadata

**PNG 隐式标识写入**

为客户端 canvas 导出的 PNG 补写 AI 隐式标识（tEXt），写入后回读断言，返回合规 PNG

- **Tag**：系统
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `content_type`（string，可选），默认 `share_card`
- **响应 data**：{render_id, metadata{}, label_check{ratio,count,metadata_ok,passed,errors}, byte_size, png_base64}
- **主要错误码**：1001 非 PNG/超 8MB/空文件(422)；1901 隐式标识写入或回读失败(500)；1101（其余见「通用错误码」）

## GET /api/v1/compliance/privacy-pledge

**隐私承诺**

四条（及以上）已实现承诺，每条附可操作跳转；未实现能力不写入承诺

- **Tag**：系统
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{version, items:[{id,title,promise,implemented,evidence,action{label,route}}], training_statement, honesty_note}

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

## GET /api/v1/reminders

**提醒列表与订阅偏好**

返回提醒任务（含站内补达）、订阅偏好总览与待展示数；不展示问答原文

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `limit`（integer，可选），默认 `50`
- **响应 data**：{items:[{task_uid,type,title,body,planned_at,status,trace_id,sent_at,opened_at,delivery}], prefs{items,any_enabled,weekly_max,template_reported}, due_count, weekly_cap}
- **主要错误码**：1301（其余见「通用错误码」）

## PUT /api/v1/reminders/prefs

**设置订阅偏好**

逐类型开启/关闭；关闭即时生效并不再发送任何订阅消息

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `pref_type`（string，必填）：偏好类型（含 all 总开关）
  - `enabled`（boolean，必填）：是否开启
- **响应 data**：{pref_type, enabled, prefs{...}}
- **主要错误码**：1001 pref_type 非法(422)；1301（其余见「通用错误码」）

## POST /api/v1/reminders/prefs/off

**关闭全部触达**

立即生效：待发任务转 skipped、全部类型置关闭；周报站内页仍可回看

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{disabled:true, canceled_tasks, prefs{...}}（关闭即时生效，站内周报仍可回看）
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/reminders/weekly-question

**每周一问**

分龄话题卡 + 预置问题，点击直达问答输入态

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{title, question, kb_id, trace_id, enabled}
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/reminders/weekly-report

**成长周报**

站内周报：本月龄变化、可问主题推荐、上周问答主题标签（不含原文）

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{period{start,end}, profiles[], last_week_topics[], suggested_questions[], privacy_note}（不含问答原文）
- **主要错误码**：1301（其余见「通用错误码」）

## POST /api/v1/reminders/{task_uid}/open

**标记提醒已打开**

归因链起点：返回 reminder_trace_id，提问时透传以支撑 M21

- **Tag**：C端-档案
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`task_uid`（string，必填）
- **响应 data**：{task_uid, status, trace_id}（归因链起点，提问时透传 reminder_trace_id）
- **主要错误码**：1002 任务不存在或非本人；1301（其余见「通用错误码」）

# C端-问答

## GET /api/v1/compliance/ai-label/check

**AI 标识三链路自检**

校验页面契约 / 长图标识 / 导出元数据三条链路的关键断言（抽检辅助，非门禁替代）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{links[3 条链路], passed, min_ratio, min_count}
- **主要错误码**：1101（其余见「通用错误码」）

## GET /api/v1/history/report/{report_uid}/image.png

**测评报告长图**

服务端模板渲染（信任条+分节+免责+双标识）+ PNG tEXt 隐式标识

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`report_uid`（string，必填）
- **响应 data**：image/png 二进制（含 tEXt 隐式标识与双处显式标识）
- **主要错误码**：1002 报告不存在/越权；1901 标识校验失败(500)（其余见「通用错误码」）

## POST /api/v1/qa/photos

**上传图片并送检**

顺序执行压缩→送检；未通过或配额超限即拒绝（不进入推理、不扣额度）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **响应 data**：{photo_uid, scene, moderation_result, expires_at, notice, parse_notice}（multipart：file + scene）
- **主要错误码**：1001 空文件/超 8MB/格式不支持(422)；1303 送检未通过或配额超限(403/429)；1301（其余见「通用错误码」）

## GET /api/v1/qa/photos/guide

**图片提问前置说明**

场景化告知：拍什么、照片如何被处理、何时删除（拒绝授权可改用文字问答）

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `scene`（string，可选），默认 `unknown`
- **响应 data**：{scenes[], selected, privacy_notice, max_count, ttl_hours, degradation}
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/qa/photos/{photo_uid}

**图片元数据**

仅返回元数据（场景/送检结果/删除时间），无原图、无 URL、无后台查看入口

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`photo_uid`（string，必填）
- **响应 data**：{photo_uid, scene, moderation_result, expires_at, deleted_at}（**无原图无 URL**）
- **主要错误码**：1002 不存在或非本人（其余见「通用错误码」）

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
  - `input_mode`（string，可选）：输入形态 text/voice/photo（RQ-05 预留）
  - `photo_uids`（array<string>，可选）：图片标识（photo 模式，≤3 张）
  - `reminder_trace_id`（，可选）：触达归因标识（RQ-08）
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

## GET /api/v1/qa/sessions/{session_uid}/share-card.png

**问答分享长图**

服务端模板渲染（信任条+正文+免责+双标识）+ PNG tEXt 隐式标识；被拦截会话 403

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **响应 data**：image/png 二进制；响应头 X-Render-Id / X-Share-Trace-Id / X-AI-Generated / X-AI-Label-Ratio / X-AI-Label-Count
- **主要错误码**：1002 会话不存在/越权；1102 会话不可分享（被拦截/未完成）403；1901 标识校验失败(500)（其余见「通用错误码」）

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

## POST /api/v1/qa/sessions/{session_uid}/triage/recheck

**追问后重判档位**

把追问内容与首轮问题拼接重判；🟢→🔴 时返回置顶强提醒标记

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`session_uid`（string，必填）
- **请求体**（application/json）：
  - `followup`（string，必填）：追问原文
  - `temperature`（，可选）：体温（℃）
  - `mental_state`（，可选）：精神状态 normal/poor
  - `duration_hours`（，可选）：持续小时数
- **响应 data**：{triage, previous_level, level_changed, escalate_banner, banner_text}
- **主要错误码**：1002 会话不存在/越权；1301 未同意基础协议（其余见「通用错误码」）

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

## POST /api/v1/risk/referral

**就近就医转介**

按场景返回合规机构指引；POI 未接入时降级为城市级急诊指引，不排名不导流

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `scene`（string，可选）：emergency_block / triage_red / pet_redflag
  - `region_city`（，可选）：城市（唯一可落库位置字段）
  - `region_district`（，可选）：区县
  - `lat`（，可选）：纬度（仅本次计算，不落库）
  - `lng`（，可选）：经度（仅本次计算，不落库）
  - `session_uid`（，可选）：关联会话（归因）
- **响应 data**：{available, enabled, items[], notice, fallback_guide, region}（精确坐标不落库；POI 未接时降级城市级指引）
- **主要错误码**：1001 scene 非法(422)；1101（其余见「通用错误码」）

## GET /api/v1/triage/decide

**分级判定（独立）**

按问题与档案（月龄/宠龄）执行规则引擎判定，返回红/黄/绿档位与观察项；未命中分级场景返回 triage=null

- **Tag**：C端-问答
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `question`（string，必填）：问题原文
  - `domain`（string，可选）：child / pet，默认 `child`
  - `profile_uid`（，可选）：档案 UID
- **响应 data**：{triage:{level,level_label,rule_hits[],observations[],escalation_flags[],contraindications[],disclaimers[],night_notice,rule_version}|null, rule_snapshot{source,total,by_scene,signed}, note}
- **主要错误码**：1001 domain 非 child/pet(422)；1002 档案不存在/越权；1301 未同意基础协议（其余见「通用错误码」）

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

## GET /api/v1/topics

**专题包列表**

交叉主题包与宠物行为内容线；红旗前置，交叉内容育儿+宠物专家双签后才上架

- **Tag**：C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `domain`（，可选）
- **响应 data**：{items:[专题包视图], member_included:false}
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/topics/recommended

**专题包场景化推荐**

按入口推荐（family 优先育儿×宠物交叉），挂问答尾部，不做弹窗打扰

- **Tag**：C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `entry`（string，可选）：child / pet / family，默认 `family`
  - `limit`（integer，可选），默认 `2`
- **响应 data**：{items[]}（family 入口优先交叉主题）
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/topics/{topic_code}

**专题包详情**

返回红旗前置块 + 正文块；不含会员权益（专题独立计费）

- **Tag**：C端-商业化
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`topic_code`（string，必填）
- **响应 data**：专题包详情（红旗块前置 + 正文块；会员不含）
- **主要错误码**：1002 不存在或未上架；1301（其余见「通用错误码」）

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

# C端-健康与笔记

## GET /api/v1/health/records

**健康记录列表**

按体检日期倒序；每条含复查提醒状态 due_status（overdue/soon/upcoming/none）

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `subject_type`（，可选）
  - `subject_uid`（，可选）
- **响应 data**：统一包络 data（详见端点 docstring）

## POST /api/v1/health/records

**新建健康记录**

JSON 体：档案主体 + 体检信息；报告文件创建后经 /file 端点单独上传。儿童主体需儿童信息同意有效

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `subject_type`（string，必填）：档案主体类型
  - `subject_uid`（string，必填）：档案对外标识
  - `record_date`（string，必填）：体检日期 YYYY-MM-DD
  - `title`（string，必填）：记录标题
  - `notes`（，可选）：医生建议/备注
  - `next_checkup_date`（，可选）：下次复查日期
  - `next_checkup_note`（，可选）：复查项目说明
- **响应 data**：统一包络 data（详见端点 docstring）

## DELETE /api/v1/health/records/{record_uid}

**删除健康记录**

软删并清理报告文件

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`record_uid`（string，必填）
- **响应 data**：统一包络 data（详见端点 docstring）

## GET /api/v1/health/records/{record_uid}

**健康记录详情**

解密返回医生建议与复查说明

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`record_uid`（string，必填）
- **响应 data**：统一包络 data（详见端点 docstring）

## PUT /api/v1/health/records/{record_uid}

**更新健康记录**

JSON 全量替换可编辑字段（体检日期/标题/备注/复查计划）

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`record_uid`（string，必填）
- **请求体**（application/json）：
  - `record_date`（string，必填）：体检日期 YYYY-MM-DD
  - `title`（string，必填）：记录标题
  - `notes`（，可选）：医生建议/备注
  - `next_checkup_date`（，可选）：下次复查日期
  - `next_checkup_note`（，可选）：复查项目说明
- **响应 data**：统一包络 data（详见端点 docstring）

## POST /api/v1/health/records/{record_uid}/file

**替换报告文件**

multipart 单文件（file 字段），覆盖旧的自动删除。用 POST 而非 PUT：微信 uploadFile 在开发者工具/部分基础库上会把 PUT 静默降级为 POST（2026-10-14 实测）

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`record_uid`（string，必填）
- **响应 data**：统一包络 data（详见端点 docstring）

## GET /api/v1/notes

**笔记列表**

按更新时间倒序，返回标题+摘要；keyword 按标题过滤

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `keyword`（，可选）
- **响应 data**：统一包络 data（详见端点 docstring）

## POST /api/v1/notes

**新建笔记**

正文 Markdown 加密落库；本地敏感词前置检查（命中推广引流词拒绝）

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **请求体**（application/json）：
  - `title`（string，必填）：笔记标题
  - `content`（string，必填）：笔记正文 Markdown
- **响应 data**：统一包络 data（详见端点 docstring）

## DELETE /api/v1/notes/{note_uid}

**删除笔记**

软删

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`note_uid`（string，必填）
- **响应 data**：统一包络 data（详见端点 docstring）

## GET /api/v1/notes/{note_uid}

**笔记详情**

解密返回正文 Markdown 与乐观锁版本号

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`note_uid`（string，必填）
- **响应 data**：统一包络 data（详见端点 docstring）

## PUT /api/v1/notes/{note_uid}

**更新笔记**

乐观锁更新：version 不一致返回 1003；保存前同样过敏感词检查

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`note_uid`（string，必填）
- **请求体**（application/json）：
  - `title`（string，必填）：笔记标题
  - `content`（string，必填）：笔记正文 Markdown
  - `version`（integer，必填）：乐观锁版本号
- **响应 data**：统一包络 data（详见端点 docstring）

## GET /api/v1/tools

**轻工具列表**

结构化内容 + 简单交互；不消耗问答额度，工具页带 AI 标识与免责

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **查询参数**：
  - `domain`（，可选）
- **响应 data**：{items:[{tool_code,title,tool_type,domain,summary,kb_refs,content,disclaimer,ai_label,quota_cost:0}], quota_cost:0, entry:'secondary'}
- **主要错误码**：1301（其余见「通用错误码」）

## GET /api/v1/tools/{tool_code}

**轻工具详情**

返回工具内容（清单步骤 / 解析口径）与免责；不消耗问答额度

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`tool_code`（string，必填）
- **响应 data**：工具视图（含 content 与免责；不消耗问答额度）
- **主要错误码**：1002 工具不存在或未上架；1301（其余见「通用错误码」）

## POST /api/v1/tools/{tool_code}/complete

**完成轻工具自查**

记录完成项数与去向（转化归因）；不消耗问答额度

- **Tag**：C端-健康与笔记
- **鉴权**：需登录（Bearer token，get_current_user）
- **路径参数**：`tool_code`（string，必填）
- **请求体**（application/json）：
  - `completed_items`（integer，可选）：完成项数
  - `next`（，可选）：去向 qa/topic/done
- **响应 data**：{tool_code, completed_items, next, quota_cost:0}
- **主要错误码**：1002 工具不存在；1301（其余见「通用错误码」）

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
  - `source_level`（，可选）：来源等级（DR-10）：guide / academic / institution / media；缺省按 source_type 推导
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
  - `source_level`（，可选）：来源等级 guide/academic/institution/media
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

## GET /api/v1/admin/channels

**危机渠道清单**

单一数据源：问答渠道卡与后台维护读同一张 crisis_channel 表（RQ-03 / DR-26）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{items[], summary{total,verified,placeholder,pending_review,missing_required}, categories{}, data_source:'crisis_channel'}
- **主要错误码**：1103 缺 channel:view（其余见「通用错误码」）

## POST /api/v1/admin/channels

**新增危机渠道**

号码未核验时留空（禁止编造）；新增后需走核验接口留痕

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `channel_code`（string，必填）：渠道编码
  - `channel_name`（string，必填）：渠道名称
  - `category`（string，可选）：psychological / pediatric_emergency / pet_emergency / police / minor_protection
  - `phone_number`（，可选）：号码（未核验留空，禁止编造）
  - `region`（string，可选）：覆盖地域
  - `service_hours`（，可选）：服务时段
  - `applicable_categories`（array<string>，可选）：适用的风险类别编码清单
  - `script`（，可选）：引导话术
  - `sort_weight`（integer，可选）：排序权重（小者优先）
- **响应 data**：渠道视图（号码未核验留空，禁止编造）
- **主要错误码**：1001 编码已存在(409)；1103 缺 channel:edit（其余见「通用错误码」）

## PUT /api/v1/admin/channels/{channel_code}

**编辑危机渠道**

修改号码需二次确认 + 原因 + 渠道编码后 4 位（对齐 V3.0 §3.4）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`channel_code`（string，必填）
- **请求体**（application/json）：
  - `channel_name`（，可选）
  - `phone_number`（，可选）
  - `category`（，可选）
  - `region`（，可选）
  - `service_hours`（，可选）
  - `applicable_categories`（，可选）
  - `script`（，可选）
  - `sort_weight`（，可选）
  - `status`（，可选）
  - `reason`（string，可选）：变更原因（改号码必填）
  - `channel_code_suffix`（，可选）：改号码二次确认：输入渠道编码后 4 位
  - `confirm_token`（，可选）：危险操作二次确认凭证
- **响应 data**：渠道视图（乐观字段更新）
- **主要错误码**：1002 不存在；1001 后 4 位校验不通过/缺原因(422)；1103；1602 改号码缺二次确认（其余见「通用错误码」）

## POST /api/v1/admin/channels/{channel_code}/review

**提交渠道核验记录**

人工拨测/官网核对结论留痕（≥3 年），成功核验后自动顺延复核到期日

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`channel_code`（string，必填）
- **请求体**（application/json）：
  - `review_method`（string，必填）：call_dial / official_site / verbal / document
  - `review_result`（string，必填）：reachable / unreachable / changed / pending
  - `conclusion`（，可选）：结论说明
  - `note`（，可选）：备注
- **响应 data**：{review_no, channel, summary}（核验留痕 ≥3 年，成功核验顺延复核到期日）
- **主要错误码**：1002 不存在；1001 方式/结论非法(422)；1103 缺 channel:review（其余见「通用错误码」）

## GET /api/v1/admin/channels/{channel_code}/reviews

**渠道核验记录**

按时间倒序返回核验留痕（核验人/方式/结论/时间/版本）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`channel_code`（string，必填）
- **响应 data**：{items[]}（核验人/方式/结论/时间/版本）
- **主要错误码**：1103 缺 channel:view（其余见「通用错误码」）

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

## POST /api/v1/admin/copy-scan

**文案合规扫描**

全量仓库扫描或指定文案扫描；命中即 blocked（fail-closed 口径）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `texts`（object，可选）：{名称: 文案}
- **响应 data**：{mode, result{hits[],hit_count,scanned_files,blocked,errors}, checklist[]}（texts 为空时扫全仓库）
- **主要错误码**：1103 缺 content:view（其余见「通用错误码」）

## GET /api/v1/admin/gates/summary

**V3.1 发布门禁自检**

四项阻塞门禁（AI 标识三链路 / 拟人化零命中 / 渠道核验 / 分级规则专家确认）当前状态

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{gates[4 项发布门禁], passed}（未达标如实显示 false）
- **主要错误码**：1103 缺 content:view（其余见「通用错误码」）

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

## GET /api/v1/admin/reminders/stats

**触达任务统计**

按类型/状态统计提醒任务；仅出统计与状态，不展示问答原文

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{total, by_type, by_status, delivered_by_channel, send_fail, privacy_note}（不含问答原文）
- **主要错误码**：1103 缺 content:view（其余见「通用错误码」）

## GET /api/v1/admin/tools

**轻工具列表（后台）**

含未上架条目；内容命中确定性进食结论即拒绝保存

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{items[]}（含未上架与 issues）
- **主要错误码**：1103 缺 content:view（其余见「通用错误码」）

## POST /api/v1/admin/tools

**新增或更新轻工具**

内容来自知识资产（kb_refs 可追溯）；含确定性进食结论即拒绝（AC-RQ12-4）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `tool_code`（string，必填）
  - `title`（string，必填）
  - `tool_type`（string，必填）：checklist / parser
  - `domain`（string，可选）：child / pet
  - `summary`（，可选）
  - `kb_refs`（array<string>，可选）
  - `content`（object，可选）
  - `sort_order`（integer，可选）
  - `status`（string，可选）：on / off
  - `confirm_token`（，可选）
- **响应 data**：{tool_code, status}
- **主要错误码**：1001 含确定性进食结论或类型非法(422)；1103 缺 content:edit（其余见「通用错误码」）

## GET /api/v1/admin/topics

**专题包列表（后台）**

含未上架草稿；交叉主题包展示双签状态与上架校验问题

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **响应 data**：{items[]}（含草稿、双签状态与 publish_issues）
- **主要错误码**：1103 缺 content:view（其余见「通用错误码」）

## POST /api/v1/admin/topics

**新增或更新专题包**

交叉主题包须育儿+宠物专家双签；行为内容线须红旗前置结构合规

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **请求体**（application/json）：
  - `topic_code`（string，必填）
  - `title`（string，必填）
  - `domain`（string，必填）：cross / behavior / child / pet
  - `summary`（，可选）
  - `price_micro`（integer，可选）
  - `product_code`（，可选）
  - `redflag_first`（boolean，可选）
  - `redflag_blocks`（array<object>，可选）
  - `content_blocks`（array<object>，可选）
  - `review_child_signoff`（，可选）
  - `review_pet_signoff`（，可选）
  - `status`（string，可选）：draft / on / off
- **响应 data**：{topic, publish_issues}（status=on 且不满足条件即拒绝并列出问题）
- **主要错误码**：1001 domain/结构/双签不满足(422)；1103 缺 content:edit（其余见「通用错误码」）

## GET /api/v1/admin/triage-rules

**分级规则列表**

条目化分级规则（RQ-06 AC-6）：可配置、带来源与专家审核记录

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **查询参数**：
  - `scene`（，可选）
- **响应 data**：{items[], snapshot, signed, total, gate_ready}
- **主要错误码**：1103 缺 triage:view（其余见「通用错误码」）

## PUT /api/v1/admin/triage-rules/{rule_id}

**编辑分级规则**

阈值/档位变更需二次确认 + 原因；变更后规则快照 60 秒内生效

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`rule_id`（string，必填）
- **请求体**（application/json）：
  - `title`（，可选）
  - `level`（，可选）：red / yellow / green
  - `priority`（，可选）
  - `conditions`（，可选）
  - `basis`（，可选）
  - `observations`（，可选）
  - `escalation_flags`（，可选）
  - `contraindications`（，可选）
  - `disclaimers`（，可选）
  - `status`（，可选）：active / inactive / draft
  - `reason`（string，可选）：变更原因
  - `confirm_token`（，可选）：危险操作二次确认凭证
- **响应 data**：{rule, snapshot}（阈值/档位变更需二次确认 + 原因，60s 内生效）
- **主要错误码**：1002 不存在；1001 level 非法(422)；1602 缺二次确认；1103 缺 triage:edit（其余见「通用错误码」）

## POST /api/v1/admin/triage-rules/{rule_id}/review

**分级规则专家确认**

首批/变更规则须专家书面确认后才满足发布门禁（§7.2）

- **Tag**：后台-配置
- **鉴权**：需后台角色（get_admin + 角色权限矩阵）
- **路径参数**：`rule_id`（string，必填）
- **请求体**（application/json）：
  - `expert_signoff`（string，必填）：专家签署（姓名/工号）
  - `note`（，可选）
- **响应 data**：{rule, signed, total, gate_ready}（专家书面确认留痕，§7.2 门禁前置）
- **主要错误码**：1002 不存在；1103 缺 triage:review（其余见「通用错误码」）

# history

> 补充分组：4 个历史端点在 OpenAPI 中使用独立 `history` tag（未列入 12 个正式 tags），建议后续任务归并至 C端-问答 或补登正式 tag。

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
*本文档由脚本自动生成于 2026-10-20 20:57:18，共 153 个端点。*

## 17. 埋点事件字典

> **本章定位**：把 §9.3 的「事件名 + 关键参数」两列清单，升级为**可开发、可验收、可审计**的事件字典。§9.3 仍是事件登记的**权威清单**；本章是它的**字段级展开**，并为 UI 文档逐页「埋点」行中出现、但 §9.3 未登记的事件补齐登记。
>
> **合稿提示**：V1.1 中 `## 17` 为「追溯矩阵」。合稿时本章插入为 §17，原「追溯矩阵」顺延为 §18，§17.1 的「需求 → 页面 → 埋点 → 验收」表保持不动。
>
> **口径权威**：指标口径唯一权威＝§9.4；性能口径唯一权威＝§7.7；留存期唯一权威＝§9.1 + §11.7（AS-25）；安全验收唯一权威＝§6.12 脚注（冻结标注集）。本章**不新设**口径，只把口径落到事件与字段上。
>
> **编号**：本章只引用已存在的 `FR-x.x` / `NFR-x.x` / `AS-xx` / `Q-xx` / `D-xx` / `CG-x` / `SC-xx` / `PA-xx`，不新增编号。

### 17.1 状态词汇与简写约定

**状态词汇（三态，与 V1.2 §0.3 一致）**：本章对每个事件/字段标注以下三态之一。

| 状态 | 含义 | 本章落点 |
| --- | --- | --- |
| `已决策，可开发` | 上游决策与口径已闭合，可直接排期开发 | 总表默认态（未额外标注者） |
| `有默认方案，可开发但需记录风险` | 有可执行的默认取值，但上游 AS/Q/D 未最终拍板，需在技术方案中登记残余风险 | 见 §17.9.1 |
| `未决策，不得开发` | 缺少决策即无法确定字段值域或触发时机，**不得开工**，只允许预留字段名 | 见 §17.9.2 |

**简写码**（总表单元格使用，避免长句）：

| 列 | 码 | 含义 |
| --- | --- | --- |
| 是否去重 | `—` | 不去重，明细全量 |
| | `U/D` | `user_id` + 自然日 |
| | `U/E/D` | `user_id` + 事件名 + 自然日 |
| | `U/∞` | `user_id` + 事件名，永久仅 1 条（首次类） |
| | `S` | `session_id`（同会话仅 1 条） |
| | `R` | `client_request_id`（幂等键，同键折叠为 1 条） |
| | `B` | 业务主键（`order_id`/`kb_id+version`/`request_no`/`appeal_id`/`report_no`/`assessment_id`） |
| 失败是否上报 | `A` | 异步；失败静默丢弃；**不影响主流程**；不重试 |
| | `B` | 异步 + 客户端本地缓存补发（≤500 条 / ≤7 天）；不影响主流程 |
| | `C` | **服务端与业务同源落库**（审计/合规/交易留痕）；写入失败按业务失败处理；不依赖客户端重试 |
| | `D` | 服务端异步 + 重试队列（≥3 次指数退避）；失败告警；不影响主流程 |
| 隐私限制 | `N0` | 无个人信息，仅匿名聚合计数 |
| | `N1` | 含 `user_id` 等内部标识；可进分析库；**禁止出境**；不含敏感个人信息 |
| | `N2` | 含敏感个人信息或业务敏感字段；须哈希/脱敏；分析库**仅收聚合** |
| | `N3` | 仅落合规/审计库；**禁止进入分析库** |
| | `N4` | 该字段禁止采集（见 §17.8） |
| 保留期 | `L6M` | ≥6 个月（网络与操作日志口径，§11.7） |
| | `L3Y` | ≥3 年（合规留档 / 交易信息，§11.7） |
| | `L1Y` | ≥1 年（用量口径，§9.1 免费额度用量） |
| | `ACCT` | 账号存续期（其他个人信息，最短必要，§11.7） |
| | `AGG` | 聚合长期 / 明细 90 天 |
| | `AGG6` | 聚合长期 / 明细 ≥6 个月 |

**两条防双计规则（开发必须遵守）**：

1. `risk_block_leave`（SC-13）触发时**必须同时**写 `qa_risk_block_followup(next_action=leave)`；报表口径**只取** `qa_risk_block_followup`。
2. `content_report`（§9.3，举报入口/详情）与 `content_report_submit`（SC-11/SC-26，提交成功）为**漏斗两步**，不得相加；举报量口径只取 `content_report_submit`。

### 17.2 埋点规范

#### 17.2.1 事件命名规则

| 规则 | 内容 |
| --- | --- |
| 结构 | `<域>_<对象>_<动作>`，全小写 snake_case，只用 `[a-z0-9_]` |
| 域前缀 | `app`/`disclaimer`/`consent`/`home`/`entry`/`profile`/`pet`/`qa`/`risk`/`crisis`/`assessment`/`report`/`history`/`paywall`/`order`/`pay`/`refund`/`quota`/`feedback`/`content`/`kb`/`term`/`log`/`privacy`/`rights`/`account`/`admin`/`config`/`agent`/`output`/`reconcile` |
| 动作后缀表 | `_view` 曝光/页面可见、`_show` 弹窗或组件渲染成功、`_click` 点击、`_exposure` 进入可视区、`_submit` 提交**成功**、`_agree`/`_decline` 同意/拒绝、`_start`/`_done`/`_complete` 流程成对、`_save` 保存成功、`_fail` 失败、`_rollback` 回滚、`_publish`/`_unpublish` 上架/下架、`_change` 变更、`_result` 结果落定 |
| 禁止 | ① 事件名携带参数值（禁 `qa_submit_voice`，应为 `qa_submit` + `input_mode`）；② 一个事件描述两个动作；③ 复用事件名表达不同语义 |
| 成对约束 | `_start` 必须有对应 `_done`/`_complete`/`_fail`；`_view` 与 `_click` 必须可配成漏斗（曝光分母缺失时按 §17.6 补 `_exposure`） |
| 命名权威 | 事件名的唯一权威是 §9.3 + 本章 §17.3；UI 文档出现的名称与本章不一致时，以本章「别名」列映射，**代码只实现本章事件名** |

#### 17.2.2 字段命名规则

| 规则 | 内容 |
| --- | --- |
| 结构 | snake_case；布尔加 `is_`/`has_` 前缀；枚举后缀 `_type`/`_status`/`_mode`/`_reason`/`_code`/`_band`；计数 `_count`；时长 `_ms`（int 毫秒）；金额 `_micro`（int，1 元 = 1 000 000，**禁浮点**）；标识 `_id` |
| 可识别标识 | 可识别 ID 必须哈希后以 `_hash` 结尾（如 `profile_id_hash`），**禁止** `nickname`/`phone`/`openid`/`birthday` 等字段名出现在 schema 中（`N4`） |
| 数组 | `xxx_ids[]`，元素只允许 ID/枚举；长度 ≤50；**禁止自由文本数组** |
| 文本长度 | 文本类只上报长度 `char_len`（int）；仅 `N3` 合规库允许存原文，且**不经埋点通道** |
| 枚举 | 每个枚举字段必须在 schema 中登记完整值域；未登记值一律上报为 `unknown` 并计入 `schema_violation` 告警，**禁止**上报原始值 |
| 版本 | 每次 schema 变更（增删字段、改枚举）必须升 `schema_version`；字段删除需保留 ≥2 个版本 |

#### 17.2.3 时间戳与时区

| 项 | 规定 |
| --- | --- |
| `ts_client` | 客户端事件发生时间，int64 毫秒；客户端时间不可信 |
| `ts_server` | 服务端接收时间，int64 毫秒（UTC）；**所有分析口径一律用 `ts_server`** |
| 时钟偏移 | `|ts_client − ts_server| > 5 分钟` 时置 `clock_skew=true`，该事件不参与耗时类指标 |
| 时区 | 自然日、cohort 窗口、额度周期**统一按 Asia/Shanghai（UTC+8）** 切分；周口径为自然周（周一 00:00 起） |
| 耗时 | 一律用服务端 `_ms` 差值，不得用客户端上报的 `elapsed_ms` 计算 P95（`elapsed_ms` 仅作体验观测） |

#### 17.2.4 公共字段（每个事件必带）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_id` | str(uuid4) | 事件幂等键；同 `event_id` 重复上报服务端去重 |
| `event_name` | enum | 本章 §17.3 登记的事件名 |
| `schema_version` | str | 事件 schema 版本 |
| `ts_client` / `ts_server` | int64(ms) | 见 §17.2.3 |
| `user_id` | str | 匿名内部 ID；**禁止** openid/unionid（`N4`） |
| `session_id` | str | 会话 ID；`session_id` 按账号维度生成，跨端不复用 |
| `platform` | enum | `mp`（小程序）/`android`/`ios`/`admin` |
| `app_version` / `os_version` / `sdk_version` | str | 版本三元组，用于灰度归因 |
| `device_type` | enum | 机型档位（`low`/`mid`/`high`），**禁止**设备指纹与 IMEI/OAID |
| `network` | enum | `wifi`/`4g`/`5g`/`other`/`offline` |
| `is_member` | bool | 事件发生时点会员状态 |
| `is_new_user` | bool | 仅 `app_launch` 权威写入；判定规则＝该 `user_id` 首次 `app_launch` |
| `page_id` | enum | `SC-01`~`SC-26` / `PA-01`~`PA-08` / `backend`（无页面） |
| `experiment_id` / `bucket` | str / int | 灰度与实验分流，见 §17.2.6 |
| `config_version` | str | 命中的配置版本号，用于配置回滚归因（FR-K8） |
| `client_request_id` | str | 问答/支付链路幂等键；非链路事件可缺省 |
| `trace_id` | str | 服务端链路追踪 ID，用于还原 NFR-5.1 |

#### 17.2.5 批量、压缩与上报可靠性

| 项 | 规定 |
| --- | --- |
| 触发上报 | 本地队列满 20 条、或 15s 定时、或切后台/退出前 flush |
| 批量上限 | 单批 ≤100 条；gzip 压缩后 ≤64KB；单次上报超时 3s |
| 重试 | 失败重试 3 次指数退避（1s / 5s / 30s） |
| 补发 | 3 次仍失败入本地持久队列（≤500 条 / ≤7 天），下次启动补发（码 `B`） |
| 主流程隔离 | 除码 `C` 的事件外，**任何埋点失败不得阻断、不得回滚主流程**；SDK 异常必须 catch 并静默降级 |
| 采样 | 安全类（`qa_risk_block`、`risk_*`、`crisis_*`）、交易类（`order_*`、`pay_*`、`refund_*`）、同意与权利类（`consent_*`、`rights_*`、`account_delete_*`）**100% 上报，禁止采样**；曝光类（`home_view`、`entry_exposure`）在 DAU 超阈值后可 10% 采样，但必须带 `sampled=true` 与 `sample_rate` |
| 超大参数截断 | 单字段字符串 ≤256 字符，超长截断并置 `_truncated=true`；数组 ≤50 元素；单事件序列化 ≤4KB；超限时**先丢非必填字段**并上报 `_dropped_fields`；**枚举字段禁止截断**（属值域错误，上报 `schema_violation`） |
| 服务端权威 | `qa_risk_block`、`pay_success`、`consent_*`、`rights_request_submit`、`account_delete_confirm` 的业务事实以**服务端落库为准**，客户端事件只作体验观测，冲突时以服务端为准 |

#### 17.2.6 灰度与实验分流字段

| 字段 | 规定 |
| --- | --- |
| `experiment_id` | 来自配置版本表（FR-K8 / PA-08）；无实验时置 `none` |
| `bucket` | 0–99 整数，`hash(user_id) % 100`，保证同用户同桶；跨端一致 |
| 分流三元组 | `platform` + `app_version` + `bucket` 共同构成灰度分流键（§13.2 灰度开关按入口粒度） |
| `config_version` | 每次事件携带命中配置版本，用于「配置回滚前后行为对比」（§13.3） |
| 入口粒度 | 紧急下线开关按入口（育儿问答/宠物问答/综合问答/测评/会员）分别生效，事件须带 `entry_type` 或 `page_id` 以便按入口切分 |
| 状态 | 灰度与实验分流字段：`有默认方案，可开发但需记录风险`（默认取值＝AS-32 体验版邀请内测 + PA-08 灰度开关；Q-30 关闭前按此实现） |

### 17.3 事件字典总表

> 共 **119** 个事件：§9.3 已登记 **42** 个 + 本次新登记 **77** 个（UI 来源 68 个 + 口径缺口补登记 9 个）。每个事件一行，列为固定 10 列。

#### 17.3.1 准入与同意（9 个）

> **采集目的**：验证合规同意链路的送达—同意—拒绝—撤回闭环，支撑留存与放弃率口径；本组**不含任何身份原文**。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `app_launch` | 小程序冷启/热启 | `launch_scene`、`is_new_user`、`network` | enum、bool、enum | `U`+`session_id` | `B` | `N1`；`launch_scene` 只允许白名单枚举，**禁止上报 scene 原始串（含 query）** | `L6M` | FR-B4、NFR-5.1 | 新用户 7 日留存、入口点击率分母、分享带来新增 |
| `disclaimer_show` | SC-01 弹窗渲染成功 | `protocol_version`、`is_first_show` | str、bool | `U/E/D` | `B` | `N1` | `L6M` | FR-A1、FR-A5 | 免责触达率 |
| `disclaimer_agree` | 勾选并点「进入」 | `protocol_version`、`guardian_claimed` | str、bool | `—` | `C`（同意记录同源） | `N1`；`guardian_claimed` 仅为布尔声明，**禁止**上报核验材料与手机号 | `L3Y` | FR-A1、FR-A3 | 同意转化率 |
| `disclaimer_decline` | 未勾选点「进入」被拦截 / 主动退出 | `protocol_version`、`decline_reason` | str、enum | `—` | `B` | `N1`；`decline_reason` 只允许枚举，**禁自由文本** | `L6M` | FR-A1 | 拒绝放弃率 |
| `consent_child_show` | SC-06 独立同意弹窗渲染 | `consent_version`、`entry_scene` | str、enum | `U/E/D` | `B` | `N1` | `L6M` | FR-A2 | 单独同意触达率 |
| `consent_child_agree` | 勾选并提交 | `consent_version`、`guardian_verified` | str、enum | `—` | `C` | `N1`；`guardian_verified` 只记核验方式枚举 | `L3Y` | FR-A2、FR-A3、CG2/CG3 | 单独同意通过率 |
| `consent_child_decline` | 拒绝/关闭弹窗 | `consent_version`、`decline_action` | str、enum | `—` | `B` | `N1` | `L6M` | FR-A2 | 儿童档案流失率（分母 `consent_child_show`） |
| `consent_withdraw_start`（别名 `consent_withdraw`＝§9.3，UI SC-24 名称优先） | SC-24 进入撤回流程 | `consent_type`、`warn_shown` | enum、bool | `U/E/D` | `B` | `N1` | `L6M` | FR-A6、CG7 | 撤回漏斗分母 |
| `consent_withdraw_done` | 确认撤回成功 | `consent_type`、`affect_profile_count` | enum、int | `—` | `C` | `N1`；只记受影响档案数 | `L3Y` | FR-A6、CG7 | 撤回完成率 |

#### 17.3.2 档案（14 个）

> **采集目的**：度量建档—编辑—切换—删除全链路，并为首页入口与留存分层提供「是否已建档」维度；儿童可识别字段一律以哈希与月龄档代替。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `home_view` | SC-02 首页可见 | `profile_count`、`quota_remain` | int、int | `U/D` | `B` | `N1`；只记数量，不记档案标识 | `L6M` | FR-B1 | 入口点击率分母、7 日留存回访 |
| `entry_click` | 点击首页入口卡 | `entry_type`、`with_profile` | enum、bool | `U/E/D` | `B` | `N1` | `L6M` | FR-B1、FR-B4 | 入口点击率（G-2）、入口排序效果 |
| `entry_exposure` | 入口卡进入可视区 ≥1s | `entry_type`、`slot` | enum、int | `U/E/D` | `B` | `N1` | `AGG6` | FR-B1 | 入口曝光—点击率（补 C8 缺口） |
| `profile_center_view` | SC-23 个人中心可见 | `is_member` | bool | `U/D` | `B` | `N1` | `L6M` | FR-I1 | 个人中心渗透率 |
| `profile_view` | SC-03 档案列表可见 | `profile_type`、`profile_count` | enum、int | `U/E/D` | `B` | `N2`；**禁止**昵称/出生日期/过敏项原文，档案以 `profile_id_hash` 标识 | `L6M` | FR-C1、FR-C2 | 建档转化率分母 |
| `profile_form_view` | SC-04 建档表单可见 | `profile_type`、`entry_scene` | enum、enum | `U/E/D` | `B` | `N2` | `L6M` | FR-C1 | 表单到达率、建档漏斗 |
| `profile_create` | 提交建档成功 | `profile_type`、`field_filled_bitmap`、`age_band` | enum、str、enum | `B` | `C`（与档案落库同源） | `N2`；只上报字段填写位图与月龄档，**禁止**昵称/生日/身高体重/过敏项原文 | `ACCT` | FR-C1、FR-C3 | 建档成功率、留存 cohort 分层 |
| `profile_save` | 表单保存成功（新建/编辑） | `profile_id_hash`、`is_new`、`changed_fields[]` | str、bool、enum[] | `B` | `C` | `N2`；`changed_fields` 只记字段名不记值 | `ACCT` | FR-C1、FR-C6 | 编辑成功率、并发冲突率 |
| `profile_set_current` | 切换当前问答对象 | `profile_id_hash`、`from_type`、`to_type` | str、enum、enum | `S` | `B` | `N2` | `L6M` | FR-C5 | 多档案使用率 |
| `profile_delete_start` | SC-07 删除入口点击 | `profile_id_hash`、`delete_mode` | str、enum | `—` | `B` | `N2` | `L6M` | FR-C4 | 删除漏斗分母 |
| `profile_delete_confirm` | 二次确认后执行删除 | `delete_mode` | enum | `—` | `C`（与删除同源 + 审计） | `N2` | `L3Y` | FR-C4 | 级联删除占比（验收 5） |
| `profile_delete_cascade` | 级联删除完成 | `delete_mode`、`affected_sessions`、`affected_reports` | enum、int、int | `—` | `C` | `N2`；只记计数 | `L3Y` | FR-C4、AS-13 | 级联影响面、脱敏处置举证 |
| `pet_form_view` | SC-05 宠物表单可见 | `pet_type` | enum | `U/E/D` | `B` | `N1` | `L6M` | FR-C2 | 宠物建档漏斗 |
| `pet_save` | 宠物档案保存 | `pet_type`、`age_band`、`is_neutered` | enum、enum、bool | `B` | `C` | `N1`；品种等只记枚举，**禁自由文本** | `ACCT` | FR-C2、AS-10 | 宠物模块渗透（G-1） |

#### 17.3.3 问答与风险（19 个）

> **采集目的**：度量问答链路的调度、耗时、降级、成本与风险拦截后的用户行为，并支撑 §9.4 的拦截后离开率与离线安全指标；**提问原文一律不进埋点**。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qa_submit` | 提交提问 | `client_request_id`、`input_mode`、`bind_profile`、`entry`、`is_retry`、`char_len` | str、enum、bool、enum、bool、int | `R`（同键折叠并置 `is_retry=true`） | `B` | `N2`；**禁止上报提问原文**；`input_mode` MVP 只允许 `text` | `L6M` | FR-D1、FR-F1、FR-G1、NFR-9.5、AS-24 | 二次提问率分母、单位成本分母、线上拦截率分母 |
| `qa_retry` | 失败/阻断/断网后重试 | `client_request_id`、`retry_reason`、`retry_no` | str、enum、int | `R` | `B` | `N2` | `L6M` | NFR-8.4、NFR-9.5、AS-24 | 重试率、幂等命中率、成本扣减正确性 |
| `qa_result_view` | 回答渲染完成 | `client_request_id`、`request_type`、`agent_count`、`agent_ids[]`、`is_conflict`、`is_degraded`、`first_packet_ms`、`is_member_content` | str、enum、int、enum[]、bool、bool、int、bool | `R` | `B` | `N2`；`agent_ids` 为服务端枚举，非用户数据 | `L6M` | FR-G3、FR-G4、FR-G5、NFR-5.1 | 冲突标注率、P95 响应时长、调度正确率（G-3） |
| `qa_followup` | 同一会话再次提问 | `session_id`、`parent_request_id`、`question_no` | str、str、int | `S`+`question_no` | `B` | `N2` | `L6M` | FR-D1 | 问答二次提问率分子 |
| `qa_risk_block` | 风险拦截判定生效 | `client_request_id`、`level`、`score_band`、`rule_hit_id`、`body_emitted`、`response_bytes`、`risk_event_no` | str、enum、enum、str、bool、int、str | `R` | `D`（安全类必须落库并写高风险事件表） | `N3`；`rule_hit_id` 只记规则 ID，**禁止上报命中词条与用户原文**；`category_group` 未决策（见 §17.9.2） | `L3Y` | FR-L1、FR-L2 | 线上拦截量、召回率回放、命中后正文为空率 |
| `qa_risk_block_followup` | 拦截后的用户行为回流 | `session_id`、`next_action`、`delay_ms` | str、enum、int | `S`（同会话只记首个动作） | `B` | `N3` | `AGG6` | FR-L3、FR-L4 | 高危拦截后离开率分子 |
| `risk_block_leave` | SC-13 停留超时/返回离开 | `session_id`、`risk_event_no`、`stay_ms` | str、str、int | `S` | `B` | `N3`；只记事件编号，**禁原文**；须同写 `qa_risk_block_followup` 防双计 | `L6M` | FR-L2 | 高危拦截后离开率（辅助校验） |
| `risk_appeal_submit` | SC-13 提交误报申诉 | `risk_event_no`、`appeal_id`、`has_attachment`、`desc_len` | str、str、bool、int | `B` | `B` | `N3`；补充说明为自由文本，**禁进分析库**，只上报 `desc_len`；截图不落埋点 | `L3Y` | FR-L4、NFR-9.9 | 申诉量、申诉闭环率分母 |
| `risk_appeal_allow` | 申诉放行标记生效 | `appeal_id`、`allow_mode` | str、enum | `B` | `D` | `N3` | `L3Y` | FR-L4 | 申诉后继续提问率 —— **未决策，不得开发**（放行时机见 §17.9.2） |
| `risk_appeal_review` | 后台申诉复核完成 | `appeal_id`、`review_result`、`elapsed_hours`、`sla_met` | str、enum、int、bool | `B` | `C`（审计留痕） | `N3` | `L3Y` | FR-L4、NFR-9.9 | 申诉闭环率分子、线上误报率 |
| `crisis_channel_call` | 点击一键拨号 | `session_id`、`channel_id`、`risk_event_no` | str、enum、str | `S`+`channel_id` | `B` | `N3`；**禁止上报目标号码、热线全文与渠道自由文本**，只记 `channel_id` | `L6M` | FR-L3、CG9 | 危机渠道触达率（G-4 可埋点验证） |
| `crisis_channel_copy` | 复制渠道号码/话术 | `session_id`、`channel_id` | str、enum | `S`+`channel_id` | `B` | `N3`；**不得把复制内容写入埋点参数** | `L6M` | FR-L3、CG9 | 渠道触达率（拨号失败备用口径） |
| `qa_degraded` | 降级输出 | `client_request_id`、`reason`、`failed_agent_ids[]`、`quota_counted` | str、enum、enum[]、bool | `R` | `D` | `N2` | `L6M` | FR-G6、NFR-8.3、§7.7 | 降级率、Agent 失败率、不计次校验 |
| `agent_call` | 单 Agent 调用结束 | `session_id`、`agent_id`、`status`、`duration_ms`、`confidence_band` | str、enum、enum、int、enum | `R`+`agent_id` | `D` | `N2`；输入摘要由服务端脱敏生成，**禁原始输入** | `AGG6` | NFR-5.1、NFR-5.2、FR-K3 | Agent 失败率/超时率、调度正确率 |
| `output_filter_hit` | 输出侧敏感词过滤命中 | `client_request_id`、`rule_id`、`action` | str、str、enum | `R` | `D` | `N3` | `L6M` | NFR-1.1、NFR-9.8、CG14 | 违规词命中率（G-6，目标 0） |
| `collab_agent_expand` | 展开「参与 Agent」折叠区 | `session_id`、`agent_count` | str、int | `U`+`S` | `B` | `N1` | `L6M` | FR-G3 | 协同透明度使用率 |
| `qa_cost` | 单次问答模型成本落账 | `client_request_id`、`model_id`、`prompt_tokens`、`completion_tokens`、`cache_hit`、`cost_micro` | str、enum、int、int、bool、int | `R` | `D` | `N2`；模型用量非个人信息，可进分析库；`cost_micro` 仅留聚合 | `AGG6` | NFR-6.1、NFR-6.3、§7.13、AS-31 | 单位问答成本（护栏） |
| `quota_exhausted` | 额度裁决为用尽 | `used_today`、`limit_snapshot`、`is_member` | int、int、bool | `U/D` | `D` | `N1` | `L1Y` | FR-J3、NFR-6.2、AS-02 | 额度用尽率、付费前置漏斗 |
| `quota_exhausted_view` | SC-21 额度用尽态可见 | `source`、`is_member` | enum、bool | `U/D` | `B` | `N1` | `L6M` | FR-J3、AS-08 | 额度闸门转化率 |

#### 17.3.4 测评与报告（13 个）

> **采集目的**：度量测评引导—作答—断点—完成全链路与报告查看—保存—分享链路；作答明细只留维度与分值，报告只留类型码与档位。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `assessment_intro_view` | SC-14 引导页可见 | `has_resume` | bool | `U/D` | `B` | `N1` | `L6M` | FR-E1 | 测评入口点击率分母（G-2） |
| `assessment_start` | 点击开始作答 | `assessment_id`、`question_version`、`is_resume`、`entry` | str、str、bool、enum | `B` | `B` | `N1` | `L6M` | FR-E1、FR-E2 | 测评完成率分母（AS-01） |
| `assessment_exit_before_start` | 未开始即离开引导页 | `entry`、`stay_ms` | enum、int | `U/D` | `B` | `N1` | `L6M` | FR-E1 | 引导页流失率 |
| `assessment_answer` | 单题作答 | `assessment_id`、`question_no`、`dimension`、`score` | str、int、enum、int | `B`+`question_no` | `B` | `N2`；只上报维度与 5 点分值，**禁止**关联儿童信息 | `AGG` | FR-E2、AS-15 | 作答分布、题目质量 |
| `assessment_exit_save` | 退出并保存断点 | `assessment_id`、`question_no` | str、int | `B` | `B` | `N1` | `AGG` | FR-E1、AS-15 | 断点率 |
| `assessment_resume` | 断点续填 | `assessment_id`、`resume_from_q` | str、int | `B` | `B` | `N1` | `AGG` | FR-E1、NFR-2.3 | 续填率 |
| `assessment_complete` | 提交完成 | `assessment_id`、`question_version`、`elapsed_ms`、`type_code` | str、str、int、enum | `B` | `C` | `N1`；分析库只留 `type_code` 与维度档，**不留作答明细** | `ACCT` | FR-E3、FR-E4 | 测评完成率分子（AS-01） |
| `report_view` | 报告页可见 | `report_id`、`report_type`、`from` | str、enum、enum | `B`+`U` | `B` | `N1` | `ACCT` | FR-E4、FR-H2 | 报告查看率 |
| `report_save_image` | 保存长图成功 | `report_id`、`report_type`、`channel` | str、enum、enum | `B` | `B` | `N1`；**图片本身不进埋点** | `L6M` | FR-E5、FR-H3、CG1 | 保存率、AI 标识随图外传量 |
| `report_share` | 触发分享 | `report_id`、`share_target`、`with_qr`、`privacy_masked` | str、enum、bool、bool | `B`+`share_target` | `B` | `N1` | `L6M` | FR-E5、§12.8 | 分享率、分享带来新增 |
| `report_link_copy` | 复制分享短链 | `report_id`、`link_type` | str、enum | `B` | `B` | `N1`；只记链接类型，**禁止上报短链原文（含 trace 参数）** | `L6M` | FR-E5 | 分享率（补充口径） |
| `report_privacy_toggle` | SC-17 打码/隐私提示切换 | `report_id`、`masked_on` | str、bool | `B` | `B` | `N1` | `L6M` | FR-E5 | 隐私打码使用率 |
| `report_regenerate` | SC-19 重新生成报告 | `report_id`、`from` | str、enum | `B` | `B` | `N1` | `L6M` | FR-H2 | 重生成率、报告满意度代理 |

#### 17.3.5 会员与支付（18 个）

> **采集目的**：把 `paywall_view → paywall_cta_click → order_create → pay_success` 漏斗补全，并覆盖 iOS 分支、额度、退款与对账；支付标识只进交易库。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `paywall_view` | SC-20/SC-21 权益页可见 | `source`、`platform`、`is_member` | enum、enum、bool | `U`+`source`+`D` | `B` | `N1` | `L6M` | FR-J1、FR-J3 | 付费漏斗第一步 |
| `paywall_cta_click` | 点击「立即开通/续费」 | `platform`、`price_snapshot`、`refund_checked` | enum、int、bool | `U`+`paywall_view_id` | `B` | `N1`；`price_snapshot` 为运营参数，非个人信息；**iOS 端不产生该事件**（AS-21） | `L6M` | FR-J1、AS-21 | 付费漏斗第二步 |
| `refund_notice_view` | SC-20 退款告知可见/展开 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-J4、CG17、AS-35 | 退款告知触达率 |
| `refund_notice_agree` | 勾选退款告知 | `order_draft_id` | str | `B` | `C`（随订单落库留痕） | `N1` | `L3Y` | FR-J4、CG17、AS-35 | 电商法明示义务举证 |
| `refund_policy_view` | SC-22 退款政策全文页可见 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-J4、CG17 | 政策阅读率 |
| `price_fetch_fail` | 商品配置拉取失败 | `source`、`error_code`、`retry_no` | enum、str、int | `U/D`+`error_code` | `B` | `N1` | `L6M` | FR-B4、FR-K8、§12.3 | 改价可用性、配置故障告警 |
| `ios_paywall_notice_view` | SC-21 iOS 说明文案可见 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-J1、AS-21、D-09 | iOS 验收项「说明文案出现」 |
| `benefit_detail_click` | SC-21 权益细节点击 | `benefit_id`、`platform` | enum、enum | `U/E/D` | `B` | `N1` | `L6M` | FR-J1 | 权益关注度 |
| `order_create` | 创建订单成功 | `order_id`、`product_id`、`amount_micro`、`platform`、`out_trade_no` | str、str、int、enum、str | `B` | `D` | `N1`；**禁止上报支付账号与 openid 明文** | `L3Y` | FR-J2、NFR-9.5 | 付费漏斗第三步、下单成功率 |
| `pay_success` | 支付成功回调确认 | `order_id`、`transaction_id`、`amount_micro`、`pay_channel` | str、str、int、enum | `B` | `D` | `N1`；`transaction_id` **不得进分析库**，仅交易库 | `L3Y` | FR-J2、§8.5 | 付费转化率分子（AS-01） |
| `pay_fail` | 支付失败 | `order_id`、`fail_code`、`fail_stage` | str、str、enum | `B` | `D` | `N1` | `L6M` | FR-J2、NFR-9.4 | 支付失败率、失败原因分布 |
| `pay_confirming` | 回调未达，订单转「确认中」 | `order_id`、`pending_since` | str、int64 | `B` | `D` | `N1` | `L3Y` | FR-J2、§8.5 | 回调丢失率、T+1 兜底触发量 |
| `pay_pending_view` | SC-22「支付确认中」页可见 | `order_id` | str | `U`+`order_id` | `B` | `N1` | `L6M` | FR-J2 | 确认中态触达 |
| `order_retry` | 支付重试 | `order_id`、`retry_no` | str、int | `B`+`retry_no` | `B` | `N1` | `L6M` | FR-J2、NFR-8.4 | 支付重试率 |
| `order_list_view` | SC-23 订单记录可见 | `order_count`、`is_member` | int、bool | `U/D` | `B` | `N1` | `L6M` | FR-I1 | 订单查询渗透 |
| `refund_result` | 退款结果落定 | `order_id`、`refund_status`、`refund_amount_micro`、`refund_at` | str、enum、int、int64 | `B` | `C`（交易留痕） | `N1` | `L3Y` | FR-J4、CG17、§9.4 排除规则 | 付费转化率排除项 —— **未决策，不得开发**（见 §17.9.2） |
| `member_card_click` | SC-23 会员卡点击 | `is_member`、`source` | bool、enum | `U/D` | `B` | `N1` | `L6M` | FR-I1 | 会员入口二次转化 |
| `reconcile_diff` | T+1 对账发现差异 | `biz_date`、`diff_count`、`diff_amount_micro`、`handled` | str、int、int、bool | `B` | `D`（差异 >0 即告警） | `N1` | `L3Y` | NFR-9.6、NFR-5.2、§8.5 | 对账差异告警 |

#### 17.3.6 反馈与举报（15 个）

> **采集目的**：度量反馈与举报的提交—回执—审核—处置—追溯全闭环，支撑 CG15/CG16 与内容质量指标；正文与截图一律不进埋点。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `history_view` | SC-18 历史列表可见 | `filter_used`、`list_type` | bool、enum | `U/D` | `B` | `N1` | `L6M` | FR-H1 | 历史使用率、留存回访 |
| `history_filter` | 切换筛选条件 | `filter_type`、`filter_value_enum` | enum、enum | `U/E/D` | `B` | `N2`；`filter_value_enum` 只允许档案哈希与类型枚举 | `L6M` | FR-H1 | 筛选使用率 |
| `history_load_more` | 分页加载下一页 | `page_no`、`result_count` | int、int | `U/D`+`page_no` | `B` | `N1` | `L6M` | FR-H1、NFR-9.2 | 深度浏览率 |
| `feedback_submit` | 提交反馈成功 | `feedback_id`、`linked_session`、`linked_report`、`char_len` | str、bool、bool、int | `B` | `C`（回执编号同源） | `N3`；**反馈正文不得进分析库**，只上报长度与关联类型 | `L6M` | FR-N1、FR-K4 | 反馈量、反馈响应时效 |
| `feedback_image_upload` | 反馈附图上传 | `feedback_id`、`image_count`、`audit_status` | str、int、enum | `B` | `C` | `N3`；**禁止上报图片 URL、签名链接与内容安全回调原文** | `L6M` | FR-N1、NFR-1.1、CG5 | 附图率、审核中态 |
| `feedback_history_click` | SC-23 反馈记录入口点击 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-I1 | 反馈闭环触达 |
| `feedback_reply` | 后台回复反馈（PA-06） | `feedback_id`、`operator_role`、`reply_template_id` | str、enum、str | `B` | `C` | `N3`；`operator_role` 只记角色，**禁记人名** | `L3Y` | FR-K4 | 反馈响应时效 |
| `content_report` | 举报入口/详情可见（SC-16/SC-19） | `report_id`、`source_page` | str、enum | `U`+`report_id` | `B` | `N1` | `L6M` | FR-O1 | 举报漏斗第一步（**不与提交事件相加**） |
| `content_report_submit` | 提交举报成功 | `report_no`、`category`、`involves_minor`、`char_len` | str、enum、bool、int | `B` | `C` | `N3`；正文与截图不进埋点；`involves_minor` 不得进分析库 | `L3Y` | FR-O1、FR-O2、CG15/CG16 | 举报量、分类分布、涉未成年人 SLA |
| `report_receipt_view` | 受理回执/编号可见 | `report_no` | str | `U`+`report_no` | `B` | `N1` | `L6M` | FR-O1 | 回执触达率 |
| `ugc_review_status_view` | 举报/反馈审核状态查看 | `report_no`、`status` | str、enum | `U`+`report_no` | `B` | `N3` | `L6M` | FR-O1 | 处置透明率 |
| `report_dispose` | 后台举报处置（PA-06） | `report_no`、`category`、`action`、`involves_minor`、`sla_met` | str、enum、enum、bool、bool | `B` | `C` | `N3` | `L3Y` | FR-O2、FR-K5、CG15 | 举报处置闭环率、涉未成年人 SLA 达标 |
| `content_removal` | 内容下架处置 | `object_type`、`object_id`、`level`、`kb_id` | enum、str、enum、str | `B` | `C` | `N2` | `L3Y` | FR-K6、§8.10、R-5 | 追溯处置闭环率分母 |
| `content_trace_dispose` | 按 `kb_id` 反查受影响内容的处置完成 | `kb_id`、`level`、`affected_sessions`、`disposed_count`、`done_at` | str、enum、int、int、int64 | `B`+`level` | `C` | `N2` | `L3Y` | FR-K6、§8.10、§2.3 | 内容追溯处置闭环率（7 日 / 100%） |
| `content_audit_result` | 平台内容安全送检结果返回 | `object_type`、`audit_result`、`quota_exceeded`、`action` | enum、enum、bool、enum | `B` | `D`（超配额必须告警且不得放行） | `N2`；不记送检内容原文，只记结果与动作 | `L6M` | NFR-1.1、§11.5、CG5 | 送检超配额拦截率 |

#### 17.3.7 后台与配置（31 个）

> **采集目的**：为 NFR-7.4 的「敏感操作全部留痕」与 §13.3 的回滚能力提供审计数据；后台事件一律与业务同源落库（码 `C`），且不记人名与导出内容。

| 事件名 | 触发时机 | 必填字段 | 字段类型 | 是否去重 | 失败是否上报 | 隐私限制 | 保留期 | 对应 FR/NFR | 支撑的指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `admin_login_success` | 后台登录成功 | `admin_id_hash`、`role`、`mfa_used`、`ip_segment`、`device_type` | str、enum、bool、str、enum | `B` | `C` | `N1`；`ip_segment` 只记 /24 网段，**禁完整 IP 与设备指纹** | `L3Y` | NFR-7.4、NFR-7.1 | 后台登录审计 |
| `admin_login_fail` | 后台登录失败 | `admin_id_attempt_hash`、`fail_reason`、`ip_segment`、`fail_count` | str、enum、str、int | `—` | `C` | `N1` | `L6M` | NFR-7.1、NFR-7.4 | 暴力破解监控 |
| `kb_edit` | 知识库条目编辑保存 | `kb_id`、`changed_fields[]`、`version` | str、enum[]、int | `B` | `C` | `N1` | `L3Y` | FR-K1、NFR-7.4 | 编辑留痕完整性 |
| `kb_submit_review` | 提交专家审核 | `kb_id`、`version`、`submitter_role` | str、int、enum | `B` | `C` | `N2` | `L3Y` | FR-K1、NFR-9.10 | 审核工单时效 |
| `kb_review` | 审核结果落定 | `kb_id`、`version`、`result`、`reviewer_role`、`reject_reason_code` | str、int、enum、enum、enum | `B` | `C` | `N2`；`reject_reason_code` 只记枚举，**禁自由文本** | `L3Y` | FR-K1、NFR-9.10 | 审核通过率、抽检合格率 |
| `kb_publish` | 条目上架生效 | `kb_id`、`version`、`reason_code` | str、int、enum | `B`+`version` | `C` | `N2` | `L3Y` | FR-K1 | 知识库状态流转、上架时效 |
| `kb_unpublish` | 条目下架生效 | `kb_id`、`version`、`reason_code` | str、int、enum | `B`+`version` | `C` | `N2` | `L3Y` | FR-K1、§13.3 | 下架量与原因分布 |
| `kb_rollback` | 版本回滚生效 | `kb_id`、`from_version`、`to_version`、`trigger` | str、int、int、enum | `B` | `C` | `N2` | `L3Y` | FR-K1、§13.3、§8.10 | 回滚次数、追溯处置触发 |
| `kb_sample_check` | 抽检任务执行 | `kb_id`、`batch_id`、`result`、`checker_role` | str、str、enum、enum | `B`+`batch_id` | `C` | `N2` | `L3Y` | NFR-9.10、Q-40/Q-41 | 抽检合格率分母（G-6） |
| `term_create` | 词库条目新增 | `term_id_hash`、`lexicon_type`、`strategy`、`threshold_band` | str、enum、enum、enum | `B` | `C` | `N3`；**禁止上报词条原文**，只记哈希与类型 | `L3Y` | FR-K2、NFR-7.4 | 词库变更留痕 |
| `term_update` | 词库条目更新 | `term_id_hash`、`lexicon_type`、`changed_fields[]`、`version` | str、enum、enum[]、int | `B`+`version` | `C` | `N3` | `L3Y` | FR-K2 | 命中率变化归因 |
| `term_disable` | 词库条目停用 | `term_id_hash`、`lexicon_type`、`reason_code` | str、enum、enum | `B` | `C` | `N3` | `L3Y` | FR-K2、NFR-9.9 | 误报治理可追溯性 |
| `risk_threshold_change` | 预警阈值变更 | `level`、`from_band`、`to_band`、`operator_role` | enum、enum、enum、enum | `B`+`version` | `C` | `N3` | `L3Y` | FR-K2、Q-12、D-06 | 召回/误报变化的归因 |
| `risk_event_review` | 高风险事件值班复核 | `risk_event_no`、`review_result`、`elapsed_hours`、`sla_met`、`reviewer_role` | str、enum、int、bool、enum | `B` | `C` | `N3` | `L3Y` | FR-L6、NFR-9.9、PA-07 | 复核闭环率 |
| `risk_event_escalate` | 高风险事件上报 | `risk_event_no`、`escalated`、`escalate_at` | str、bool、int64 | `B` | `C` | `N3`；`escalate_target` **未决策，不得开发**（见 §17.9.2） | `L3Y` | FR-L6、CG9、Q-43 | 强制报告留痕 |
| `log_export` | 后台日志导出 | `admin_id_hash`、`scope`、`row_count`、`format` | str、enum、int、enum | `B` | `C` | `N1`；**导出内容本身不得进埋点** | `L3Y` | NFR-7.4 | 敏感操作留痕、泄露追溯 |
| `privacy_request_handle` | 后台处理权利请求 | `request_no`、`request_type`、`action`、`reject_reason_code`、`elapsed_hours` | str、enum、enum、enum、int | `B` | `C` | `N1`；拒绝理由只记枚举 | `L3Y` | FR-K7、CG7、Q-44 | 权利请求 SLA 达标率 |
| `rights_center_view` | SC-25 权利中心可见 | `is_member` | bool | `U/D` | `B` | `N1` | `L6M` | FR-I3、CG7 | 权利入口触达率 |
| `rights_center_click` | SC-23 权利中心入口点击 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-I1、FR-I3 | 入口点击率 |
| `rights_request_submit` | 提交权利请求 | `request_no`、`request_type`、`delivery_method` | str、enum、enum | `B` | `C` | `N1`；`delivery_method` **未决策，不得开发**（见 §17.9.2） | `L3Y` | FR-I3、CG7、Q-44 | 权利请求量与类型分布 |
| `rights_export_start` | 导出任务开始 | `request_no`、`format`、`delivery` | str、enum、enum | `B` | `C` | `N1`；`delivery` **未决策，不得开发** | `L3Y` | FR-I3、Q-44 | 导出成功率分母 |
| `rights_export_fail` | 导出失败 | `request_no`、`fail_code`、`retry_no` | str、str、int | `B`+`retry_no` | `C` | `N1` | `L3Y` | FR-I3 | 导出失败率 |
| `rights_request_status_view` | 查看请求状态 | `request_no`、`status` | str、enum | `U`+`request_no` | `B` | `N1` | `L6M` | FR-I3 | 状态可查率 |
| `account_security_view` | SC-24 账号与安全可见 | `is_member` | bool | `U/D` | `B` | `N1` | `L6M` | FR-I2 | 账号安全触达率 |
| `account_security_click` | SC-23 账号与安全入口点击 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-I1、FR-I2 | 账号安全渗透率 |
| `permission_setting_click` | 权限管理项点击 | `permission_type`、`state` | enum、enum | `U/E/D` | `B` | `N1`；只记权限类型与开关态，**禁系统权限详情** | `L6M` | FR-I2、FR-A4 | 权限前置说明效果 |
| `child_rule_click` | 儿童个人信息处理规则入口点击 | `source` | enum | `U/D` | `B` | `N1` | `L6M` | FR-A5、CG3 | 专门文本触达率（合规举证） |
| `account_delete_start` | 注销流程开始 | `entry`、`warn_shown` | enum、bool | `U/D` | `B` | `N1` | `L6M` | FR-I2、CG7 | 注销漏斗分母 |
| `account_delete_confirm` | 注销二次确认完成 | `user_id_hash`、`delete_scope` | str、enum | `—` | `C` | `N3`；`retention_plan` **未决策，不得开发**（见 §17.9.2） | `L3Y` | FR-I2、CG7、Q-28 | 注销完成率、注销举证 |
| `config_change` | 系统开关/价格/文案/渠道变更生效 | `config_id`、`config_type`、`from_version`、`to_version`、`operator_role`、`price_micro` | str、enum、str、str、enum、int | `B`+`to_version` | `C` | `N1`；价格金额为运营参数可记；**禁记变更理由自由文本** | `L3Y` | FR-K8、FR-B4、NFR-7.4 | 变更留痕、价格故障归因 |
| `config_rollback` | 配置回滚生效 | `config_id`、`from_version`、`to_version`、`rollback_reason_code` | str、str、str、enum | `B`+`to_version` | `C` | `N1` | `L3Y` | FR-K8、§13.3 | 回滚次数与 MTTR |

### 17.4 新增事件登记（UI 文档来源）

> 共 **69 行**（对应 UI 文档出现、§9.3 未登记的事件名）；其中 1 行为别名归并（`consent_withdraw_start`），**净新增事件 68 个**。「不上报的后果」一律写成该指标无法计算的具体后果。

| 事件名 | 来源（UI 页） | 采集目的 | 不上报的后果（指标无法计算） |
| --- | --- | --- | --- |
| `profile_form_view` | SC-04 | 建档表单到达 | 无法区分「打开表单」与「提交成功」，建档流失点无法定位 |
| `profile_save` | SC-04 | 保存成功与变更字段 | 建档成功率无分子；留存 cohort 无法按「已建档」分层 |
| `pet_form_view` | SC-05 | 宠物表单到达 | 宠物模块渗透漏斗断裂，G-1「两大模块可用」不可度量 |
| `pet_save` | SC-05 | 宠物档案保存 | 宠物模块渗透率无分子，F 模块使用度不可度量 |
| `profile_delete_cascade` | SC-07 | 级联删除影响面 | 级联删除影响面不可举证，FR-C4 验收 5 无数据 |
| `collab_agent_expand` | SC-10 | 协同透明度使用 | FR-G3 使用率不可度量，多 Agent 价值验证缺证据 |
| `content_report_submit` | SC-11 / SC-26 | 举报提交与分类 | 举报量、分类分布与 SLA 无分子，CG15 与 FR-O2 不可举证 |
| `crisis_channel_call` | SC-12 | 危机渠道一键拨号 | 渠道触达率不可算，G-4「引导触达」缺可埋点证据（C2 要求） |
| `crisis_channel_copy` | SC-12 | 复制渠道信息 | 拨号失败时的替代触达无口径，渠道有效性不可评估 |
| `risk_appeal_submit` | SC-13（别名 `qa_risk_appeal`＝SC-12） | 误报申诉提交 | 申诉量缺失，§9.4 离线表「申诉闭环率」分母不可算 |
| `risk_appeal_allow` | SC-13 | 申诉放行标记 | 「申诉后继续提问率」无数据，FR-L4 效果不可评估 |
| `risk_block_leave` | SC-13 | 拦截后离开 | 高危拦截后离开率分子缺失，G-4 与 AS-01 目标不可验证（C3 缺口） |
| `assessment_intro_view` | SC-14 | 测评引导页到达 | G-2「测评入口点击率」分母缺失（C8 缺口） |
| `assessment_exit_before_start` | SC-14 | 未开始即离开 | 引导页流失率不可算，完成率偏低的原因无法归因 |
| `report_privacy_toggle` | SC-17 | 分享前打码开关 | FR-E5 隐私打码使用率不可度量 |
| `history_filter` | SC-18 | 筛选条件使用 | FR-H1 筛选可用性无数据，历史检索效率不可评估 |
| `history_load_more` | SC-18 | 分页加载 | 深度浏览率不可算，内容价值评估缺证据 |
| `report_regenerate` | SC-19 | 重新生成报告 | 报告满意度代理指标缺失，FR-H2 效果不可评估 |
| `paywall_cta_click` | SC-20 | 购买 CTA 点击 | 付费漏斗中间态缺失，`paywall_view → order_create` 断点不可定位 |
| `refund_notice_view` | SC-20 | 退款告知可见 | CG17/AS-35 明示义务举证链不完整 |
| `refund_notice_agree` | SC-20 | 退款告知勾选 | CG17/AS-35 留痕缺失，退款争议不可举证 |
| `price_fetch_fail` | SC-20 | 商品配置拉取失败 | 改价可用性不可观测，价格配置故障无告警 |
| `ios_paywall_notice_view` | SC-21 | iOS 说明文案可见 | AS-21/D-09 的 iOS 验收项「说明文案出现」无法验收 |
| `quota_exhausted_view` | SC-21 | 额度用尽态可见 | 额度闸门转化率无分子，FR-J3 效果不可度量 |
| `benefit_detail_click` | SC-21 | 权益细节点击 | 权益关注度不可算，权益文案优化无依据 |
| `pay_pending_view` | SC-22 | 支付确认中态可见 | 回调丢失的用户侧体验不可观测，§8.5 兜底效果不可评估 |
| `order_retry` | SC-22 | 支付重试 | 支付重试率不可算，NFR-8.4 幂等重试不可验证 |
| `order_list_view` | SC-23 | 订单记录可见 | 订单查询渗透与售后入口触达不可度量 |
| `refund_policy_view` | SC-22 | 退款政策全文阅读 | 退款政策触达率不可算，CG17 明示义务举证弱化 |
| `profile_center_view` | SC-23 | 个人中心可见 | 个人中心渗透率不可算，FR-I1 聚合入口价值不可评估 |
| `member_card_click` | SC-23 | 会员卡点击 | 会员入口二次转化路径不可观测 |
| `rights_center_click` | SC-23 | 权利中心入口点击 | FR-I3 入口触达率不可算 |
| `child_rule_click` | SC-23 | 儿童规则入口点击 | CG3 专门文本触达率不可算，合规举证缺项 |
| `account_security_click` | SC-23 | 账号与安全入口点击 | 账号安全功能渗透率不可度量 |
| `feedback_history_click` | SC-23 | 反馈记录入口点击 | 反馈闭环触达不可度量，FR-K4 效果不可评估 |
| `account_security_view` | SC-24 | 账号与安全页可见 | 账号安全触达率不可算，FR-I2 无数据 |
| `permission_setting_click` | SC-24 | 权限管理项点击 | FR-A4 权限前置说明效果不可度量 |
| `consent_withdraw_start` | SC-24（＝§9.3 `consent_withdraw` 的别名，**不新增事件**） | 撤回流程开始 | 撤回漏斗分母缺失，FR-A6 不可度量 |
| `consent_withdraw_done` | SC-24 | 撤回完成 | 撤回完成率无分子，CG7 举证不完整 |
| `account_delete_start` | SC-24 | 注销流程开始 | 注销漏斗分母缺失，FR-I2 不可度量 |
| `account_delete_confirm` | SC-24 | 注销二次确认完成 | 注销完成率无分子，CG7 与 FR-I2 举证缺失 |
| `rights_center_view` | SC-25 | 权利中心可见 | FR-I3 触达率不可算 |
| `rights_request_submit` | SC-25 | 权利请求提交 | 权利请求量与类型分布无数据，CG7 不可举证 |
| `rights_export_start` | SC-25 | 导出任务开始 | 导出成功率分母缺失，Q-44 SLA 不可评估 |
| `rights_export_fail` | SC-25 | 导出失败 | 导出失败率不可算，导出交付方式优劣不可比较 |
| `rights_request_status_view` | SC-25 | 请求状态查看 | 状态可查率不可算，FR-I3「每项显示处理时限」不可验收 |
| `feedback_image_upload` | SC-26 | 反馈附图上传 | 附图率与审核中态不可观测，NFR-1.1 图片送检不可验证 |
| `report_receipt_view` | SC-26 | 受理回执可见 | 回执触达率不可算，FR-O1 效果不可评估 |
| `ugc_review_status_view` | SC-26 | 审核状态查看 | 处置透明率不可算，FR-O1「处置时限可见」不可验收 |
| `admin_login_success` | PA-01 | 后台登录成功审计 | NFR-7.4 后台登录留痕缺失，权限审计不可举证 |
| `admin_login_fail` | PA-01 | 登录失败审计 | NFR-7.1 暴力破解监控缺失 |
| `kb_publish` | PA-02 | 知识库上架 | 知识库状态流转与上架时效不可度量 |
| `kb_unpublish` | PA-02 | 知识库下架 | 下架量与原因不可统计，§13.3 回滚效果不可评估 |
| `kb_sample_check` | PA-02 | 抽检任务执行 | G-6/NFR-9.10 抽检合格率分母缺失（C8 缺口） |
| `kb_edit` | PA-03 | 条目编辑留痕 | 编辑留痕不完整，NFR-7.4 敏感操作留痕缺失 |
| `kb_submit_review` | PA-03 | 提交专家审核 | 审核工单时效不可算，NFR-9.10 不可验证 |
| `kb_rollback` | PA-03 | 版本回滚 | 回滚次数与内容追溯触发不可统计（§13.3） |
| `term_create` | PA-04 | 词库新增 | FR-K2 变更留痕缺失，词库来源不可审计 |
| `term_update` | PA-04 | 词库更新 | 命中率变化无法归因到具体词条变更 |
| `term_disable` | PA-04 | 词库停用 | 误报治理动作不可追溯，NFR-9.9 闭环缺证据 |
| `risk_threshold_change` | PA-04 | 预警阈值变更 | 召回率/误报率变化无法归因到阈值调整，C2 双阈值验收不可复现 |
| `log_export` | PA-05 | 日志导出留痕 | NFR-7.4「导出留痕」缺失，数据泄露追溯断链 |
| `feedback_reply` | PA-06 | 后台回复反馈 | Q-26 响应时效不可算，FR-K4 效果不可评估 |
| `report_dispose` | PA-06 | 举报处置 | FR-O2/CG15 处置闭环率不可算 |
| `risk_event_review` | PA-07 | 高风险事件复核 | NFR-9.9 复核闭环率不可算 |
| `risk_event_escalate` | PA-07 | 高风险事件上报 | CG9/FR-L6 强制报告留痕缺失（字段级未决策） |
| `privacy_request_handle` | PA-08 | 权利请求处理 | FR-K7/CG7 的 SLA 达标率不可算 |
| `config_change` | PA-08 | 配置变更留痕 | FR-K8 变更留痕缺失，价格/开关故障不可归因 |
| `config_rollback` | PA-08 | 配置回滚 | §13.3 一键回滚效果与 MTTR 不可度量 |

### 17.5 口径缺口补登记事件

> 共 **9 个**。这些事件在 UI 文档中没有对应页面行，来源是 §9.4 的分子分母口径与 NFR 告警阈值；**不补则对应指标恒为不可算**。

| 事件名 | 缺口来源 | 为什么必须补 | 不上报的后果 |
| --- | --- | --- | --- |
| `refund_result` | §9.4 付费转化率「排除退款用户」＋FR-J4＋CG17 | 无退款结果事件，退款用户无法从分子中剔除 | 付费转化率被高估，D-01/AS-01 目标失真 |
| `qa_cost` | §9.4 单位问答成本＋NFR-6.1/6.3＋§7.13 | 无 token 与费用落账事件，成本只能事后估算 | 单位问答成本护栏失效，毛利测算（§12.7）无输入 |
| `agent_call` | NFR-5.2（失败率 >3%、超时率 >5% 告警）＋§7.7 | `qa_degraded` 只覆盖整体降级，无 per-Agent 结果 | Agent 失败率/超时率告警不可配置，降级无法提前发现 |
| `output_filter_hit` | §7.7 阶段 8＋NFR-1.1＋NFR-9.8 | 输出侧过滤命中无埋点 | 违规词命中率（G-6，目标 0）不可算 |
| `entry_exposure` | 审核意见 §3.7「入口曝光未命中」＋C8 | 只有点击没有曝光，点击率分母只能借用 `home_view` | 入口点击率分母错误，入口排序（AS-07）无法评估 |
| `content_trace_dispose` | §2.3 内容追溯处置闭环率（7 日/100%）＋FR-K6＋§8.10 | `content_removal` 只记处置动作，不记受影响内容处置完成 | 追溯处置闭环率不可算，R-5 与 A11 无法闭环 |
| `risk_appeal_review` | §9.4 申诉闭环率（24h/100%）＋线上误报率＋FR-L4 | 只有申诉提交，没有复核完成与耗时 | 申诉闭环率与线上误报率均不可算，NFR-9.9 不可验证 |
| `reconcile_diff` | NFR-5.2（对账差异 >0 告警）＋NFR-9.6＋§8.5 | 对账差异只落财务表，未形成可告警事件 | 对账差异告警不可配置，支付异常只能人工发现 |
| `content_audit_result` | NFR-1.1（超配额不得放行）＋§11.5＋CG5 | 平台内容安全送检结果无埋点 | 「超配额拒绝」不可验证，上线前置检查表第 7 项无证据 |

### 17.6 指标 → 埋点 反查表

#### 17.6.1 §9.4 线上指标表

| 指标（§9.4） | 分子 / 分母口径 | 依赖事件 | 去重维度 | 是否存在缺口 | 补哪个事件 / 字段 |
| --- | --- | --- | --- | --- | --- |
| 新用户 7 日留存 | D+7 有任意事件的用户 / D 日新增用户（cohort＝自然日） | `app_launch` + 全事件（供 join） | `user_id` | 无（口径级） | 补字段规则：`is_new_user` 固定为「该 `user_id` 首次 `app_launch`」 |
| 测评完成率 | `assessment_complete` 用户数 / `assessment_start` 用户数（排除 7 日内重复） | `assessment_start`、`assessment_complete` | `user_id` | 无（口径级） | 固化「进入测评」＝`assessment_start`，**不得**改用 `assessment_intro_view` |
| 问答二次提问率 | 有 `qa_followup` 的会话数 / 有 `qa_submit` 的会话数（排除 `is_retry=true`、排除被拦截会话） | `qa_submit`、`qa_followup`、`qa_risk_block`（排除用） | `session_id` | 无 | 补字段：`qa_followup.parent_request_id` |
| 付费转化率 | 首次 `pay_success` 用户数 / 同期新增用户数（排除退款用户） | `pay_success`、`app_launch`、`refund_result` | `user_id` | **有** | 补 `refund_result` |
| 高危拦截后离开率 | 拦截后无继续追问的会话数 / 拦截会话数 | `qa_risk_block`、`qa_risk_block_followup`、`risk_block_leave` | `session_id` | 无（**双计风险**） | 口径固化：只取 `qa_risk_block_followup`；`risk_block_leave` 必须同写该事件 |
| 冲突标注率 | 含冲突标注的回答数 / 多 Agent 协同回答数（`agent_count ≥ 2`） | `qa_result_view` | `session_id` | 无 | 补字段：`agent_count`、`is_conflict` 置为必填 |
| 单位问答成本 | 周期内模型费用 / 周期内问答数（含缓存命中为 0 的请求） | `qa_cost`、`qa_submit` | 请求（`client_request_id`） | **有** | 补 `qa_cost` |
| P95 响应时长 | 分位数，无分子分母；按单领域/复合/灰区分别统计 | `qa_result_view` | 请求 | **有**（字段级） | 补字段：`request_type`、`first_packet_ms`、`gray_triggered` |
| 召回率（离线） | 标注集被拦截高危样本数 / 标注集高危样本总数（≥95%） | 离线标注任务 + `qa_risk_block.level`/`score_band` | 样本 | 无 | 无需新事件（线上事件仅用于回放比对） |
| 误报率（离线） | 标注集被误拦正常样本数 / 标注集正常样本总数（≤5%） | 离线标注任务 + `risk_appeal_submit`、`risk_appeal_review` | 样本 | **有** | 补 `risk_appeal_review` |
| 命中后正文为空率 | 命中且响应体正文为空的请求数 / 命中请求数（100%） | `qa_risk_block` | 请求 | **有**（字段级） | 补字段：`body_emitted`、`response_bytes` |
| 申诉闭环率 | 24h 内完成复核的申诉数 / 申诉总数（100%） | `risk_appeal_submit`、`risk_appeal_review` | 申诉号 | **有** | 补 `risk_appeal_review`（含 `elapsed_hours`、`sla_met`） |

#### 17.6.2 §2.3 / §12.8 / §13.2 / NFR 要求但 §9.4 未列口径的指标

| 指标 | 分子 / 分母口径 | 依赖事件 | 是否存在缺口 | 补哪个事件 / 字段 |
| --- | --- | --- | --- | --- |
| 内容追溯处置闭环率（7 日/100%，§2.3） | `content_trace_dispose` 完成数 / `content_removal` 触发数 | `content_removal`、`content_trace_dispose` | **有** | 补 `content_trace_dispose` |
| 测评入口点击率（G-2） | `entry_click(entry_type=assessment)` 去重用户 / `entry_exposure(entry_type=assessment)` 去重用户 | `entry_click`、`entry_exposure`、`assessment_intro_view` | **有** | 补 `entry_exposure`（备用分母 `home_view`，须标注口径差异） |
| 调度正确率（G-3） | 期望 Agent 集合与线上 `agent_ids` 一致的样本数 / 评测样本数 | `qa_result_view`、`agent_call` | **有**（字段级） | 补字段：`agent_ids[]`（集合比对，不能用 `agent_count` 代替） |
| 知识库抽检合格率（G-6） | `kb_sample_check.pass=true` 数 / `kb_sample_check` 总数 | `kb_sample_check`、`kb_review` | 无（判定规则未决策） | 无需新事件；`pass` 判定规则见 §17.9.2 |
| 违规词命中率（G-6） | `output_filter_hit(action=block/rewrite)` 数 / 抽检回答数（目标 0） | `output_filter_hit` | **有** | 补 `output_filter_hit` |
| Agent 失败率 / 超时率（NFR-5.2） | `agent_call(status=fail/timeout)` 数 / `agent_call` 总数（失败 >3%、超时 >5% 告警） | `agent_call` | **有** | 补 `agent_call` |
| 对账差异（NFR-5.2 / NFR-9.6） | `reconcile_diff.diff_count > 0` 即告警；差异金额合计 | `reconcile_diff` | **有** | 补 `reconcile_diff` |
| 送检超配额拦截率（NFR-1.1） | `content_audit_result(quota_exceeded=true, action=reject)` 数 / 送检总数 | `content_audit_result` | **有** | 补 `content_audit_result` |
| 分享率与分享带来新增（§12.8） | `report_share` + `report_link_copy` 去重用户 / `report_view` 去重用户；新增归因＝`app_launch.share_trace_id` | `report_share`、`report_link_copy`、`app_launch` | **有**（字段级） | 补字段：`app_launch.share_trace_id`（无此字段则分享新增只能归入自然新增） |
| 免责拒绝放弃率 | `disclaimer_decline` 去重用户 / `disclaimer_show` 去重用户 | `disclaimer_show`、`disclaimer_decline` | 无事件缺口（§9.4 未列口径） | 无需新事件；口径需补入 §9.4 |
| 危机渠道触达率 | `crisis_channel_call`（`copy` 为备用）/ `qa_risk_block` 命中会话数 | `crisis_channel_call`、`crisis_channel_copy` | 无 | — |
| 举报处置闭环率 | `report_dispose(sla_met=true)` 数 / `content_report_submit` 数 | `content_report_submit`、`report_dispose` | 无 | — |
| 知识库审核工单时效（NFR-9.10） | `kb_review.ts_server − kb_submit_review.ts_server` 的时长分布 | `kb_submit_review`、`kb_review` | 无（评分标准未决策） | 无需新事件；评分与合格线见 §17.9.2 |
| 后台登录审计与越权（NFR-7.x） | `admin_login_fail` 连续失败计数；`log_export` 异常范围告警 | `admin_login_success`、`admin_login_fail`、`log_export` | 无 | — |
| 免费额度用尽率（FR-J3） | `quota_exhausted` 去重用户 / `qa_submit` 去重用户 | `quota_exhausted`、`qa_submit` | 无 | — |
| 支付漏斗转化（FR-J2） | `paywall_view` → `paywall_cta_click` → `order_create` → `pay_success` 各步去重用户 | 四个事件 | 无 | 无需新事件（中间态已补齐） |

**缺口小结**：共识别 **14 处**缺口 —— **10 处**需新增事件（归并后 **9 个**）、**4 处**仅需补字段或固化口径。

### 17.7 数据保留与合规

#### 17.7.1 保留期映射（与 §9.1、§11.7、AS-25 一致）

| 事件族 | 保留期 | 依据 | 最短必要策略 |
| --- | --- | --- | --- |
| 网络与操作类（`app_launch`、`home_view`、`entry_*`、`*_view`、`*_click`、`history_*`、`report_*`） | ≥6 个月 | §11.7 网络与操作日志 | 明细 90 天后**只留聚合**（日 × 事件 × 入口 × `is_member` × `is_new_user`），删除 `session_id` 与 `user_id` |
| 交易类（`order_create`、`pay_success`、`pay_fail`、`pay_confirming`、`refund_*`、`reconcile_diff`、`refund_notice_agree`） | ≥3 年 | §11.7 交易与订单信息 | 明细全留但**分离存储**：`transaction_id` 只进交易库，**不进分析库、不进埋点报表** |
| 合规留档类（`disclaimer_*`、`consent_*`、`profile_delete_confirm`、`qa_risk_block`、`risk_appeal_*`、`risk_event_*`、`crisis_channel_*`、`content_report_submit`、`report_dispose`、`rights_*`、`account_delete_confirm`） | ≥3 年 | §11.7 合规留档（CG6） | 原文全不留：只留编号 + `level`/`score_band`/枚举；`desc_len` 与 `char_len` 代替正文 |
| 安全指标类（`agent_call`、`qa_cost`、`qa_risk_block_followup`、`entry_exposure`） | 聚合长期 / 明细 ≥6 个月 | §11.7 + §9.4 趋势监控 | 明细 90 天后只留日聚合（per-Agent 成功率、日均 token、日均离开率） |
| 额度用量类（`quota_exhausted`） | ≥1 年 | §9.1 免费额度用量 | 只留 `user_id` + 日期 + 次数，不留 `limit_snapshot` 历史值 |
| 内容与配置留痕类（`kb_*`、`term_*`、`config_*`、`risk_threshold_change`、`log_export`、`admin_login_*`、`privacy_request_handle`） | ≥3 年 | §9.1 配置版本表 / NFR-7.4 / §11.7 | `term_*` 只留哈希；`log_export` 只留导出元数据，不留导出内容 |
| 其他个人信息类（`profile_*`、`pet_save`、`assessment_*`、`feedback_*`） | 账号存续期（断点 90 天；档案注销后 30 天删除） | §9.1、§11.7、FR-C4 | 档案事件只留 `profile_id_hash` + `age_band` + 字段位图；测评只留 `type_code` 与维度档 |
| 后台审计登录（`admin_login_success`/`admin_login_fail`） | ≥6 个月（操作留痕建议 ≥3 年） | UI PA-01 自述 ≥6 个月 + NFR-7.4 | `ip_segment` 90 天后降为「是否同网段」布尔值 |

#### 17.7.2 最短必要（只留聚合不留明细）字段清单

| 只留聚合的字段 | 原因 |
| --- | --- |
| `client_request_id`、`session_id` | 仅用于 join 与去重；聚合完成后无独立价值，保留会形成超长明细表 |
| `agent_ids[]`、`failed_agent_ids[]` | 只用于集合比对与失败归因；长期只留 per-Agent 聚合计数 |
| `prompt_tokens`、`completion_tokens`、`cost_micro` | 长期只留 `model_id` × 日均 token × 均成本 |
| `profile_id_hash`、`pet_id_hash`、`admin_id_hash` | 单条明细长期无必要；只留「是否有档案」等派生布尔 |
| `desc_len`、`char_len`、`response_bytes` | 仅用于分布统计，长期保留分位值即可 |
| `stay_ms`、`delay_ms`、`elapsed_ms`、`duration_ms` | 长期保留分位数与均值，不保留逐条 |
| `ip_segment` | 90 天后只留「是否同网段」 |
| `appeal_id`、`risk_event_no`、`report_no`、`request_no`、`feedback_id` | 合规类只留编号索引，不留事件明细全字段 |

#### 17.7.3 出境与训练约束（CG8 / AS-29 / CG12）

1. **禁止出境**：本章全部事件的数据（含聚合）**不得传输至境外**，只允许境内已备案的埋点与分析服务（§9.5）。
2. **禁止训练**：埋点数据不得用于模型训练或微调（硬约束，§9.5 / CG12）。
3. **第三方 SDK**：分析 SDK 必须列入《第三方共享清单》并声明处理目的、字段、存储地、留存期（CG11）；新增 SDK 必须走上线前置检查表（§11.8 第 3 项）。
4. **自动清理**：留存期到期必须由定时任务自动删除或聚合化，删除动作留日志（§11.8 第 8 项）。

### 17.8 禁止采集清单

> 本节为**硬禁止**。任何事件 schema 中不允许出现下列字段；代码评审与埋点走查（UI 文档 §10.3 第 12 条）逐条核对。

| # | 禁止采集 | 禁止范围 | 依据 |
| --- | --- | --- | --- |
| 1 | 儿童可识别信息进分析库 | 昵称、出生日期、身高、体重、早产标记、过敏项、辅食月龄、头像/照片、`profile_id` 明文 | §9.1（P0 加密字段）、CG2/CG3、§17.3.2 只允许 `profile_id_hash` + `age_band` |
| 2 | 用户原文进第三方分析 | 提问文本、反馈正文、举报正文、申诉补充说明、测评逐题作答明细、宠物/儿童自由文本字段值 | §9.5、NFR-1.9、审核意见 §3.7 |
| 3 | 手机号进埋点参数 | 任何形式的 `phone`/`mobile`/`contact`，**含监护核验所用手机号** | CG13（最小化）、§9.1 用户实体 |
| 4 | 危机渠道目标号码 | 一键拨号的目标号码、热线完整号码、渠道名称自由文本、复制到剪贴板的内容 | FR-L3、§11.3；只允许 `channel_id` 枚举 |
| 5 | 支付敏感信息 | 微信 `openid`/`unionid` 明文、支付账号、支付凭证、签名；`transaction_id` 进分析库 | §9.2 加密字段清单、NFR-7.3 |
| 6 | 图片与音频本体 | 图片 URL、签名 URL、图片内容、ASR 转写原文、原始音频、内容安全回调原文 | §11.5、AS-28、审核意见 2.29 条 |
| 7 | 完整 IP 与设备指纹 | 完整 IP、IMEI/IDFA/OAID/MAC、通讯录、位置、剪贴板、相册内容 | NFR-1.9、CG13；只允许 /24 网段与 `device_type` 档位 |
| 8 | 命中词条原文 | 敏感词/高危词的具体词条文本、规则正则原文、`rule_hit` 的匹配片段 | FR-K2、CG5；只允许 `rule_hit_id` 与 `score_band` |
| 9 | 自由文本类运营字段 | 拒绝理由正文、审核意见正文、变更理由正文、回执正文 | §17.2.2 枚举字段规则；只允许 `*_reason_code` |
| 10 | 后台人员身份 | 管理员真实姓名、手机号、完整账号、后台导出内容、被导出数据行 | NFR-7.4；只允许 `admin_id_hash` 与 `operator_role` |
| 11 | 短链与场景原始串 | 分享短链全文（含 trace 参数）、`scene` 原始串、小程序路径原始串 | §17.2 命名规则；只允许白名单枚举与 `share_trace_id` |
| 12 | 未登记枚举值 | 任何枚举字段的未登记取值（含 `category_group`、`type_code` 等未决策值域） | §17.2.2；未登记一律上报 `unknown` 并计入 `schema_violation` |

### 17.9 三态标注汇总

#### 17.9.1 有默认方案，可开发但需记录风险

| 事项 | 默认方案（按此实现） | 上游编号 |
| --- | --- | --- |
| 入口枚举与排序（`entry_click`、`entry_exposure`） | 按 AS-07 默认排序（测评置顶），入口枚举固定为 4 入口 + 会员 + 测评 | AS-07、Q-30 |
| 预警阈值档位（`risk_threshold_change.from/to_band`） | 取 D-06 推荐双阈值（>0.8 拦截 / 0.5–0.8 拦截+引导 / <0.5 放行打标） | D-06、Q-12 |
| 成本口径（`qa_cost.cost_micro`） | 埋点只落 token 明细与 `model_id`，费用由离线单价表计算；单价表未定前不落 `cost_micro` 的绝对值 | NFR-6.3、§12.7、NFR-6.4 |
| 灰度与实验分流（`experiment_id`、`bucket`） | 按 AS-32 体验版邀请内测 + PA-08 按入口粒度灰度开关；`bucket` 用 `hash(user_id)%100` | AS-32、Q-30 |
| 价格快照（`paywall_cta_click.price_snapshot`） | 按 §12.3 单次购买不自动续费；iOS 端不产生该事件 | AS-21、D-09、Q-25 |
| 后台角色枚举（`admin_login_*`、`operator_role`、`reviewer_role`） | 取 NFR-7.4 四角色（超管/内容运营/客服/专家）为枚举值域 | NFR-7.4、Q-27、D-15 |
| 危机渠道枚举（`crisis_channel_call.channel_id`） | 取 `CRISIS_CHANNELS_V1` 文案 ID 的占位枚举（`police`/`minor_protection`/`psych_hotline`/`other`） | FR-L3、Q-42、CG9 |
| 反馈回执（`feedback_reply`） | 按 Q-26 默认不承诺时效，事件只记时长 | FR-K4、Q-26 |
| 测评文案与引导（`assessment_intro_view`） | 按 AS-14 放弃「科学测评」宣称后的文案边界实现 | AS-14、Q-09、D-03 |

#### 17.9.2 未决策，不得开发

> 以下事项**缺少决策即无法确定字段值域或触发时机**，仅允许在 schema 中**预留字段名**，不得实现上报逻辑。

| # | 事项 | 缺什么决策 | 上游编号 | 先行可做的部分 |
| --- | --- | --- | --- | --- |
| 1 | `risk_appeal_allow` 的触发时机与 `allow_mode` | 「申诉即放行」与「24h 复核后放行」是否并存 | Q-12、D-06、FR-L4（SC-13 自认口径冲突） | 可先开发 `risk_appeal_submit` 与 `risk_appeal_review` |
| 2 | `qa_risk_block.category_group` | 命中类别清单与分级粒度 | Q-12、D-06 | 可先上报 `level` 与 `score_band` |
| 3 | `rights_request_submit.delivery_method`、`rights_export_start.delivery`、SLA 数值字段 | 交付方式（邮件/本地）与答复时限 | Q-44、CG7、D7 | 可先开发 `rights_request_submit.request_type` 六类枚举 |
| 4 | `account_delete_confirm.retention_plan` | 注销后各实体处置范围与时限 | Q-28、FR-I2、CG7 | 可先开发 `account_delete_start`/`_confirm` 的漏斗字段 |
| 5 | `risk_event_escalate.escalate_target` | 是否负有强制报告义务、上报对象与流程 | Q-43、CG9、FR-L6 | 可先上报 `escalated` 与 `escalate_at` |
| 6 | `qa_submit.input_mode` 的 `voice` 取值 | 语音方案（服务商/方言/时长/落盘） | Q-18、AS-04、FR-D2（已移出 MVP） | MVP 只落 `text`，`voice` 不入值域 |
| 7 | `assessment_answer.dimension`、`assessment_complete.type_code` 值域 | 四象命名、维度定义与判定阈值 | Q-06/Q-08、AS-15/AS-16、D-02/D-04 | 可先开发 `assessment_start`/`_complete` 的耗时与题量字段 |
| 8 | `refund_result.refund_status`、`refund_amount_micro` | 退款政策、权益回收与驳回口径 | Q-25、CG17、AS-35、D-09 | 可先开发 `refund_notice_view`/`_agree`/`refund_policy_view` |
| 9 | `kb_sample_check.pass` 判定与合格线 | 抽检评分标准与合格线 | Q-41、NFR-9.10 | 可先开发 `kb_sample_check.result` 原始评分 |

#### 17.9.3 已决策，可开发（本章主体）

除 §17.9.1 与 §17.9.2 列明者外，§17.3 中 **119 个事件及其字段**均为 `已决策，可开发`，依据为 §9.3（事件登记）、§9.4（口径）、§11.7 + AS-25（留存）、§17.2（规范）。其中 9 个补登记事件（§17.5）的依据为 §9.4 与 NFR-5.2/NFR-9.6/NFR-1.1/NFR-6.x，属**口径必需项**，可与对应 FR 同批开发。

> **合稿后必须回填的位置**：① §9.3 增加「字段/类型/去重/失败上报/隐私/保留期」六列或指向本章；② §9.4 每条指标补「依赖事件」列；③ §12.8 增长指标补 `entry_exposure` 与 `share_trace_id`；④ UI 文档 §10.3 走查清单第 12 条改为「埋点事件与 PRD §17 事件字典一致」；⑤ §17.1 追溯矩阵的「关键埋点」列按本章事件名刷新。
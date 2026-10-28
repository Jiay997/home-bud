# Babe宝伴 V3.1 全功能模拟测试 · 续测报告

- **测试日期**：2026-10-21（续 2026-10-20 首轮全功能测试）
- **测试方式**：浏览器实测（Trae 内嵌 Chromium，browseruse 自动化）+ API 脚本实测（Python urllib 直连）
- **需求基线**：[宝伴-PRD_V3.1.md](file:///e:/FeiSi/Project%20code/HomeBud/docs/02-基线/宝伴-PRD_V3.1.md)（V3.0 未触及章节继续生效）
- **接口基线**：[API.md](file:///e:/FeiSi/Project%20code/HomeBud/docs/API.md)
- **缺陷基线**：[Babe宝伴-V3.1-全功能模拟测试报告_2026-10-20.md](file:///e:/FeiSi/Project%20code/HomeBud/docs/08-测试/Babe宝伴-V3.1-全功能模拟测试报告_2026-10-20.md)（N1–N6、D1–D7、U/A 用例编号体系）
- **本轮结论**：API 跑批 30 例 **PASS=27 / FAIL=3**（3 例均为新发现真实缺陷，无误报残留）；用户端 H5 15 个功能模块 UI 走查全部完成；运营端 admin 15 个页面全部走查；新发现缺陷 7 项（严重 2 / 一般 3 / 轻微 2）+ 观察项 4 项。

---

## 1. 测试环境说明

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows（宿主机） |
| 容器运行时 | Docker Desktop 4 容器：jiaban-frontend / jiaban-backend / jiaban-postgres / jiaban-redis |
| 前端服务 | nginx（宿主机 80 端口），uni-app H5 构建产物 |
| 后端服务 | FastAPI（backend:8000，nginx 反代 /api/v1） |
| 数据库 | PostgreSQL 16（宿主机 15432，库 jiaban） |
| 缓存 | Redis 7 |
| LLM 配置 | [.env](file:///e:/FeiSi/Project%20code/HomeBud/backend/.env)：`LLM_MOCK=true`、`EMBEDDING_PROVIDER=mock`（本地 mock 实现，未配置外部模型密钥） |
| 测试账号 | C 端：dev-login 动态设备号用户；admin：admin / Admin@123456 + MFA 123456 |
| 浏览器 | Trae 内嵌 Chromium（视口 1024×619） |
| 环境事件 | 测试中途 Docker Desktop 意外停止一次（14:10 前后），重启后容器自动恢复（restart policy 生效），数据未丢失 |

> **重要口径**：`LLM_MOCK=true` 下知识型问答正文走 referral_notice 兜底块（无 LLM 生成正文），triage 分级决策、SSE 协议、额度、合规链路均为真实代码路径。涉及"正文质量"的结论需在 `LLM_MOCK=false` 正式环境二次回归。

## 2. 各端访问网址（全部实测可达）

| 端 | 网址 | 实测结果 |
| --- | --- | --- |
| 用户端 H5 | http://localhost/app/ | ✅ 200，首页正常渲染，tabbar 四项可切换 |
| 运营端后台 | http://localhost/admin/ | ✅ 200，登录页渲染，两步验证可完成 |
| 后端 API | http://localhost/api/v1/* | ✅ 全部用例走 nginx 反代 200 |
| 不存在路由 | http://localhost/app/pages/profile/index、/admin/audit | ⚠️ 渲染空白页 / 回退知识库列表，无 404 兜底（D14） |

## 3. 多智能体协作功能验证

### 3.1 SSE 帧结构（本轮全部问答实测）

```
POST /api/v1/qa/sessions  →  session_uid
POST /api/v1/qa/sessions/{suid}/stream (SSE)
  started ×1 → section_delta ×N → section_done ×2（safety/child）→ completed ×1
```

- `section_done` 帧 = `{sequence, section_key, title, blocks[{block_key, title, content, access_tier}], pinned, cached}`；
- `completed` 帧 = `{status, degraded_reason, agents_involved, ai_label, trust_bar, triage, quota}`；
- delta 与 done 帧内容重复下发属协议设计（前端只渲染 done 块），实测前端无重复渲染。

### 3.2 智能体协作证据

| 场景 | agents_involved | 实测结果 |
| --- | --- | --- |
| 儿童知识问答（本轮 d21_final_check） | `['child','safety']` | ✅ 意图路由→child 智能体→safety 审核，completed 帧齐备 |
| 三面协作场景（R-E2E 复测） | child+safety+trust | ✅ completed.quota `{used:1, limit:4}` 正常交付 |
| 风险场景（危机词） | safety 硬拦截 | ✅ 今日产生 8 起"一级硬拦截"高风险事件（admin 风险列表可见），拦截与留痕链路真实生效 |
| LLM_MOCK 降级 | child（referral_notice 兜底） | ✅ 按设计降级，页面 AI 标识/信任条不缺失 |
| Agent 调用日志（admin /admin/logs） | retrieve/intent_route/triage/child_agent/pet_agent/safety_agent | ✅ 每次问答产生 5 节点调用记录（含耗时、trace_id） |

### 3.3 多智能体调度与降级结论

- 协作编排（意图路由 → 领域智能体 → 安全审核 → 信任组装）链路完整，Agent 失败率 0.00%（系统监控页实测）。
- LLM_MOCK 下"正文缺失"为环境降级而非编排缺陷；**编排骨架、帧协议、前端渲染三者契约一致**。

## 4. 功能测试用例

### 4.1 用户端 H5（UI 实测，15 模块）

| # | 模块 | 功能描述 | 操作步骤 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| U-01 | 首启隐私门禁 | 基础同意+免责声明确认后方可进入 | 首次访问→勾选两条同意→点主按钮 | 门禁面板消失，进入首页 | 面板消失，首页正常（截图 h5-01-privacy-gate.png） | ✅ PASS |
| U-02 | 首页 | 四入口卡+额度+阶段测评卡+会员卡+AI 角标+免责声明 | 浏览首页并核对元素 | 四入口/「今日可用 剩余 x/4 次」/测评卡「3 分钟·16 题·4 维度」/月卡 19.9 元/tabbar 四项/底部免责 | 全部齐备（截图 page-…03-45-29-543Z.png、ui-01-home.png） | ✅ PASS |
| U-03 | 问答流-儿童 | 提问→内容安全检查→回答→信任条→操作区 | 首页→育儿问答→输入问题→发送 | 「正在检查内容安全」→回答上屏→额度扣减→信任检查单/信息依据/安全提示/复制/存图/长图/反馈/举报 | 全流程正常；额度 4→3；「本页信息依据」含生成标识/适用月龄/来源等级（截图 03-46-49、03-47-08） | ✅ PASS |
| U-04 | 未建档降级 | 未建档时诚实提示 | 未建档状态提问 | 「暂无孩子档案：将按通用 1-3 岁回答」+「补充档案」入口 | 提示准确，入口可跳转 | ✅ PASS |
| U-05 | 儿童档案 | 单独同意门禁+建档表单+月龄计算 | 我的→档案→新建→填昵称/出生日期/性别等→保存 | 儿童信息单独同意弹层→建档成功→列表显示"xx 个月·性别" | 同意门禁生效（「已记录同意」toast）；建档成功「测试宝A 17 个月·女孩」月龄正确（截图 03-56-09） | ✅ PASS |
| U-06 | 宠物档案 | 类型/品种/年龄段/体重/主粮/绝育表单 | 档案页→宠物 tab→新建宠物档案→chip 选择→保存 | 档案建立，列表显示「狗 幼年·已绝育」 | 建立成功；chip 选择（猫/狗/幼年/已绝育）状态正确保存（宠物 2/3） | ✅ PASS |
| U-07 | 记录页 | 问答/报告历史+筛选 | 记录 tab→切换筛选（全部/孩子/宠物/问答/报告） | 条目含时间/类型/免费标识，计数准确 | 「共 x 条记录·已全部加载」正确 | ✅ PASS |
| U-08 | 我的页 | 账户信息脱敏+全部入口 | 我的 tab→逐项核对 | 账户标识脱敏（uid 前缀…）/档案额度/9+入口（健康档案/笔记/提醒/反馈/订单/权利中心/隐私承诺/易懂版/共享清单/协议/标识说明/账号安全） | 全部入口存在且可打开（截图 03-56-53） | ✅ PASS |
| U-09 | 提醒设置-开关联动 | 6 类型开关+总开关+一键关闭 | 提醒设置→开「疫苗」→开「每周一问」→开总开关→「一键关闭全部触达」 | 状态即时切换、持久化、批量联动 | 单开/总开/一键全关均生效；刷新后状态持久（截图 03-57-10、reminders_weekly_on.png） | ✅ PASS |
| U-10 | 每周一问转化 | 话题卡→自动提问归因闭环 | 开「每周一问」→刷新→点话题卡「带着这个问题去提问→」 | 跳转问答页自动发送，URL 带 reminder_trace_id，按档案月龄适配 | 跳转+自动发送成功；额度 3→2；回答页「适用：1–3 岁（17 月龄）」；正文含话题预置建议（截图 weekly_question_auto_ask.png） | ✅ PASS |
| U-11 | 个人信息权利中心 | 六类权利请求+SLA 承诺 | 我的→个人信息权利中心→查阅/导出/撤回/删除/注销 逐项打开 | 弹层文案合规；导出提交生成受理编号 | 查阅（档案/记录/同意状态）✓；导出受理 RT202610210410326E4C21（预计 2026-11-05 答复，处理中入列）✓；撤回（分项）/删除（不可恢复警告）/注销弹层文案合规 ✓ | ✅ PASS |
| U-12 | 隐私承诺页 | 5 条承诺+实现证据锚点+训练口径 | 我的→隐私承诺 | 每条承诺附「实现证据」与可操作跳转；训练口径声明 | 5 条承诺（最小化收集/单独同意/不用于训练/可删除导出/图片用完即删）+训练口径+诚实说明齐备 | ✅ PASS |
| U-13 | 阶段测评全流程 | 介绍→16 题→断点→提交→报告 | 首页→开始测评→答题→中途退出→重进→答完提交 | 介绍页反宿命论声明；断点自动保存；报告 4 维度档位+会员分层+演示数据标识 | 「这不是什么」声明✓；第 2 题退出重进恢复 2/16✓；首页出现「上次答到第 15 题 继续填写→」✓；报告页维度档位（只显示档位不渲染分数）/「关于气质」反宿命论/「演示数据」标识/会员分层/分享隐私提示齐备 | ✅ PASS |
| U-14 | 轻工具 | 3 工具展开+深入问问转化（不消耗额度外的额外扣减逻辑见用例） | 首页→工具→展开「宠粮配料表解析」→「深入问问」 | 展开内容含边界声明；转化到宠物问答自动发送 | 「不判定能否喂食」声明✓；禁忌成分科普✓；转化自动发送✓（额度正常扣减 1 次）；宠物侧「未匹配到知识库条目」诚实提示✓ | ✅ PASS |
| U-15 | 会员页 | 权益对照+合规购买文案+订单 | 我的→会员与订单→核对文案→勾选协议→立即开通→订单记录 | 权益对照表/「单次购买、不自动续费、到期不自动扣费」/退款条款/订单空态 | 全部合规文案齐备；点击后弹「微信支付接入后开放，当前版本暂无法完成支付」（mock 环境预期占位）；订单「暂无订单」 | ✅ PASS（支付为设计占位） |

### 4.2 运营端 admin（UI 实测，15 页面）

| # | 页面（路由） | 功能描述 | 实测结果 | 状态 |
| --- | --- | --- | --- | --- |
| A-01 | 登录（/admin/login） | 账号密码+MFA 两步验证+最小权限说明+审计提示 | 两步登录成功；「验证码已自动发送」toast；60s 重发倒计时 | ✅ PASS |
| A-02 | 知识库管理（/admin/kb） | 30 条条目列表（2 测试条目 v2+16 题库+宠物条目）、筛选、批量、导出 CSV、编辑/下架/回滚按钮 | 列表/操作按钮/分页（1 2）/合规基线说明齐备 | ✅ PASS |
| A-03 | 新建知识文档（/admin/kb/new/edit） | 5 种条目类型、适用前提（一票否决必填）、Markdown 编辑+预览、发布前合规校验（敏感词+医疗/兽药模式）、变更说明必填、并发锁 | 编辑器全要素齐备；「并发锁正常 当前由 系统超管 独占编辑」；「字数 0」实时统计 | ✅ PASS |
| A-04 | 词库维护（/admin/lexicon） | 24 条高危词两级判定（0.5 初拦 / 0.8 阻断）+刻度标尺 | 24 条与 N5 定量一致；「抽搐」在库、「抽筋」不在（与 10-20 结论一致）；编辑/删除按钮存在 | ✅ PASS |
| A-05 | Agent 调用日志（/admin/logs） | 每次问答 5 节点调用（retrieve/intent_route/triage/child_agent/pet_agent/safety_agent）+耗时+详情 | 记录与 C 端问答一一对应，「查看详情」入口存在 | ✅ PASS |
| A-06 | 反馈与举报（/admin/feedback） | 反馈列表+涉未成年强监管 SLA（24h 初审/72h 处置）+联动说明 | E2E 测试反馈 1 条待处理；SLA 与联动机制说明齐备 | ✅ PASS |
| A-07 | 高风险事件（/admin/risk） | 15 条事件列表+筛选（时间/14 类别/状态）+复核处置+内容追溯+误报回流抽检 | **N2 已修复**：列表正常渲染；复核面板（SLA 超时提示 94.9h/判定依据/结论三选/理由必填/上报主管部门选项/责任终身倒查声明）完整；「判定误报+测试性表达」提交成功「复核结论已提交」 | ✅ PASS |
| A-08 | 权利请求（/admin/rights） | RT 编号列表+处理按钮+SLA 状态筛选 | 3 条历史请求可处理；紧急（≤24h）筛选存在 | ✅ PASS |
| A-09 | 系统开关与配置（/admin/config） | 灰度开关（网络体验版开/正式版关）、pricing_config+一键回滚、入口级开关、危机渠道入口联动提示 | 「CRISIS_CHANNELS_V1 已废弃 前往危机渠道清单」联动正确；变更留痕说明齐备 | ✅ PASS |
| A-10 | 危机渠道清单（/admin/channels，V3.1 新增） | 10 类目缺渠道对照+渠道记录（police 已核验 2027-01-14 到期+4 条号码待补充）+核验操作 | 类目对照与渠道台账齐备；「号码待补充」状态如实展示 | ✅ PASS |
| A-11 | 分级规则（/admin/triage-rules，V3.1 新增） | 5 场景 23 条规则、月龄区间、专家会签门禁（未会签红档规则阻塞发布） | 场景分组/档位/优先级/会签状态（已会签 0/23）与后端一致；「专家会签」按钮存在 | ✅ PASS |
| A-12 | 内容运营（/admin/content） | 专题包（双签+红旗前置校验）+轻工具（禁确定性进食结论）+审计日志入口 | 3 专题包（交叉主题缺双签会签提示）+3 轻工具（无阻塞问题）；上架口径说明齐备 | ✅ PASS |
| A-13 | 系统监控（/admin/monitor，直达） | 调用统计/延迟分位（P50 36.48ms、P95 156.88ms、样本 187）/关键比率/V3.1 发布门禁卡/告警历史 | 门禁卡如实展示：AI 标识三链路通过（元数据 6/6）；拟人化扫描（扫描文件 0 个）、渠道核验（未达标类别 10）、规则会签（0/23）三项未通过——与 A-10/A-11 业务态一致，阻断性口径生效 | ✅ PASS |
| A-14 | 菜单导航（N4 回归） | 12 菜单项路由正确性 | **N4 复现（新形态）**：「系统监控」菜单点击后落在 /admin/content（直达 /admin/monitor 正常）；「审计记录」菜单也落 /admin/content（页面内确有审计日志入口，但菜单名与落地页不符） | ❌ FAIL（D11/D12） |
| A-15 | SPA 路由切换 | 菜单点击后内容区刷新 | 部分场景点击菜单仅改 URL、内容区不刷新（如首次点「高风险事件」），手动刷新后正常——与 N2 同源残留 | ⚠️ 观察项（D12） |

### 4.3 API 全量跑批（30 例）

PASS=27 / FAIL=3。前轮 6 个 FAIL 的定性全部收敛：

| 用例 | 现象 | 定性方法 | 最终结论 |
| --- | --- | --- | --- |
| M-3 建档后任务生成 tasks=0 | 建档/开偏好后 API 不同步生成任务 | 源码定位：[reminder_service.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/services/reminder_service.py#L644) 唯一生产调用点在 `run_reminder_sweep`；[scheduler.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/jobs/scheduler.py#L584) 每 1 小时触发 | **设计行为**（异步 sweep），UI 实测提醒任务正常生成（计划 2026-10-25/28）。建议优化：建档后同步触发一次 |
| S-3 长图显式标识 count=0 | 脚本在 PNG 二进制 count UTF-8 文本 | 下载 [s1_longimage.png](file:///e:/FeiSi/Project%20code/HomeBud/.build/diag/s1_longimage.png) 肉眼验证 | **误报反转 PASS**：顶部/中部/底部 3 处绿色「AI 生成·仅供参考·不构成诊疗建议」标签，满足 ≥2 处要求 |
| R-E2E quota used=0 | 脚本查 quota 端点方式错误 | 改从 completed 帧 `quota` 字段读取复跑 | **误报反转 PASS**：`{"used":1,"limit":4}` 正常交付；UI 实测额度扣减（4→3→2）同步正常 |
| C-3 PNG 元数据 resp=null | 脚本对空 POST 调用（该接口要求 multipart 上传） | 按 [compliance_api.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/api/v1/compliance_api.py#L92) 契约 multipart 上传 PNG 复测 | **误报反转 PASS**：5/5 隐式标识键（software/ai_generated/content_type/generated_at/render_id）+ label_check.passed=true |
| T-2 2 岁低热期望绿档实测红档 | 无档案用户提问 | 带档案（24 月龄）复测 [d21_t2_profile.py](file:///e:/FeiSi/Project%20code/HomeBud/.build/diag/d21_t2_profile.py) + 源码核对 [engine.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/engine.py#L438) | **部分真实缺陷（D9/D13）**：带档案后 red→yellow（月龄窗生效，fever_infant_lt3m 不再误命中），但「精神还好」未被识别 → 绿档不可达；无档案时 red 属保守设计 |
| T-3 宠物食欲差 triage 空 | completed.triage={} | 逐层核对 [templates.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/templates.py#L46) SCENE_KEYWORDS | **真实缺陷（D10）**：「食欲不好/不爱吃」不含连续子串「不吃」，场景词表无食欲类词 → scene=None；规则库 pet_behavior_mild 永不可达 |

## 5. 边界条件与异常场景测试

| # | 场景 | 操作 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- | --- | --- |
| B-01 | 免费额度用尽 | 连续提问至 4/4 用尽 | 第 5 次拒绝（1202「今日免费额度已用尽」），会员不受限 | 跑批 V3.1 专项验证通过；UI 额度文案「用尽后可次日再来，或开通会员」 | ✅ PASS |
| B-02 | 未建档问答降级 | 无档案提问（儿童/宠物） | 按通用区间回答并提示 | 「按通用 1-3 岁回答」「未绑定档案：将按通用饲喂区间回答」 | ✅ PASS |
| B-03 | 测评断点续答 | 第 2 题退出→重进 | 恢复至第 2 题 | 恢复 2/16，进度 6%；首页出现断点入口 | ✅ PASS |
| B-04 | token 过期（2h）后继续操作 | 登录超 2 小时后提交第 16 题答案 | 自动续期或引导重登 | **报「会话缺失或已失效」（1101）作答丢失**；刷新首页后登录态自动恢复 | ❌ FAIL（D8） |
| B-05 | 知识库未命中 | 宠物侧冷门问题 | 诚实提示而非编造 | 「当前未匹配到知识库条目，以下建议仅供参考」 | ✅ PASS |
| B-06 | 危机词硬拦截 | 提问含急症/用药剂量类高危词 | 一级硬拦截+高风险事件留痕 | 今日 8 起「一级硬拦截」事件入 admin 风险列表 | ✅ PASS |
| B-07 | 权利请求重复提交/SLA | 提交导出申请 | 受理编号+预计答复时间+申请记录入列 | RT 编号+「预计 2026-11-05 前答复」+处理中状态 | ✅ PASS |
| B-08 | 不存在路由 | 访问 /app/pages/profile/index、/admin/audit | 404 兜底或重定向 | H5 渲染空白页；admin 回退知识库列表 | ⚠️ FAIL（D14，轻微） |
| B-09 | 服务中断恢复 | Docker Desktop 停止后重启 | 容器自愈、数据不丢 | 4 容器自动恢复、backend health 通过、数据完好 | ✅ PASS |
| B-10 | 精神状态口语表述 | 「2岁宝宝低烧37度8精神还好」 | 识别为 normal → 绿档 | 未识别 → 退保守黄档 | ❌ FAIL（D9） |

## 6. 关键业务流程测试（E2E）

| # | 流程 | 链路 | 结果 |
| --- | --- | --- | --- |
| F-01 | 新用户首启→建档→问答→提醒→每周一问转化 | 门禁→建档（单独同意）→问答（额度扣减）→提醒开关开启→每周一问话题卡→自动提问（reminder_trace_id 归因）→月龄适配回答 | ✅ 全链路 PASS |
| F-02 | 阶段测评闭环 | 介绍页→16 题作答→断点续答→提交计分→报告（4 维度/会员分层/分享提示）→保存长图 | ✅ PASS（保存长图 H5 端为 toast 占位，见 O-1） |
| F-03 | 个人信息权利行使 | 查阅（摘要）→导出申请（受理编号+SLA）→撤回/删除/注销弹层（不强执行） | ✅ PASS |
| F-04 | 高风险事件复核处置（admin） | 列表→复核面板→判定误报→预设理由→提交→状态流转 | ✅ PASS |
| F-05 | 轻工具→问答转化 | 工具展开→深入问问→带话题自动提问→额度扣减 | ✅ PASS |
| F-06 | 会员购买（mock） | 权益对照→勾选协议→立即开通→支付占位弹窗→订单空态 | ✅ PASS（真实支付需微信支付接入后回归） |
| F-07 | admin 知识运营流 | 新建文档编辑器→合规校验→变更说明→并发锁；词库 24 条两级阈值；规则会签门禁（0/23 阻断发布） | ✅ PASS（门禁阻断性生效） |
| F-08 | 多智能体问答协作 | 意图路由→领域智能体→安全审核→信任组装→SSE 四段帧 | ✅ PASS |

## 7. 界面兼容性测试

| # | 项目 | 方法 | 结果 |
| --- | --- | --- | --- |
| C-1 | 375×667 小屏适配 | 代码级：客户端全量使用 rpx（750rpx=屏宽自动换算）+ flex 弹性 + `min-width:0` 防溢出；[App.vue](file:///e:/FeiSi/Project%20code/HomeBud/client/src/App.vue#L65) `max-width:480px` 容器约束 | ✅ 布局体系天然适配（1024×619 实测渲染无横向滚动、无错位） |
| C-2 | 动效减弱偏好 | [qa/index.vue](file:///e:/FeiSi/Project%20code/HomeBud/client/src/pages/qa/index.vue#L1786)、StateSkeleton 存在 `@media (prefers-reduced-motion: reduce)` | ✅ 已适配 |
| C-3 | 旧浏览器新 API 依赖 | 全量检索 `randomUUID/structuredClone/replaceAll/??=` 等：零直接依赖；构建链含 Babel targets | ✅ 无明显兼容风险 |
| C-4 | 桌面浏览器（Chromium 1024×619） | 本轮全部 UI 走查 | ✅ 全模块正常 |
| C-5 | Firefox / WebKit / 微信开发者工具 / 真机 | 本环境无对应运行时，无法实测 | ⚠️ **限制声明**：建议真机回归（iOS Safari、Android Chrome、微信 H5 容器） |

## 8. 缺陷清单（本轮新增）

严重程度定义：致命（阻断上线）/ 严重（主流程受损）/ 一般（功能缺损但有绕行）/ 轻微（体验/文案问题）。

| 编号 | 严重程度 | 标题 | 复现步骤 | 实际 vs 预期 | 证据 |
| --- | --- | --- | --- | --- | --- |
| **D8** | **严重** | access_token 2h 过期后无自动续期，长会话操作中断丢数据 | dev-login 后保持会话 >2h → 进入测评答题 → 提交答案 | 实际：PUT answer 返回 1101「会话缺失或已失效」，页面 toast 报错，第 16 题作答丢失；预期：静默 refresh_token 换发或引导重登后恢复现场 | [request.ts](file:///e:/FeiSi/Project%20code/HomeBud/client/src/platform/request.ts) 无 1101 拦截/重试逻辑；[security.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/core/security.py#L20) `USER_ACCESS_TTL=2h`、refresh 30d 未被客户端使用（仅 session.ts consent 场景有单次重试） |
| **D9** | 一般 | triage 精神状态词表缺口，AC-RQ06-2 绿档不可达 | 建档 2 岁（24 月）孩子 → 提问「2岁宝宝低烧37度8精神还好要不要去医院」 | 实际：level=yellow（fever_default 保守档）；预期：识别「精神还好」为 normal → fever_low_green 绿档。[NORMAL_STATE_KEYWORDS](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/engine.py#L65) 含「精神好」但「精神还好」非其连续子串 | d21_t2_profile.py 复测输出 rule_hits=["fever_default"] |
| **D10** | 一般 | 宠物食欲类问题场景词表断层，观察档规则永不可达 | entry=pet 提问「狗狗这两天食欲不好不爱吃狗粮」 | 实际：completed.triage={}（scene=None，无档位）；预期：命中 pet_behavior_mild 绿档（观察档）。[SCENE_KEYWORDS.pet_acute](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/templates.py#L46) 无「食欲不好/不爱吃/胃口差/食欲下降」，规则条件与场景词表脱节 | d21_triage_check.py 输出 triage={} |
| **D11** | 一般 | admin「系统监控」菜单路由绑错 | admin 登录 → 侧栏点「系统监控」 | 实际：URL 跳 /admin/content（内容运营页）；预期：/admin/monitor（直达可达且渲染正常）。另「审计记录」菜单也落 /admin/content | 菜单点击实测 URL 记录（本轮 A-14） |
| **D12** | 轻微 | admin SPA 菜单点击后内容区不随 URL 刷新 | 登录后首次点击「高风险事件」等菜单 | 实际：URL 已变 /admin/risk 但内容区仍显示上一页，需手动刷新；预期：路由切换即重渲染。与 N2 同源（前端路由 watch 缺失），N2 修复后仅剩该残留 | 本轮 A-15；刷新后 N2 列表渲染正常 |
| **D13** | 轻微 | 无档案发热场景展示月龄特异规则标题，语义误导 | 无档案用户提问含「低烧/37.8」 | 实际：红档（保守正确）但 rule_hits[0].title=「3 月龄以下婴儿发热…」，对未知月龄用户有误导；预期：无档案时优先展示 fever_default（「发热但信息不足以定档」）类通用标题，或 title 按「月龄不明」口径输出 | d21_triage_check.py T-2 输出 |
| **D14** | 轻微 | 前端不存在路由无 404 兜底 | 访问 /app/pages/profile/index（真实「我的」页为 /app/pages/me/index）或 /admin/audit | 实际：H5 渲染空白页（uni-app 空容器）；admin 回退知识库列表无提示；预期：404/重定向兜底页 | 本轮 §2 实测 |
| O-1 | 观察项 | H5「保存长图/存图」仅 toast，无实际下载 | 报告页点「保存长图」 | toast「已保存到相册」，浏览器无下载动作——H5 端应触发图片下载或明确提示"请在小程序内使用" | 本轮 U-13/U-15 实测 |
| O-2 | 观察项 | 会员页未勾选协议点「立即开通」静默无提示 | 不勾选直接点开通 | 无任何 toast/抖动提示，按钮无响应；建议补充「请先阅读并勾选」提示 | 本轮 U-15 实测 |
| O-3 | 观察项 | 每周一问跳转 q 参数双重 URL 编码 | 从话题卡跳转问答页查看 URL | `q=1-3%2520%25E5...`（%25 双重编码），页面标题解码正常不影响使用；分享链路冗余度增加 | 本轮 U-10 实测 |
| O-4 | 观察项 | LLM_MOCK 环境知识型问答无正文 | mock 环境提问知识类问题 | child section 仅 referral_notice 兜底块；属环境降级。**上线前必须以 LLM_MOCK=false 回归正文质量、来源引用与信任条完整性** | 前轮定性延续 |
| （前轮延续） | 严重 | 测评报告长图数据区渲染 Python dict repr | 提交测评→保存长图→肉眼检查 | `{'report_name': ...}`、`{'demo': True}` 等内部字典直接绘制，分享产物不可读且暴露内部标记（本报告归档 report-longimage-s3.png 可复核） | 10-20 会话发现，本轮确认未修复 |

### 前轮缺陷回归状态（N1–N6、D1–D7 摘要）

| 编号 | 本轮状态 |
| --- | --- |
| N1 401 时间窗 | ✅ 未复现（600s/289 次监测）；本轮 D8 为另一根因（token 自然过期），两者已区分 |
| N2 风险事件列表前端绑定 | ✅ **已修复**（/admin/risk 直达渲染 15 条+复核流程走通） |
| N3 | ✅ 回归通过 |
| N4 admin 菜单问题 | ⚠️ 复现新形态：系统监控菜单路由绑错（D11）+内容区不刷新（D12） |
| N5 词库数量 | ✅ 24 条与词库维护页一致（「抽筋」仍缺失，维持原建议） |
| N6 | ✅ 定性归档（环境因素，未复现） |
| D1–D7 | 其中"报告长图 dict repr"确认未修复（严重）；其余维持 10-20 报告结论 |

## 9. 测试总结与建议

### 9.1 总体结论

1. **核心链路可发布度**：隐私门禁、问答协作（SSE/额度/信任条/AI 标识）、分级决策骨架、危机硬拦截、权利中心、测评全流程、admin 运营与 V3.1 发布门禁机制**全部真实可用**，本轮 UI+API 双通道均未发现阻塞性回归。
2. **V3.1 上线阻塞项现状**：PRD 要求的 RQ-01/02/03/06/07/08 中——AI 标识三链路（RQ-01）✅ 已达标；渠道清单（RQ-03 项下）台账就绪但**核验未达标（占位 5 条、未达标类别 10）**；分级规则**专家会签 0/23**——与系统监控页"V3.1 发布门禁：3 项未通过"一致，**按门禁口径当前不得发布**，需完成渠道核验与规则会签。
3. **LLM 正式接入为最大前置项**：O-4 表明正文链路未经过真实模型验证；建议在接入后优先回归：正文质量、知识引用来源等级、拟人化禁用词全量扫描（当前扫描文件数为 0，接入后才有意义）。

### 9.2 缺陷处置建议（按优先级）

1. **D8（严重）**：在 [request.ts](file:///e:/FeiSi/Project%20code/HomeBud/client/src/platform/request.ts) 增加统一 1101 拦截：调用 refresh 接口换发（refresh_token 30 天有效已在下发），失败再跳登录；测评/长表单场景增加本地草稿暂存，避免作答丢失。
2. **D9/D10（一般）**：扩充 [engine.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/engine.py#L65) NORMAL 词表（精神还好/精神状态不错/能吃能睡 等）；为 [templates.py](file:///e:/FeiSi/Project%20code/HomeBud/backend/app/triage/templates.py#L32) SCENE_KEYWORDS.pet_acute 增补食欲类词（食欲不好/食欲下降/不爱吃/胃口差/挑食），使 pet_behavior_mild 可达。**分诊词表属医疗安全相关，建议一并提交专家会签流程（与 A-11 门禁合并处理）**。
3. **D11/D12（一般/轻微）**：修正 admin 侧栏「系统监控」router 目标为 /admin/monitor；为「审计记录」独立路由或在 content 页内高亮锚点；补路由 watch 或改用编程式导航强制重渲染。
4. **D13/D14（轻微）**：triage 输出层对 age_months=None 场景重排 rule_hits 展示顺序（fever_default 置顶）；uni-app/admin 补 404 兜底页。
5. **报告长图 dict repr（严重，前轮延续）**：渲染层数据序列化修复后，需重验「显式标识≥15% 面积+≥2 处+元数据 6/6」三项仍达标。

### 9.3 流程与体验建议

- **M-3 优化**：建档/偏好变更后同步触发一次 `generate_tasks_for_user`（当前依赖最长 1h 的 sweep），否则用户开完开关看不到任务产生的即时反馈。
- **O-1/O-2**：H5 端存图改走浏览器下载或加端判断文案；会员未勾选时给否定 toast。
- **真机回归**：iOS Safari / 微信 H5 容器 / 微信开发者工具在本环境无法覆盖，建议列入发版前必测清单。

### 9.4 本轮测试覆盖统计

| 维度 | 数量 |
| --- | --- |
| API 跑批用例 | 30（PASS 27 / FAIL 3，3 例全部转化为缺陷 D9/D10 + T-2 拆分） |
| 用户端 UI 模块 | 15（PASS 15） |
| 运营端 UI 页面 | 15（PASS 13 / FAIL 2：A-14、A-15） |
| 边界异常场景 | 10（PASS 7 / FAIL 3 → D8/D9/D14） |
| E2E 业务流 | 8（PASS 8） |
| 新增缺陷 | 严重 1（D8）+ 前轮延续严重 1（长图 repr）+ 一般 3（D9/D10/D11）+ 轻微 2（D13/D14）+ 观察项 4 |
| 截图证据 | 31 张（[docs/08-测试/attachments/](file:///e:/FeiSi/Project%20code/HomeBud/docs/08-测试/attachments/)） |

---

**报告产出**：2026-10-21，基于当日全部实测记录；诊断脚本与原始输出留存于 [.build/diag/](file:///e:/FeiSi/Project%20code/HomeBud/.build/diag/)（d21_user_tests.py、d21_final_check.py、d21_triage_check.py、d21_t2_profile.py、d21_png_eye.py、d21_body_probe.py 等）。

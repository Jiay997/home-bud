---
target: frontend/src/views/app/
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
target_identity: "file:D:\\HomeBud\\frontend\\src\\views\\app"
timestamp: 2026-10-10T09-08-42Z
slug: frontend-src-views-app
---
# 家伴用户端 UI/UX 评审报告（frontend/src/views/app/）

`Method: dual-agent (A: 设计评审子代理 · B: 检测器/浏览器证据子代理)`

> **运行环境修正**：HomeBud 的真实 dev 端口是 **5188**（5173/5174 上是另一个项目「梦绘片场」）。截图通道不可用（viewport 0×0, visibilityState=hidden），运行态证据以 DOM 计算样式、元素尺寸实测与 console 检测输出为准；视口 375×812 量测、九条路由实测。

## Design Health Score（Nielsen 10 启发式）

| # | 启发式 | 分数 | 关键问题 |
|---|-----------|-------|-----------|
| 1 | 系统状态可见性 | 3 | 问答页整页不显示剩余额度（QaSessionPage.vue:13-207）；记录页“下拉加载更多”与实际“触底自动加载”不符（HistoryListPage.vue:109-110 vs :287-295） |
| 2 | 贴合真实世界 | 2 | 工程/法务黑话外泄：MemberPage.vue:109（1202）、OrderPage.vue:32,81,89,93-94（制段校验/VAL-TOKEN/幂等防重）、MePage.vue:44、FamilyQaPage.vue:34；OrderPage.vue:56 中文不通 |
| 3 | 用户控制与自由 | **1** | 实测 /app/member 375×812 下返回控件 0 个、tabbar 不渲染；16 个页面用裸 $router.back()，深链进入时 history.state.back === null → web-view 里“返回”= 退出小程序；专为此写的 PageHeader.vue 全仓 0 引用 |
| 4 | 一致性与标准 | **1** | 同一目的地三个名字（记录/历史记录/历史问答与报告）；返回控件 6 种类名、32/36px 两套；tab 级页面也画返回箭头；脱敏只在一屏生效 |
| 5 | 防错 | 3 | 勾选置灰、幂等、连点锁、删档二次确认到位；扣分：额度用尽时输入框先被清空才报错（QaSessionPage.vue:387 → :463）；500 字上限无计数器 |
| 6 | 识别而非回忆 | 3 | 但剩余额度必须回首页记，MePage 6 个装饰性右标只增解析成本 |
| 7 | 灵活与效率 | 2 | 无“再问一次/追问”，回答卡只能整篇复制；三个问答页是三份 27-31KB 近似重复实现 |
| 8 | 美学与极简 | 2 | AI 免责同屏 2-3 次、固定输入区占屏 13%（109px/812px，含约 60px 免责条） |
| 9 | 错误识别/恢复 | 2 | 大量静默吞异常（MePage.vue:228-247 三处 catch {// 静默}）；1202 toast 无行动入口 |
| 10 | 帮助与文档 | 2 | 四个法务链接全是 javascript:void(0) 死链（StartPage.vue:62-68），且回访用户默认带勾（:120） |
| **Total** | | **21/40** | **可接受（下沿）** |

## 设计特异性裁决

**LLM assessment（A）**：高度定制，但定制只覆盖一半产品。贯穿三层（视觉/信息结构/文案）的“量具/刻度/校准”隐喻是活的（GraduatedBand.vue 游标越轨 5px、首页额度分段、抽屉 30 格刻度尺、空态画成空刻度槽；问答对象选择器嵌 header、多 Agent 调度卡、危机话术卡）。但 MePage（12 行同权重清单 + 3 行假链接）与 MemberPage（3 列规格对照 + 价格卡 + 勾选条款）退化为任何产品都能套的模板，且恰是用户抱怨的入口。

**Deterministic scan（B）**：impeccable detect 对 views/app/、layouts/、components/ 三目录 0 发现（退出码 0），灵敏度自证有效。视觉层没有廉价“AI 味”反模式；但静态规则集不覆盖渲染态。

**Visual overlays（B）**：检测脚本注入成功（preflight 通过；live-server 8400）。console 报告：/app/home 2 条（skipped-heading h1→h3 跳级、repeating-stripes-gradient）、/app/member 1 条（bounce-easing，element-plus 库自带，误报/advisory）、/app/qa/family 0 条、/app/profiles 与 /app/history 各 1 条 low-contrast（2.5:1，非误报，系统性令牌问题）。截图通道不可用，可视标注未能截图验证。

**A 与 B 的分歧裁决**：A 判定“对比度全部达标”漏算了“白字 on 深色 accent (#4fb3a4)”组合。tokens.scss:116 的 html.dark { --el-color-primary: #4fb3a4 } 使深色模式下所有主按钮白字对比度 2.5:1（浅色 #0a6b60 约 5.9:1 达标）。以 B 的实页计算样式为准，为确定性缺陷。

## Overall Impression

视觉纪律极高、把“刻度”隐喻与安全合规做成一等公民；但“出口（导航）”与“移动硬标准（触控/键盘/对比度）”两处系统性违约，恰好集中在用户最常走的路径上。最刺痛：额度用尽时最需要的安抚抽屉（SC-21）已实现，却只挂在会员页一张写着“点击预览”的演示卡上。

## What's Working

1. “量具”隐喻是活的：4 个场景复用同一语法，数字全等宽 tabular，承担“结论落哪一档”的产品承诺。
2. 流式回答的分层等待：骨架 → 安全检查 → “Agent 生成中（≤8s）” → 逐节 delta → 降级时点名哪几节失败（QaSessionPage.vue:83-96,118-165）。
3. 安全合规是一等公民：存证回显、拦截不回显原文且“不计次数”、危机渠道配沟通话术（RiskBlockPage.vue:56-71）。
4. 对比度地基扎实（浅色模式）：18 组 token 组合最低 4.81:1；.touch-target/--focus-ring/sr-only/prefers-reduced-motion 机制齐备——问题在没推广。

## Priority Issues

### [P0] 二级页面零出口 & 深链返回即退出
- Why：/app/member 实测返回控件 0 个、tabbar 不渲染（路由只有 meta.title 无 meta.tab，tabbar 只在 meta.tab 时渲染）；16 个页面裸 $router.back()，深链进入时 history.state.back === null → web-view 里等于退出小程序。MemberIosPage.vue 同样零出口。已写好的 PageHeader.vue（三段式返回 to → history.state.back → replace('/app/home')）全仓 0 引用。会员页“立即开通 19.9”按钮实测 y=812 恰好卡在首屏外（bodyH=1444）。
- Fix：把“出口”从页面责任改为布局责任——MobileLayout 对 !route.meta.tab 路由统一渲染返回页头；删掉 16 处裸 back() 改走三段式；/app/member 补明确返回落点。
- 定位：MemberPage.vue:12-19、MemberIosPage.vue:9-11、router/index.ts:148-159、MobileLayout.vue:11-12,96-113、components/PageHeader.vue:63-73；裸返回样例：OrderPage.vue:13、QaSessionPage.vue:17、ProfileListPage.vue:12 等 16 处。
- Suggested command：$impeccable adapt + $impeccable polish

### [P0] 移动可用性硬标准系统性不达标
- Why：tokens.scss:58-59 自订 --touch-min: 44px，但实测：返回键 32×32、首页“立即建档”48×19、MePage 列表行 299×39、退款 el-checkbox 14×32、同意页勾选行 299×22、问答主输入框 247×42（14px 字）；全仓 visualViewport 0 命中——iOS 弹键盘时固定输入区（109px）不会让位；index.html:7 禁止缩放，12px 小字无补偿（WCAG 1.4.4 失败）。
- Fix：列表行 padding 8px 0→12px 0（39→47px）；图标按钮统一 44×44（视觉可 32，.touch-target::after 扩热区）；输入框 42→44px、字号 14→16px；同意页/退款行整行做成 48px label；监听 visualViewport 抬升输入区 bottom。
- 定位：tokens.scss:58-59,260-274、QaSessionPage.vue:867-870,895-905、MemberPage.vue:84-87,439-449、StartPage.vue:360-397、MePage.vue:323-331,398-405、HomePage.vue:82、index.html:5-9。
- Suggested command：$impeccable adapt + $impeccable audit

### [P1] 额度用尽闭环断裂：安抚抽屉没接真实触发器，且输入被清空
- Why：唯一处理是 3 秒 toast（三页各写一遍），且发请求前就 question.value = '' → 用户写的问题直接消失；MemberPage.vue:154-212 那个设计完整的抽屉（标定预警/次日归位/会员不受限/仍可浏览绿条）只由一张演示卡打开，文案还把错误码“1202”印给用户看（:109）。问答页全程无剩余额度显示。
- Fix：抽 useQuotaGuard() 统一三页 1202：就地在当前页打开抽屉（非 toast）+ 回填输入；问答页头部常驻剩余额度；删演示卡与 1202 文案；抽屉主按钮改为具体动作。
- 定位：QaSessionPage.vue:387,463-465、PetQaSessionPage.vue:494、FamilyQaPage.vue:535、MemberPage.vue:106-112,154-212。
- Suggested command：$impeccable harden + $impeccable clarify

### [P1] 深色模式主按钮对比度 2.5:1 + 首页标题层级跳级
- Why：tokens.scss:116 深色 --el-color-primary:#4fb3a4 上白字 2.5:1，全部主按钮不达 WCAG AA（实页复核非误报）；/app/home h1→h3 缺 h2；首页有 repeating-stripes-gradient。A 遗漏、B 捕获。
- Fix：深色模式主按钮文字改深色（如 #0f1e1c on #4fb3a4 约 8:1）或压暗按钮底；补 h2 语义层级；替换条纹渐变。
- 定位：styles/tokens.scss:116、HomePage.vue:113-124。
- Suggested command：$impeccable audit + $impeccable typeset

### [P2] “承诺了但没做”：3 个死链行 + 4 份读不到的法务协议
- Why：MePage.vue:122,135,140 三行带 › 点击无反应（实测非导航元素）；StartPage.vue:62-68 四份协议全部 javascript:void(0)——用户必须“已阅读并同意”却无处可读；回访默认带勾（:120）。合规与信任双重缺口。
- Fix：二选一不留中间态——实现内页/dialog 可读，或去掉 › 加“暂未开放”灰标；协议不预勾；“假可点”扫描纳入门禁。
- 定位：MePage.vue:122,135,140、StartPage.vue:62-68,113,120、MemberPage.vue:119-120。
- Suggested command：$impeccable clarify + $impeccable harden

## Persona Red Flags

**Casey（移动单手/频繁被打断）**
- 从首页点“了解会员”→ 进 /app/member 即被困（0 返回、0 tabbar）；被孩子叫走后回来，唯一出路是系统手势——点错就离开小程序（用户原话 100% 复现）。
- 开通按钮 y=812 卡在首屏外，必须滑动后点击；中途打断后页面不记住滚动位置。
- 问答页：输入框被键盘顶住风险 + 固定栏吃掉 13% 屏；额度用尽/失败时输入已清空。
- 返回键在最难够的顶部（x16,y10），可达的底部 tab 只存在于 tab 页——最关键的动作放在最难够的位置。

**Sam（无障碍/大字体）**
- 禁缩放 + 全站大量 12px 小字 → 需要放大者无任何手段（WCAG 1.4.4 失败）。
- div 型可点目标（MemberPage.vue:106、HomePage.vue:113、MePage.vue:162）无 role/tabindex；无 href 的 <a>（MemberPage.vue:119-120）。
- 亮点保留：对比度浅色全达标、--focus-ring、sr-only、GraduatedBand 用 aria-label 讲档位。

**Jordan（首次用户）**
- 入口先“同意”但协议读不到——第一次信任接触即失败。
- 首屏最抢眼的是“四象宝宝气质测评”（实底+主色按钮），而他要的是“问一个育儿问题”（列表行）。
- 未建档提示与问答页“未选档案”提示各自为政；档案页脱敏显示“宝某”让家长怀疑数据没存对。

## Minor Observations

- PageHeader.vue 在评审期间（16:48）被外部进程创建，全仓 0 引用——疑似并行会话/工具产物，本轮未动它。
- --sp-5(20px) > --sp-6(16px)，后缀不单调 + 3 个文档外档位（tokens.scss:46-56 自称“禁止未定义档位”）。
- --on-accent 从未声明（tokens.scss:543 用 fallback）。
- .page 的 padding-bottom:72px 加在无 tabbar 页面（会员/订单）上白扔一条屏。
- 记录页“下拉加载更多”是假承诺，无 IntersectionObserver 时无手动加载入口。
- 设计规范演示页 /app/answer-demo 挂在生产路由表。
- 脱敏只在一屏生效（档案页掩码 vs 问答/详情/删除弹窗裸名）。
- ProfileListPage.vue:101“● 正在接受 AI 深度发育监测”有广告法/医疗宣称风险且与免责自相矛盾。
- 静默吞异常（MePage.vue:228-247、HomePage.vue:283-284）——抖动时显示“你没有档案”而非“加载失败，重试”。
- theme-color 静态浅色绿，不随深色模式切换。

## Questions to Consider

1. 如果微信导航栏不可依赖，为什么“返回”是页面的责任而不是外壳的责任？能否接受“MobileLayout 为所有非 tab 路由强制渲染出口 + 构建期断言”的硬规则？
2. 产品的差异化（刻度/量具）与它的阅读门槛（标定/制段/校准）是同一件事吗？
3. 既然额度抽屉已实现，为什么只在“点击预览”里？把它接到真实 1202 时刻后，会员页能不能删掉一半内容？
4. 输入区常驻 13% + 免责条写 4-5 次，换来了什么？腾出的 60px 放什么？

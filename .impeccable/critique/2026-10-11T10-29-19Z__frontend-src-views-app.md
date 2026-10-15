---
target: frontend/src/views/app/（用户端界面）
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:D:\\HomeBud\\frontend\\src\\views\\app"
timestamp: 2026-10-11T10-29-19Z
slug: frontend-src-views-app
---
# 家伴用户端 UI/UX 评审报告（frontend/src/views/app/）

`Method: dual-agent (A: 设计评审子代理 · B: 检测器/浏览器证据子代理)`

> **运行环境备注**：HomeBud dev server 在 `http://localhost:5173/`（`127.0.0.1:5173` 上是另一个项目，勿混）。评审期间登录态过期，多页出现 401（B 实测），A 以页内只读 fetch mock 复现设计态。截图通道间歇可用，量化结论以 DOM 计算样式、几何实测与 iframe 375×812 复核为准。

## Design Health Score（Nielsen 10 启发式）

| # | 启发式 | 分数 | 关键问题 |
|---|-----------|-------|-----------|
| 1 | 系统状态可见性 | 3 | 渐进渲染/安全检测行是全站最好的一处；但会话失效后首页只剩「数据加载失败/重试」且重试永久失败（HomePage.vue:64-67, 292-296） |
| 2 | 贴合真实世界 | 3 | 家长语体很稳；工业英文标签漏进 UI：「MANDATORY · 必须知悉」(StartPage.vue:21)、「SAFE-ONLY 模式」(AnswerCardDemo.vue:113)、「GraduatedBand」(AssessmentReportPage.vue:76) |
| 3 | 用户控制与自由 | 2 | 壳体已有开发期出口审计（MobileLayout.vue:93-107)；但 MePage 3 行假可点死链（MePage.vue:122-145）、StartPage 4 个 `javascript:void(0)` 协议（StartPage.vue:62-68） |
| 4 | 一致性与标准 | 2 | token 一致、页面层分裂：签名组件 1/26 页在用（`GraduatedBand` 实测仅 PetQaSessionPage.vue:248）；回答卡两套实现（SectionCard vs 内联 `.ai-sec`）；3 个组件 0 引用 |
| 5 | 错误预防 | 3 | 分层同意/退款勾选/删除二次确认/幂等/风险前置/1202 抽屉扎实 |
| 6 | 认得而非回忆 | 3 | Tab 图标+文字、空态教学、问答页额度 chip；扣分：MePage 12 行同构、页头 5 个纯图标按钮 |
| 7 | 灵活与效率 | 2 | 无建议问题、无「再问一次」、历史无快捷入口；语音已移出 MVP 却仍占着主操作行 |
| 8 | 美学与极简 | 2 | 无装饰噪音，但极简沦为同构：首页 6 个同构矩形、Me 8 张同构卡；层次只靠主色实底承担，而主色花在了测评促销上 |
| 9 | 错误识别与恢复 | 2 | 「数据加载失败」通用文案 + 无诊断 + 对 1101 无限重试；无字段级内联错误；降级恢复（保留已渲染分节）做得好 |
| 10 | 帮助与文档 | 2 | 无应用内帮助/检索；帮助信息散落在 MePage 合规行里；空态 hint 质量不错 |
| **Total** | | **24/40** | **Acceptable（60%）** |

## 设计特异性裁决

**LLM assessment（A）**：结论——**「系统」是为这个产品做的，「版式」不是。** 方向（Operate + 量具 + 安全即主色）有立场、有来源、可辩护；但方向只兑现到了 token 层，没有兑现到页面层：

1. **签名组件几乎不存在。** DESIGN.md 称 `GraduatedBand` 为「全系统的签名」，实测仅 **1/26** 个页面 import（PetQaSessionPage.vue:248）；`AppealPanel`/`CrisisChannelCard`/`ProfileSwitcher` **0 引用**——风险与申诉两条高敏感链路各自手搓实现。
2. **占据视觉的恰是系统明令禁止的东西。** 全产品最高频 motif 是「彩色左竖条 + 标题」：tokens.scss:515-522 的 `.st-section-head::before`（3px）加上 12 处 6px 竖条（AssessmentReportPage.vue:831-836 等），实测 **17 个文件 55 处**；而 DESIGN.md:308/286 明确写着「不用超过 1px 的彩色边框」「不设左侧色条：用面，不用线」。
3. **「量具」退化点可逐页点名**：报告页四维分档是 `repeat(3,1fr)` 三格勾选控件（AssessmentReportPage.vue:98-112, 742-772）＝视觉上的 radio group，不是量具；组件名被当文案打印（:76）；首页刻度带注释自认「纯装饰」（HomePage.vue:478-494），违反 DESIGN.md:282 第①条；风险三档置信度在最该出现的一刻（RiskBlockPage.vue:33）完全缺席；MePage「刻度容量」是纯文本。

**委托人「一进来只是选项框框」的机制成立**（首页首屏实测）：六个同宽、同圆角、同发丝线的矩形垂直堆叠（品牌卡→黄条→额度→测评→三入口→会员）；首屏唯一的主色实底按钮是「开始测评」（HomePage.vue:120），而核心任务「提问」是三行列表项（HomePage.vue:531-563），描述文字 12px 灰字。`--surface` 对 `--bg` 的层级差仅 **1.10:1**（浅深主题相同）——「面 + 发丝线」被压到肉眼几乎不可辨。

**Deterministic scan（B）**：`impeccable detect` 对 views/app、layouts、components 三目录 exit 0 / 0 发现——**但对照实验证明这是检测器不解析 .vue 的结果**（同样内容存为 .html → 3 条发现；.vue/.tsx/.ts 等 → 0 条），「0 发现」不能作为干净证据（也修正了上一轮评审"灵敏度自证有效"的口径）。浏览器注入（live-server :8400）逐页结果：**/app/member 3 条**（`nested-cards` ×2 为非误报，DOM 已核实；`bounce-easing` 属 Element Plus 库自带＝误报）；其余 5 页 No anti-patterns。

**Visual overlays（B）**：overlay 实际生成并做了几何实测（member 页 banner 526×36 + 2 个标注块 352×77/91），但截图通道间歇不可用，未留下可视截图验证；标签页已还原、无残留注入。

**A/B 裁决**：深色对比度两边一致且均为正面（实测 5.26–15.77:1 全达标；上一轮 2.5:1 缺陷已修复为 `#0e1a18 on #4fb3a4` = 7.05:1）。B 补上了 A 未覆盖的最差点：**浅色 `.st-note` 12px 文本 4.47:1**，略低于 AA 4.5:1。

## Overall Impression

方向正确、执行未兑现。委托人的「单调/乏味」直觉准确，但归因错了一半：问题不是「美术不够强」，而是**唯一差异化资产（量具体系）没有真正落到页面上**——于是用户看到的就是通用卡片流。深色模式则是一份正确的调色板，还不是一种模式。最贵的一处机会浪费：夜醒（真实核心场景）没有任何夜间专属设计。

## What's Working

1. **等待时间被用来讲产品主张**：QaSessionPage.vue:86-100「正在检查内容安全→通过→Agent 生成中（≤8s）」+ SkeletonBlock 的 240ms 延迟策略——不是装饰，是对真实加载分布做的判断，同类里少见的「诚实派」。
2. **深色的色彩正确性实测过关**：120/123 元素仅颜色变化且无一错漏；`--on-accent` 在深色主动翻转为深墨字（tokens.scss:103）。
3. **空态承担教学且分场景**：EmptyState.vue 4 张 96 网格线描（含"空刻度槽"），问答页 hint 同时教「怎么问」与「产品立场（分档呈现、不给定论）」。

## Priority Issues

### [P1] 首屏没有焦点：「问」没有入口，唯一的主按钮属于测评促销
- **What**：首屏唯一 `el-button--primary` 是「开始测评」（HomePage.vue:120），坐在首屏唯一染色面（accent-soft）上；核心任务「提问」是三行列表项，描述 12px 灰字（:594）。
- **Why it matters**：产品定义的成功是「8 秒内拿到贴合月龄的建议」（PRODUCT.md:38）；夜醒家长在首屏拿到的最大视觉指令却是「做测评」。
- **Fix**：首屏还给「问」——一个问题输入面或「描述你的问题」主操作；测评降为普通行；额度/会员卡退到第二屏；首屏只允许一个主色实底。
- **Suggested command**：`$impeccable layout`

### [P1] 「量具」身份在界面上不可感知
- **What**：签名组件 1/26 页在用；报告页四维退化成三格勾选控件；`GraduatedBand` 字样漏进 UI（AssessmentReportPage.vue:76）；风险三档置信度缺席拦截页；首页刻度带自认「纯装饰」；全产品真正的缝合语言是自家文档禁止的彩色左竖条（17 文件 55 处）。
- **Why it matters**：这是产品唯一的差异化资产，也是「乏味」的准确机制——它现在只活在文档里。
- **Fix**：立一条硬规则——任何「处在哪一档/还剩多少/过了多久」都必须由刻度带渲染（月龄/额度/风险置信度/Agent 耗时/四维）；删彩色竖条改「用面」；报告页换真游标带。
- **Suggested command**：`$impeccable shape`

### [P1] 深色模式是换色，不是第二设计
- **What**：实测切主题后 123 个元素中 120 个仅颜色变化、2 个仅阴影 alpha；几何/字号/字重/背景图 0 变化；全项目无任何位图资产（`<img>`=0，public/ 为空）；EmptyState 线描图深浅对比仅 1.66–1.86:1 / 2.21–2.37:1（低于图形建议的 3:1）；深色同时保留纯黑阴影+发丝线（违反 DESIGN.md:230-231「阴影与发丝线二选一」）；无任何"只有夜间才成立"的决定（无夜灯档、无按时间/环境进入、无夜间捷径）。
- **Why it matters**：DESIGN.md:302 与 PRODUCT.md:103 承诺「深色模式完整设计/一等公民，因为夜醒是真实高频场景」——现在它是一份正确的调色板，不是一种模式。
- **Fix**：升级为真正的「夜灯模式」：降低强调色饱和/取消纯白面/字号上浮一档/输入框自动聚焦/给三个夜间一键问题（夜醒/发烧/不肯睡）；关键图形对比度补到 ≥3:1。
- **Suggested command**：`$impeccable colorize`（可配 `$impeccable delight`）

### [P2] 高风险时刻没有被接住（拦截页 + 首次进入页）
- **What**：拦截页整卡全红字（RiskBlockPage.vue:257-283）；6 个危机渠道大多号码为空→渲染成灰「待开通」+灰动作（:50-51, 74）；唯一出口「我知道了」是最弱的 plain 按钮（:83）。首次进入页实测 912px 高、「进入」按钮在 y=815（视口 622），上方是 694px 的 12px 法规正文（StartPage.vue:17-92）。
- **Why it matters**：产品第一原则是「安全先于完整」（PRODUCT.md:100）。拦截页现在读起来像一张错误通知；首见页像一份同意书——而这是唯一能建立信任的时刻。
- **Fix**：拦截页改为「一个面 + 一个红锚点」——说明用中性色，至少保证一个当前一定可用的求助动作（可复制文本，不编造号码），不可用渠道不做成按钮形态；「我知道了」明确次要。首见页改为「先给一句能带走的话 + 一个示例问题」，法规正文折叠到「查看全文」。
- **Suggested command**：`$impeccable harden`

### [P2] 系统状态在说假话
- **What**：(a) 会话过期→首页「数据加载失败/重试」且重试永久失败（HomePage.vue:64-67, 292-296；守卫只看 token 是否存在，router/index.ts:311-315）；(b) 已失效的 `profileUid` 仍被当"当前档案"作答，未建档黄条被 v-if 抑制（QaSessionPage.vue:68, 242）——用户以为在走通用回答，实际按一个不存在的档在回答；(c) `pinned`/`immutable` 写入分节状态但模板从不使用（QaSessionPage.vue:253-254, 446-447），`SafetyBanner` 未接入 → 单领域问答页不成立「安全分节置顶且不可折叠」。
- **Why it matters**：前两条直接损害产品最核心的两条承诺（贴合月龄、安全前置）。
- **Fix**：全局捕获 1101 → 清凭证 + 跳 `/app/start` 并说明原因；档案 uid 与拉取到的列表校验，不匹配即视为未选；问答页接入 SectionCard/SafetyBanner 并真实渲染 pinned。
- **Suggested command**：`$impeccable harden`

## Persona Red Flags

**Casey（移动单手/频繁被打断）**
- 「断点提示已保存」是假承诺：断点存在 `sessionStorage`（HomePage.vue:220-222）却渲染成持久文案（:243）——web-view 销毁即丢失，中断归来看到「开始测评」，而自己明明答了十几题。
- 核心任务没有拇指区按钮：提问靠列表行（y=445），唯一实底按钮属于测评（y=372）。
- 主操作行左侧被永久禁用的语音按钮占住（`title="暂不支持"` 在触屏上永远看不到，QaSessionPage.vue:185-190）；凌晨三点只能打字，无建议问题、无「再问一次」。

**Sam（无障碍/大字体）**
- 12px 是全局说明字号：`var(--fs-caption)` 全仓 **291 处**（含底部 Tab 标签 MobileLayout.vue:165、入口描述、法规正文），直接击穿自家规范「12px 只给免责与时间戳」（DESIGN.md:204）。
- 字号全为 px 常量、无 rem/em（tokens.scss:45-49），「放大 1.2 倍不破」未经检验且结构上脆弱。
- 灰度是唯一意义载体：配额段只有颜色（HomePage.vue:98-104）、拦截页整页红字无第二编码、`st-kpi` 把「0/3」空状态染成最高饱和主色（MePage.vue:58,64，与 DESIGN.md:315 相反）。
- 浅色禁用发送键对比度 1.83:1 且无近旁解释（DESIGN.md:299 要求禁用态必须给理由）。

**Jordan（首次用户）**
- 第一屏是义务不是承诺：「进入」在 y=815/视口 622，上方是 694px 法规文本（StartPage.vue:17-92），首屏没有一句「这能帮你做什么」。
- 术语墙：「MANDATORY · 必须知悉」「SEC-SYS」「实名与伦理双校准已生效」「编号：#CL-A1B2C3D4」「刻度容量：0/6」。
- 会点但不会响的行：MePage.vue:122,135,140 三行与可跳转行 DOM 同构，只有 `@click.prevent` 让它们无声；StartPage 四个协议链接同理。
- 承诺打架：支付页写着「微信支付安全保障 · 支付流程由模拟支付完成」（MemberPage.vue:99）；首页重心「四象测评」的理论映射在 PRODUCT.md:73（Q-06）仍是未决事实。

## Minor Observations

- 间距 token 已与规范脱钩：tokens.scss:51-61 的 `--sp-1..12` 与 DESIGN.md:73-79 无法对应，还出现规范外的 4px/20px，而注释自称「一一对应，禁止未定义档位」。
- 阴影 token 同样脱钩（e1 用 .08 vs 规范 .07；e2 是 4px/12px vs 规范 10px/28px）。
- `.entry-card:first-child` 的 `border-top-color` 解析为 `--accent`（隐藏地雷：一旦加边框宽度就长出彩色分隔线，正好踩 DESIGN.md:308 禁令）。
- 主题开关有两个入口两种形态（首页图标按钮 vs MePage 的 el-switch）。
- `document.title` 变成「家伴 · 家伴」（router/index.ts:23 遇首页 meta.title）。
- 额度表述不对称：首页「剩余 3 次」vs 问答 chip「2/5」（HomePage.vue:107 vs QaSessionPage.vue:63）。
- MePage.vue:78「共 3 份 详情」两段文案粘连。
- `AppealPanel`/`CrisisChannelCard`/`ProfileSwitcher` 三个死件背后是风险与申诉链路各自手搓。
- 安全分节的签名样式未落地：SectionCard 实现为 12px 圆角普通卡、标题色 ink-1，而非 DESIGN.md:286 的「实底铺满整宽、accent-press 标题」。
- 最好的组件（额度抽屉）只由会员页一张「点击预览」演示卡打开。

## Questions to Consider

1. 如果「安全即主色」是最核心的赌注，那主色为什么出现在测评促销卡、额度条、导航选中、小节头竖条和 `0/3` 徽章上？**如果主色只留给安全，首屏会长成什么样？**
2. 凌晨三点打开小程序，**第一眼看到的不是额度表而是"上次那个问题"**，这个页面会变成什么？
3. 整套界面只能保留一个可见的量具元素，它应该落在哪一刻：月龄区间、风险置信度、还是四维分档？
4. 「没有插画、没有 logo、没有品牌资产」——这是一个设计立场，还是资源约束？如果是立场，为什么有 55 处彩色竖条替它说话？

---
target: frontend/src/views/app/（用户端界面）
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:D:\\HomeBud\\frontend\\src\\views\\app"
timestamp: 2026-10-11T11-09-27Z
slug: frontend-src-views-app
---
# 家伴用户端 UI/UX 复评报告（frontend/src/views/app/）

`Method: focused delta pass（对照基线 24/40：2026-10-11T10-29-19Z__frontend-src-views-app.md）`

> **范围**：只复评基线 P1×3 + P2×2 的修复 delta 及其连带面。基线 Minor 10 项按拍板排除，不参与本次计分变化。
> **证据通道**：dev server `localhost:5173` 上 iframe 仿真实测（375×812 与 430×932，浅/深双主题）；`npm run build`（vue-tsc + vite 通过）；全仓 grep 验收（违禁左/右条 = 0）；对比度静态复算与 token 实测。

## Design Health Score（复评 · 对照基线）

| # | 启发式 | 基线 | 复评 | 关键变化 / 残余 |
|---|-----------|-------|-------|-----------|
| 1 | 系统状态可见性 | 3 | **4** | 会话失效全局接管（1101 → 清凭证 + 带原因回 Start）；首页失败态改骨架 + 「提问不受影响」+ 重试不挡主任务；`pinned` 安全分节真实渲染 |
| 2 | 贴合真实世界 | 3 | **4** | 工业英文标签清零（MANDATORY / SAFE-ONLY / CHILD PRIVACY SPECIFICATION / CALIBRATION SYSTEM SCALE 1.0 / DSG-C03 / MVP / “GraduatedBand” 字面，共 7 处）；残余：MePage「#CL-」编号与页脚规格码（低权重） |
| 3 | 用户控制与自由 | 2 | **2** | 拦截页已去「假按钮」（idle 渠道无按钮形状 + 复制求助兜底）；但 MePage 3 行死链、StartPage 4 个协议链接仍为结构外（拍板范围外），扣分项保留 |
| 4 | 一致性与标准 | 2 | **3** | 签名组件 GraduatedBand 1→4 页；ProfileSwitcher 死件接入首页；彩色左竖条 55 处 → 刻度方点；残余：QaSessionPage 内联 `.ai-sec` 与 FamilyQaPage SectionCard 两套回答卡仍共存 |
| 5 | 错误预防 | 3 | **3** | 未动（分层同意 / 退款勾选 / 二次确认 / 幂等保持） |
| 6 | 认得而非回忆 | 3 | **3** | 未动；夜间 chips 小幅加分但不足改档 |
| 7 | 灵活与效率 | 2 | **3** | 建议问题落地：首屏 3 个示例 chips，按对象（孩子/宠物）与主题（白天/夜间）切换，点击即发送；残余：无「再问一次」、禁用语音按钮仍占主操作行 |
| 8 | 美学与极简 | 2 | **3** | 首屏唯一主色实底 = 「问一下」；测评促销降为普通行；深色阴影关闭 + 线稿下限；残余：Me 页同构卡 |
| 9 | 错误识别与恢复 | 2 | **3** | 失败文案具体（「档案与额度暂未同步，提问不受影响」+ 就地重试）；1101 不再无限重试；残余：无字段级内联错误 |
| 10 | 帮助与文档 | 2 | **2** | 未动 |
| **Total** | | **24/40** | **30/40** | **Good（75%）· P1 清零** |

## P1 修复核验（3/3）

### [P1] 首屏还给「问」— 已完成
- **What**：首屏第一块即提问卡（HomePage.vue:48-125）：顶边标尺带 → 范围指示行（对象 + 今日剩余段刻度）→ 输入框 → 主色实底「问一下」→ 示例 chips；测评从 accent-soft 促销大卡降为普通列表行（:128-147），文案诚实化（无断点「16 题 · 约 3 分钟」，有断点「已答 n/16」，不再说「断点提示已保存」）。
- **Evidence**：iframe 375×812 实测首屏含输入框/主按钮/chips，页面横向溢出 = 0；全屏唯一主色实底 = 「问一下」。
- **Residual**：无。

### [P1] 量具落地 — 已完成
- **What**：`.st-section-head::before` 彩色竖条 → 6×6 刻度方点（tokens.scss:529-535）；GraduatedBand 接入 4 页（AssessmentReportPage / ReportImagePage / PetQaSessionPage / RiskBlockPage，基线为 1/26）；报告页四维改真游标带；RiskBlockPage 新增拦截级别带（`tone=danger`，红只染当前档读数与游标）；组件名字面泄漏删除。
- **Evidence**：`grep "border-left|border-right: ≥2px"` = 0 文件；`width: 3-9px` 扫描全部为合法元素（方点/圆点/admin 容忍项）；`npm run build` 通过。
- **Residual**：admin 导航指示条（3px）为已记录容忍项。

### [P1] 夜灯模式 — 已完成（含 1 项已记录的实施偏差）
- **What**：深色不再是换色：字号 +1 档（`--fs-caption 13` / `--fs-sub 15`）；阴影关闭（`--shadow-e1/e2: none`，层级靠发丝线）；线稿专用 token `--art-line`（深色 3.8 / 3.4 / 4.2:1，浅色 3.9 / 3.6:1，均 ≥3:1）；夜间常问三问（夜醒频繁/发烧怎么办/不肯睡，宠物版同理，dark 下自动切换）。
- **Deliberate deviation（记录）**：QA 输入框 dark 下 `autofocus` 跳过 —— 移动端进入即弹键盘会顶掉首屏浏览，改为不自动聚焦、保留清晰焦点态。
- **Evidence**：tokens.scss:112-122；HomePage.vue:263-264/307-312；沿用基线深色实测（5.26–15.77:1 全达标）。

## P2 修复核验（2/2）

### [P2] 高风险时刻被接住 — 已完成
- **What**：RiskBlockPage 整页红 → 单红锚点（stop 图标 danger-soft 底，唯一红；标题/正文回 ink-1/ink-2）+ 拦截级别刻度带（软类别=高风险 1/2，硬类别=危机 5/6，无数据 partial 显示「信息不足」）；idle 渠道不再渲染按钮形状（状态由徽章「暂未开通/接入中」说明）；新增「复制求助信息」兜底动作；「我知道了」降为次级描边。StartPage hero 后新增「一句能带走的话 + 示例问题预告」，法务正文折进 `<details>`（合规文本一字不删），「进入」落回首屏。
- **Evidence**：iframe 实测「进入」按钮 bottom 617 ≤ 812；details 默认收起、展开后 4 协议链接 + 3 条款可达；浅/深双主题带读数与游标颜色实测正确。
- **Residual**：无。

### [P2] 系统状态说真话 — 已完成
- **What**：(a) 全局 1101 处理（request.ts）：有 token 才触发 → 清凭证 → 跳 `/app/start?session=expired`，StartPage 展示「登录已过期，请重新进入」；首页失败态骨架化 + 内联提示 + 重试；(b) 问答页 `profileUid` 挂载校验，失效即回落通用（QaSessionPage:367-369 / PetQaSessionPage:578-579）；(c) `pinned` 分节真实渲染盾牌标识（QaSessionPage:121-134）。
- **Evidence**：iframe 实测失败态与正常态；`npm run build` 通过。
- **Residual**：无。

## 连带解决（基线点名、但不在 5 个优先项内的顺带修复）

1. **工业英文/开发缩写标签 7 处清零**：`MANDATORY · 必须知悉` → 「使用前必读」；`SAFE-ONLY 模式` → 「仅安全建议」；`● CHILD PRIVACY SPECIFICATION` → 「● 儿童隐私保护说明」；`CALIBRATION SYSTEM SCALE 1.0` → 「系统校准版本 1.0」；`MVP 仅支持猫/狗` → 「当前仅支持猫/狗」；`· 构成池 DSG-C03` 删除；`GraduatedBand` 字面 → 真组件渲染。复扫 views/app + components + layouts，剩余大写英文仅为 AI 标识 / SC-26 / ICP / GDPR-CN 等合规码。
2. **ProfileSwitcher 死件接入**：HomePage 范围行 tap → 弹层选对象（基线 3 死件 → 2）。
3. **额度抽屉不再是会员页专属演示**：QuotaDrawer 已由 3 个问答页在 1202（额度用尽）场景触发。
4. **`.entry-card:first-child` 隐藏地雷**：随首页重构删除。
5. **「断点提示已保存」假承诺**：随测评行文案诚实化删除。

## 遗留与记录项（明确不计入本轮修复）

- 假可点死链：MePage 3 行（:122/135/140）+ StartPage 4 个协议链接（现位于 details 内）— 拍板范围外。
- 语音按钮（QaSessionPage:185-190）永久禁用仍占主操作行 — 范围外。
- MePage「编号：#CL-」/「校准：SC-26」等规格码与同构卡 — 范围外。
- 无字段级内联错误、无应用内帮助/检索 — 未动（H10 保持 2）。
- 基线 Minor 10 项：3 项被上述连带修复消除（死件/地雷/额度抽屉），其余保留。
- 基线 B 增量测量点「浅色 `.st-note` 12px 4.47:1」在当前代码不可复现：views/app 内 3 个实例（MePage me-note、RightsCenterPage rt-note、FeedbackPage img-note）均为基类样式 ink-2 on accent-soft = 6.47:1，warn 变体 5.70:1，无 ink-3 文本实例。

## 结论

- **P1 清零、P2 清零**；总分 24 → 30（+6），评级 Acceptable（60%）→ Good（75%）。
- 差异化资产（量具体系）从「只活在 DESIGN.md」变为「4 页真实渲染 + 全站刻度方点语言」；深色从「换色」变为「夜灯五规则」。
- 下一轮提升优先级（如需继续）：H3 假可点控件清理、回答卡实现合一（SectionCard 化 QaSession）、Me 页信息架构与同构卡。

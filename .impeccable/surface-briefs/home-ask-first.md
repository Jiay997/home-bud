# 首页 · 还给「问」（home-ask-first）

> 方向：适度品牌化（2026-10-11 拍板）。约束：不推翻现有量具体系，把它从 DESIGN.md 落进界面。
> 范围：Top 3（首屏还给「问」/ 量具落地 / 夜灯模式）+ P2（高风险时刻被接住 / 系统状态说真话）。Minor 10 项不做。
> 依据：`.impeccable/critique/2026-10-11T10-29-19Z__frontend-src-views-app.md`（24/40）。

---

## 1. 诊断（一句话）

量具设计系统只活在 token 与 DESIGN.md 里：26 个页面中签名组件 GraduatedBand 只用过 1 次，
而全仓 49 处 `.st-section-head::before` 彩色左条 + 若干 3–6px 色条，成了页面间的「视觉连接组织」。
于是「家伴」看起来像任何一张模板：一堆等大圆角卡片 + 顶部一根绿条。

## 2. 首屏结构（375×812 基准；430 上限）

```
┌───────────────────────────────┐
│ 家伴           [◐主题] [◯我的] │  品牌行（压缩：无独立卡，header 高度 56px）
├───────────────────────────────┤
│ ● 当前对象 · 宝宝A · 14个月   │  范围指示行（tap → ProfileSwitcher 弹层）
│ ────────────────────────────  │  范围行底边 = 1px 基准线（量具零线）
│ 今天可以问点什么               │
│ ┌───────────────────────────┐ │
│ │ 孩子夜里频繁醒、接觉难…     │ │  提问输入框（textarea 1 行起）
│ └───────────────────────────┘ │
│ [ 问一下 ]                     │  全屏唯一主色实底按钮
│ [夜里频繁醒] [猫哈气] [揪猫尾巴]│  示例 chips（点击直接发送）
├───────────────────────────────┤
│ 今日剩余 3/5  ▮▮▯▯▯           │  额度行（并入基线行，不独立成卡）
├───────────────────────────────┤
│ ▸ 四象宝宝气质测评   开始/继续 │  紧凑行（非主卡）
│ ▸ 0-6岁宝宝养育               │
│ ▸ 猫狗宠物饲养                │
│ ▸ 家庭综合问答                │
├───────────────────────────────┤
│ 会员权益（次级，plain 按钮）    │
└───────────────────────────────┘
```

- 首屏（812px）内必须完整看到：brand 行 / 范围行 / 输入框 / 「问一下」/ 示例 chips。
- 首屏唯一实底主色元素 = 「问一下」。
- 输入框上方一条 8px 标尺装饰带（复用 ReportImagePage `.ruler-band` 语汇：1px 竖刻度
  @8px 周期，`--line` 色）。这是「器械物件」签名第一次出现在进入路径上。

## 3. 交互规格

### 3.1 提问发送
- 输入为空 → 「问一下」禁用（`disabled`，Alpha 降但保留形状，不消失）。
- 回车 / 点击 → 按**当前对象**路由：
  - 孩子档案 → `/app/qa/parenting?q={encodeURIComponent(文本)}`
  - 宠物档案 → `/app/qa/pet?q=…`
  - 无档案（通用回落）→ `/app/qa/parenting?q=…`（QA 页已有「通用 1-3 岁」黄条兜底）
- 示例 chips 与输入等价：点击即发送对应问题（直接跳转）。

### 3.2 `?q=` 交接协议（QA 页侧）
- parenting / pet 两页 `onMounted` 读取 `route.query.q`；
- 命中 → `prefill + auto-ask once`（复用既有 `ask()`，重构为接受文本参数）；
- 立即 `router.replace` 去掉 query（防止返回键重发）；
- 全程无 query 时行为与现状完全一致（不影响深链外的任何入口）。

### 3.3 范围指示行（当前对象）
- 内容：`● {昵称} · {月龄/物种}`；未建档 → `● 通用 1-3 岁参考`（中性 ink-2，不吓唬人）。
- 右侧：`今日剩余 n/m` + 迷你段刻度（沿用首页 quota 段刻度语汇，12 段以内直显，>12 段只显数字）。
- tap → 打开 `ProfileSwitcher`（已存在、0 引用的组件）→ 选中后 `user.setCurrentProfile(uid)`。
- ProfileSwitcher 空档案态：提示去建档，不弹空对话框。

### 3.4 测评降级（诚实文案）
- 从 accent-soft 大卡降为**普通列表行**（与三大入口同一容器分节）。
- 文案说真话：
  - 无断点：`四象宝宝气质测评 · 16 题` + 「开始」
  - 有断点未答满：`已答 n/16` + 「继续」（不再说「断点提示已保存」——sessionStorage 清失即真）
  - 答满：`查看报告`
- 保留 `goAssessment()` 逻辑不变。

## 4. 器械物件线稿词汇表（新签名，全站只准这样画小图形）

- 网格 24；描边 1.75（大图 2）；`fill="none"`；色用 `currentColor`；圆头只在短线端出现。
- 允许的「物件」：**标尺**（竖刻度带）、**刻度槽**（trough）、**游标**（cursor 点）、**档位段**、
  **零线**（1px 基准线）、**基点**（6×6 刻度方点，继承 FamilyQaPage `.ac-badge` 既有模式）。
- 禁止：emoji / Unicode 字符充当图标（■ ▲ ◆ 一律删）；彩色 >1px 左/右条；装饰性渐变；
  进度百分比填充条假装刻度（改用「档位 + 游标」）。
- 签名时刻（渲染在意的两个位置）：首屏提问卡标尺带；报告长图顶/底标尺带（已存在）。

## 5. 量具三处落地（历史欠账偿还）

| 位置 | 现状（违禁） | 改为 |
|---|---|---|
| `tokens.scss` `.st-section-head::before` | 3px 彩色竖条 × 49 处 | 6×6 `--radius-1` 刻度方点（`--accent`，静态不悬停） |
| `AssessmentReportPage.vue` `.band-track` | 3 格选择器（低/中/高），transition:all | `GraduatedBand` + `partial` 支持；游标档位跳变（reduced-motion 直切） |
| `ReportImagePage.vue` `.st-meter__fill` | 25/55/85% 假进度条 | 刻度槽 + 游标（档位化 three-position snap） |
| `AssessmentReportPage.vue` `.ib-bar` ×3 | 6×14 彩条 | 刻度方点 |
| `AssessmentReportPage.vue` :76 | "GraduatedBand" 英文字面泄漏 | 删除，换「四维行为倾向刻度」 |
| `ReportImagePage.vue` :30 | "■ 标定校准协议" | 删 ■，换刻度方点 SVG |
| PetQaSessionPage / HistoryDetailPage / ConsentModal `::before` | 3px 彩条 | 同款刻度方点 |
| RiskBlockPage 风险 tier | 无档位呈现 | 档位=severity 的 GraduatedBand 语义（红仅为当前档，不是整条） |

验收：`grep -rn "st-section-head" frontend/src` 后无 3px；页面级彩色左条 = 0（admin 导航指示条保留并记录为容忍项）。

## 6. 夜灯模式（dark 不是换色）

- 只动 `html.dark` 作用域，不加第三主题：
  1. **字号 +1 档**：`--fs-caption 12→13`、`--fs-sub 14→15`（夜间阅读下限）；
  2. **阴影关闭**：`--shadow-e1/e2: none`（DESIGN.md：阴影与发丝线二选一，夜间靠线）；
  3. **线稿对比 ≥3:1**：EmptyState / 装饰刻度线换 `--art-line` 专用 token（两主题各自测量）；
  4. ~~QA 输入框 dark 下 `autofocus`~~ **（实施决策：跳过）** 移动端进入即弹键盘会顶掉整页首屏浏览，
     自动聚焦在 WebView 下打断「先看再问」；改为不自动聚焦，仅保留清晰的可聚焦态；
  5. 夜间常问三问（首页 chips dark 变体）。
- 验收：对比度脚本两主题全绿；截图对比 light/dark 差异是「重排 + 重标」不是仅色相。

## 7. DESIGN.md 修订清单（任务 #11）

1. 新增「线稿词汇」节（本文件 §4 内容）。
2. `.st-*` 兼容层定位：明确 `st-*` 为 Stitch 稿迁移过渡层，新代码不得新增 `st-` 前缀。
3. 夜灯模式规则（§6）。
4. 「刻度基元」三件套定义：刻度方点 / 刻度槽+游标 / 标尺带。
5. 容忍项记录：admin 导航指示条 3px 保留。

## 8. 高风险时刻（任务 #14 · clarify）

- RiskBlockPage：整页红 → **一个红锚点**（stop 图标保持 danger），标题/描述回 ink-1/ink-2；
  渠道 idle 态去按钮形状（改纯文本行 + 「暂未开通」），「复制求助信息」为兜底可点操作；
  ack 按钮降为次级描边。
- StartPage：hero 后插入「一句能带走的话」+ 示例问题预告；法务正文折进 `<details>`
  （合规文本不删）；「进入」按钮须落在首屏 812px 内。

## 9. 系统状态说真话（任务 #13 · harden）

- `request.ts` 全局 1101：清 token → 跳 `/app/start?session=expired`；StartPage 读 `session` 查询参数展示「登录已过期，请重新进入」提示条。
- HomePage `loadFailed` 重试环：1101 场景由全局处理接管；普通网络失败保留重试但复用骨架（不再裸文本卡）。
- QaSessionPage：`profileUid` 挂载时校验（不在 children 列表 → `setCurrentProfile(null)` + 回落通用）；`sec.pinned` 渲染为 `.ai-sec--pinned`（SafetyBanner 语义）。

## 10. 假设与显式排除

- 假设：后端接口不改（本任务纯前端）；`?q=` 仅新加 query 消费端，无新接口。
- 排除（Minor 10 项）：Avatar 组件化、字体子集统计、Skeleton 变体等 — 出范围。
- 验证手段：contrast 脚本 + `npm run build` + iframe 375×812 仿真（E2E 环境限制见记忆）
  + `$impeccable critique` 复跑对比 24/40。

---

## 11. 完成状态（2026-10-11 收口）

- **5 项全部落地**：首屏还给「问」/ 量具落地 / 夜灯模式 / 高风险时刻 / 系统状态说真话；连带清零工业英文标签 7 处，`ProfileSwitcher` 接入首页，`QuotaDrawer` 三问答页 1202 触发。
- **实施偏差 1 项**（已记录）：§6 第 4 条 QA 输入框 dark 自动聚焦跳过（见该节实施决策）。
- **复评**：`$impeccable critique` 24 → **30/40**（Acceptable 60% → Good 75%，P1/P2 清零），报告 `.impeccable/critique/2026-10-11T11-09-27Z__frontend-src-views-app.md`；验收细节见 `docs/测试报告_全面模拟测试_2026-10-09.md` §7.12。
- **遗留（范围外记录）**：MePage 假可点死链 / StartPage 协议链接（`javascript:void(0)`）改真链接或纯文本；问答页禁用语音按钮；回答卡两套实现合一；真机暗色截图轮。
- 设计系统侧：`docs/03-设计/DESIGN.md` 已补线稿词汇、刻度基元三件套、夜灯规则与 GraduatedBand `tone` 契约。

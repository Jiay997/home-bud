---
name: Babe宝伴｜AI 多智能体，家庭养育科普参考工具
description: 量具刻度系统。每一次判断都落在一条有刻度的带上，并标出它落在哪一档。
colors:
  accent: "#0A6B60"
  accent-press: "#074E46"
  accent-soft: "#E1EFEC"
  accent-line: "#8FBFB7"
  on-accent: "#FFFFFF"
  ink-1: "#0F1E1C"
  ink-2: "#455754"
  ink-3: "#5F6F6C"
  bg: "#F2F5F4"
  surface: "#FFFFFF"
  surface-2: "#E9EFED"
  line: "#D5DEDB"
  line-strong: "#B4C3BF"
  danger: "#A8231B"
  danger-soft: "#F7E4E2"
  warn: "#7A5600"
  warn-soft: "#F6EDD8"
  dark-bg: "#0C1614"
  dark-surface: "#13201E"
  dark-surface-2: "#1B2A27"
  dark-ink-1: "#E8EFEC"
  dark-ink-2: "#AEBFBB"
  dark-ink-3: "#93A5A1"
  dark-accent: "#4FB3A4"
  dark-accent-soft: "#16332E"
  dark-danger: "#E8776D"
  dark-warn: "#DCB25C"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, HarmonyOS Sans SC, Noto Sans CJK SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, HarmonyOS Sans SC, Noto Sans CJK SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, HarmonyOS Sans SC, Noto Sans CJK SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  sub:
    fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, HarmonyOS Sans SC, Noto Sans CJK SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, PingFang SC, HarmonyOS Sans SC, Noto Sans CJK SC, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  numeric:
    fontFamily: "ui-monospace, SF Mono, Cascadia Mono, Consolas, monospace"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
rounded:
  control: "8px"
  surface: "12px"
  full: "999px"
spacing:
  s0: "6px"
  s1: "8px"
  s1b: "10px"
  s2: "16px"
  s3: "24px"
  s4: "32px"
  s5: "48px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 24px"
  button-primary-hover:
    backgroundColor: "{colors.accent-press}"
  button-primary-disabled:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink-3}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 24px"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.danger}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 24px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-1}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 16px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    height: "22px"
    padding: "0 10px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-1}"
    rounded: "{rounded.surface}"
    padding: "24px"
  safety-section:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.ink-1}"
    padding: "24px"
---

# Design System: Babe宝伴｜AI 多智能体，家庭养育科普参考工具

## Overview

**这一套界面是一支量具。** 每一次判断都落在一条有刻度的带上，并标出它落在哪一档：月龄是区间，气质维度是三档而不是唯一类型，风险是置信度分档，免费额度是剩余次数，审核时限是时长。产品不说"你是哪一类"，只说"你现在在哪一段、离安全线还有多远"。

这条主张来自使用现场，不是审美偏好：家长一手抱娃、碎片时间、**深夜低光**（夜醒是核心提问场景）、情绪可能濒临崩溃。因此设计要解决的是"在低光与单手条件下，能不能一次看清自己处在什么位置"。

品类默认（粉与奶油底、糖果圆角卡片、大幅插画、emoji、三张等大功能卡）和它的反面（冷灰金融后台、纯表格、无温度）都被明确拒绝。本系统属于 **Operate** 模式：熟悉度是特性，界面应当消失在任务里；品牌表达只活在精确的细节中。

当前实现为一份自包含的样式瓦片：`宝伴-设计系统样式瓦片.html`（单文件、无构建、无外部字体、无 JS 依赖）。**本文档的 token 是规范层，样式瓦片是它的可视证据。**

## 核心页面叙事：家庭观察档案

首页、问答与测评报告共享“家庭观察刻度”记忆点，但各自承担不同任务，不把同一张卡片模板复制三遍：

- **首页｜此刻观察**：提问是首屏主舞台；档案选择与额度是读数，测评入口作为错位的档案索引，其他问答入口退为线性目录。
- **问答｜过程记录**：当前对象固定在上方，问题以观察条目呈现，回答按服务端分节渐进展开；置顶安全内容仍以完整实底呈现，输入保持拇指可达。
- **测评报告｜阶段回看**：结论作为档案封面，四维刻度带提供读数，养育建议以编辑式分节展开；非宿命声明、AI 标识和服务端会员门控始终保留。

非对称只用于建立阅读顺序，不让正文倾斜或难以扫读。首阶段不加载外部图片，使用既有线稿、标尺带、留白、实底和层叠边界形成识别；动效克制，并遵守减少动态效果设置。

## Colors

克制策略：一套向主色偏移的冷中性 + 一个强调色 + 一组只服务于状态的语义色。中性色不用纯灰，否则强调色会显得像贴上去的。

### Primary

| token | 值 | 用途 | 对白对比度 |
| --- | --- | --- | --- |
| `accent` | `#0A6B60` | 主操作、当前选中、**安全提示** | 6.4:1 |
| `accent-press` | `#074E46` | 主操作按下 / 悬停 | 9.0:1 |
| `accent-soft` | `#E1EFEC` | 安全分节实底 | — |
| `accent-line` | `#8FBFB7` | 次级按钮描边 | — |
| `on-accent` | `#FFFFFF` | 主操作文字 | 6.4:1 |

### Secondary

危险与注意不是"第二个强调色"，而是**只在刻度与状态内部出现的语义层**：

| token | 值 | 用途 | 对白对比度 |
| --- | --- | --- | --- |
| `danger` | `#A8231B` | 风险拦截、危险操作、越过安全线 | 7.2:1 |
| `danger-soft` | `#F7E4E2` | 阻断面顶部实底 | — |
| `warn` | `#7A5600` | 降级、额度用尽、审核中、占位 | 6.6:1 |
| `warn-soft` | `#F6EDD8` | 冲突标注、降级条实底 | — |

### Neutral

| token | 值 | 用途 | 对白对比度 |
| --- | --- | --- | --- |
| `ink-1` | `#0F1E1C` | 标题与正文 | 17.2:1 |
| `ink-2` | `#455754` | 次级文本、区间说明 | 7.5:1 |
| `ink-3` | `#5F6F6C` | 免责小字、时间戳 | 5.3:1 |
| `bg` | `#F2F5F4` | 页面底 | — |
| `surface` | `#FFFFFF` | 内容面 | — |
| `surface-2` | `#E9EFED` | 第二中性层：刻度槽、工具栏、表格悬停、下沉地面 | — |
| `line` | `#D5DEDB` | 发丝线 | — |
| `line-strong` | `#B4C3BF` | 输入框描边、刻度标尺、滚动条 | — |

### Named Rules

- **安全即主色。** 安全提示使用 `accent`，不另设"安全色"。安全是这个产品的身份，不是又一个警告色。这条是本系统最核心的赌注。
- **免责小字也是正文。** `ink-3` 仍须满足 4.5:1（实测 5.3:1），因为它承担合规作用，不是可读性可以打折的装饰文字。
- **会员没有颜色。** 付费门控靠"正文被裁掉"与下沉地面表达。任何给会员配专属色（金、紫）的做法都会与安全/合规元素争夺颜色语义。
- **语义色不上装饰。** `danger` / `warn` 只允许出现在刻度、状态标签、实底提示面内部；不得用于边框装饰、图标点缀或强调标题。

## Typography

**一套字就够。** 产品界面不需要标题字体与正文字体的配对。这里是中文产品且运行在微信小程序中，而**小程序不加载远程字体**（CJK 字体体积与平台限制），因此正确做法是系统中文字体栈，而不是硬塞网络字体。

### Hierarchy

| 角色 | px | rpx | 字重 | 行高 | 用途 |
| --- | --- | --- | --- | --- | --- |
| display | 23 | 46 | 600 | 1.3 | 页面主标题、问题原文 |
| title | 19 | 38 | 600 | 1.3 | 卡片标题、分节标题 |
| body | 16 | 32 | 400 | 1.6 | 回答正文（**下限**） |
| sub | 14 | 28 | 400 | 1.6 | 次级说明、字段名 |
| caption | 12 | 24 | 1.5 | 400 | 免责小字、时间戳 |
| numeric | 16 | 32 | 400 | 1.6 | 刻度读数、金额、耗时 |

字号比值 1.2，固定 rem，不用流体缩放：产品在固定 DPI 下使用，会缩放的标题在侧栏里只会更糟。正文测度控制在 65–75 字符（约 30–36 汉字）。

### Named Rules

- **12px 只给免责与时间戳。** 不得用于交互文案或按钮。
- **数字一律 tabular。** 刻度读数必须纵向对齐才能被扫读：`font-variant-numeric: tabular-nums`，`font-feature-settings: "tnum" 1`。
- **等宽字体只用于真正的代码与标识。** 知识库 ID、会话 ID、文案 ID、正则规则。不拿它当"技术感"的装饰。
- 若后续获得可商用数字字体授权，只替换 `numeric` 的 `fontFamily`，不动结构。

## Layout

- **小程序**：基准 375×812，向上适配至 430；单位 `rpx`（750rpx = 屏宽）；输出 2 倍图。页边距 32rpx，卡片间距 24rpx，卡片内边距 32rpx。顶部状态栏 88rpx（含胶囊避让），底部安全区 + Tab 112rpx。
- **后台**：1440×900；侧边导航 240px，内容区最大宽度 1200px 居中；允许表格 120ch 以上的密集排布。
- **响应式是结构性的**：折叠侧栏、表格降列、断点驱动列数，不用流体字号去解决。
- **间距用 4 的倍数**（6 / 8 / 10 / 12 / 16 / 24 / 32 / 48），刻度的周期固定 8px 且不随容器拉伸。因此刻度、内边距与栅格同源，而不是一张装饰纹理。
- **单手可达**：主操作（发送、保存、继续）位于下半屏热区（≥88rpx）；危险操作（删除、注销、撤回）二次确认，且不放在拇指惯性点击区。

### 微信小程序端适配

- 首页、问答、测评与报告共用自定义导航头；状态栏高度由 `uni.getSystemInfoSync()` 获取，右侧按微信胶囊位置留白。辅助 API 不可用时回退到标准 20px 状态栏与默认右侧间距。
- 四页均使用小程序自身滚动与触控布局，不复用 H5 的导航与视口尺寸。当前小程序未配置 TabBar；在档案、记录、我的页面实现前，不展示无效底部入口。
- 页面次级说明以 12px 为最低可读字号基线（rpx 按设备宽度换算）；首屏关系图谱节点与对象选择控件提供至少 44px 的可触控面积，并以文字同步标出当前观察对象。
- 模拟器是首轮布局基准，真机用于最终校验状态栏/胶囊、安全区、字体与触控。微信开发者工具运行失败时，不得以 H5 预览截图代替小程序验收。

## Elevation & Depth

平面优先。卡片由 **面 + 发丝线** 定义，不由阴影定义。阴影只给真正浮起的东西。

### Shadow Vocabulary

| token | 值 | 用途 |
| --- | --- | --- |
| `e1` | `0 1px 3px rgba(15,30,28,.07)` | 吸顶栏、需要脱离页面的卡片 |
| `e2` | `0 10px 28px rgba(15,30,28,.12)` | 弹层、底部面板、抽屉 |

### Named Rules

- 阴影必须带偏移与柔和模糊，并**向背景色相偏移**（用青灰而非纯黑）。零偏移的彩色光晕是装饰，不是高度。
- 一张卡片同时有阴影和发丝线是重复表达，二选一。

## 夜灯（Dark）

深色不是浅色的换色，是**为深夜低光场景重新排的版**（夜醒是核心提问场景）。两主题共享同一套结构与组件，差异只允许发生在 `html.dark` 作用域，且必须是有理由的：

1. **字号 +1 档**：`--fs-caption` 12→13、`--fs-sub` 14→15。夜间阅读距离更远、瞳孔更大，小字先失守。
2. **阴影关闭**：`--shadow-e1/e2: none`。夜间靠发丝线分离层级——阴影与线二选一，这条在两个主题里都成立。
3. **线稿有独立下限**：装饰性线条（空态插图、刻度带装饰）用 `--art-line` token，两主题各自测量，**对比度 ≥3:1**；正文仍守 4.5:1。
4. **夜间常问三问**：首页示例 chips 在 dark 下切换为夜间场景问题（夜醒/发烧/呕吐类），浅色下为白天场景。这是内容层的重排，不是颜色层。
5. **不自动聚焦**：任何页面进入时都不弹输入法键盘，夜灯下也一样。用户先看清页面，再决定开始打字。

## Shapes

| token | 值 | 适用范围 |
| --- | --- | --- |
| `rounded/surface` | 12px | 卡片、弹层、面板、手机标本框 |
| `rounded/control` | 8px | 按钮、输入框、标签、色块、焦点环 |
| `rounded/full` | 999px | **仅**头像、图标按钮、刻度槽与填充段 |

这是一套**有文档的混合系统**，不是一个随手的圆角集合：面用 12，控件用 8，圆形只给语义上真的是圆的东西（人像、刻度槽）。禁止第三个圆角值出现在面或控件上。

## 线稿（Iconography）

界面里的每一个小图形都用同一套线描语言画出来，像一本仪器的说明书插图：

- **网格 24**；描边 **1.75**（大图为 2）；`fill="none"`；颜色一律 `currentColor`（让语境决定颜色，线稿自己不配色）；圆头圆角只出现在线段端。
- 允许画的「物件」只有量具世界的词汇：**标尺**（竖刻度带）、**刻度槽**（trough）、**游标**（读数点）、**档位段**、**零线**（1px 基准线）、**刻度方点**。画不出合适合法的物件时，留白，不硬画。
- 禁止：emoji 或 Unicode 字符充当图标（■ ▲ ◆ 一律删）；装饰性渐变；进度百分比填充条假装刻度；外部插图与插画。
- **签名时刻**（线稿与标尺被刻意展示的两个位置）：首屏提问卡顶边的标尺带；报告长图顶/底边的标尺带。

## Components

每个可交互组件必须有完整周期：default / hover / focus / active / disabled / loading / error。禁用态**必须在近旁给出原因**，不能只把按钮变灰。

> **样式兼容层（`st-*`）**：`st-card` / `st-section-head` / `st-tag` 等是 Stitch 稿迁移期的过渡类，定义在 `styles/tokens.scss`。它们现在统一使用刻度方点标记，视觉已归化进本系统；但**新代码不得新增任何 `st-` 前缀类**，等价能力一律走组件或既有类。兼容层清退随组件化推进自然发生。

### Buttons

- 主按钮：实底 `accent`，白字，圆角 8，高 44px，内边距 0 24px。按下 `accent-press` 并 `translateY(1px)`。
- 加载态：保留可读文案（**绝不把文字设为透明**），转圈用 `currentColor`，因此对比度永远达标。
- 次级按钮：透明底 + `accent-line` 描边 + `accent` 文字；悬停转 `accent-soft` 底。禁用时不得继承悬停底色。
- 危险按钮：透明底 + `danger` 描边与文字，仅用于不可恢复操作。

### Chips

高 22px，圆角 8，透明底 + `line-strong` 描边 + `ink-2` 文字。语义变体用对应语义色描边与文字。状态用标签表达，**不给整行染色**。

### Cards / Containers

`surface` 底 + `line` 发丝线 + 12px 圆角。回答卡由若干**分节**组成，分节之间用 1px 分隔线，不用嵌套卡片（嵌套卡片永远是错的）。

### Inputs / Fields

高 44px，8px 圆角，`line-strong` 描边，16px 字号。标签在输入框**上方**；帮助文字在下方；错误文字在下方并带图标。占位符不得充当标签。错误必须说清问题与恢复方式（例："身高应在 40–140 cm 之间。请检查是否多输了 0。"）。

### Navigation

小程序为底部四 Tab（首页 / 档案 / 记录 / 我的），后台为左侧导航。选中态不得只靠颜色，必须同时有图标或字重变化。导航高度后台 ≤80px。

**唯一的竖条容忍项**：后台侧栏导航当前项保留 3px `accent` 位置指示条（左侧、上下各缩进 9px）。它是「你在哪里」的位置标记而非装饰，且不发生在小程序品牌面；除它以外，全仓任何彩色竖条/左边框 ≥2px 均属违规（含 `::before` 伪元素与实底块）。

### 刻度基元（三件套）

全站所有「标记与量度」都只能由这三个基元拼成，不允许第四个：

1. **刻度方点**——6×6px、圆角 1px。默认 `accent` 实底；出现在正文内容内部作次要要点时可用 `ink-3`（保持安静）。**在小程序界面内，它是分节标题、列表要点、状态条目的唯一标记**；与文字同排时垂直居中对齐（`gap` 5–8px），多行文本中 `margin-top ≈ 0.65em` 对齐首行。禁止再用 3–6px 彩色竖条做任何标记。（后台管理界面沿用各自表格的圆点状态惯例，不在此约束内。）
2. **刻度槽 + 游标**——槽为 12px 高全圆角 `surface-2` 带；游标为 22px 圆形读数点（`accent` 实底、3px `surface` 描边、**上下各越出槽体 5px**，因此槽不得 `overflow:hidden`）。档位边界用 1px × 5px `line-strong` 竖刻度标出，档位名居中于各自区段。这是 `GraduatedBand` 的实现。
3. **标尺带**——8px 一排的 1px 竖刻度（`repeating-linear-gradient`，`--line` 或 `--line-strong`），宽度不随容器拉伸。用作签名装饰：首屏提问卡顶边、报告长图顶/底边。它是刻度，不是纹理，别处不得滥用。

### GraduatedBand（签名组件）

**这是全系统的签名。** 结构四层：读数行（维度名 + 档位读数，如「中等」）→ 分区刻度层（档位边界 + 居中档位名）→ 刻度槽 → 游标。信息不足时（`partial`）游标缺席、读数沉为 `ink-3`「信息不足」——**没有读数就不假装有读数**。组件契约：`bands`（档位名，低→高）/ `value`（0–1 归一落点）/ `label`（维度名）/ `partial`（信息不足态）/ `levelLabels`（读数口径覆盖，如「低倾向」）/ `tone`（`accent` 默认 ｜ `danger`：红只染当前档读数与游标，不染整条）。

| 用途 | 档位 | 读数示例 |
| --- | --- | --- |
| 月龄区间 | 0–6 月 / 6–12 月 / 1–3 岁 / 3–6 岁 | 24 个月 · 1–3 岁 |
| 维度分档 | 低 / 中 / 高 | 每维三档，不给精确分数 |
| 拦截级别（风险拦截页） | 关注 / 高风险 / 危机 | 软类别「高风险」；硬类别「危机」（`tone=danger`，无匹配数据时 `partial`） |
| 风险置信度 | <0.5 放行打标 / 0.5–0.8 拦截+引导 / >0.8 直接拦截 | 0.61 · 灰区 |
| 免费额度 | 5 段（剩余段实底） | 剩余 3 / 5 次 |
| 时限 | 按比例填充 | 已过 7h / 24h |

**规则**：① 长度即数值，不用装饰性进度条；② 不出现精确分数与绝对类型；③ 语义色只在刻度内部使用（如风险档位红仅为当前档，不是整条）；④ `prefers-reduced-motion` 下在命名档位间跳变，不做插值动画（全局降级规则见 tokens.scss）；⑤ 必须带可读的数值与 `aria-label`，不靠颜色单独表意。

### Section（回答卡内的分节）

安全分节**置顶、实底铺满整宽、不可折叠**，使用 `accent-soft` 底与 `accent-press` 标题色。**不设左侧色条**：用面，不用线。其余分节依次为育儿侧、宠物侧，每节带图标、标题与耗时。

### LockedBlock（付费门控）

不做灰罩、不做条纹。付费墙表现为**下沉地面**（`surface-2` 底）露出，内容只保留标题与淡出的预览摘要，加一个解锁入口。真实实现由服务端裁剪正文，前端不做安全边界。

## Do's and Don'ts

### Do:

- 用 `GraduatedBand` 表达任何"处在哪一档 / 还剩多少 / 过了多久"。
- 行内标记一律用刻度方点（6×6，圆角 1px），分节、要点、状态条目同一制式。
- 安全提示用主色实底，且置顶、不可折叠。
- 每个空态都教界面：说明建档后能得到什么，并给一个主操作。
- 用骨架屏承载渐进渲染，形状与最终布局一致。
- 让禁用态在近旁解释原因。
- 主题化浏览器自带的那一层：选中底色、光标、滚动条、焦点环、下划线偏移、表格数字。
- 深色模式完整设计，因为夜醒是真实高频场景。

### Don't:

- 不给会员配专属色；不用金色或紫色表达付费。
- 不用 emoji 或 Unicode 字符充当图标；图标一律为绘制的 SVG，单一描边 1.75、24 网格。
- 不在卡片、列表项、提示条上使用彩色左边框/右边框或 ≥2px 的彩色竖条——包括 `::before`/`::after` 伪元素画出来的。唯一例外是后台侧栏导航的 3px 位置指示条（见 Navigation）。
- 不用渐变文字、不用玻璃模糊做装饰、不用硬偏移阴影。
- 不在标题上方加小标签（kicker / eyebrow），标题自己承担重量。
- 不用精确分数或绝对类型描述孩子：这是产品原则，也是免责要求。
- 不在产品界面里暴露可见的构造栅格；栅格只以刻度的形式出现。
- 不用屏幕中央的转圈替代骨架屏；不让加载态把文字设为透明。
- 不在风险拦截页出现任何建议性文本；不编造危机求助渠道号码。
- 不给隐藏状态的按钮保留饱和强调色。

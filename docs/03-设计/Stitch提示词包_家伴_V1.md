# 小光景 × Google Stitch 提示词包 V1

> **依据**：`家伴-UI原型描述_V1.3.md`（34 页唯一界面基线）+ `DESIGN.md`（视觉 token 真源）
> **用途**：在 https://stitch.withgoogle.com 生成高保真视觉稿（对应 §10.1 交付物第 4 项）
> **覆盖**：小程序 26 屏（SC）+ 后台 Web 8 屏（PA）+ 全局风格 + 状态补丁 + 走查清单

---

## 0. 使用前必读（5 条）

1. **Stitch 一次生成一屏**（Standard 模式）。先把 §2「全局风格提示词」作为第一条消息发送定基调，之后逐屏贴第 4/5 章的屏幕提示词，风格会自动延续。
2. **提示词主体用英文**（Stitch 对英文响应更稳），但要渲染的**中文界面文案用引号包住**写进英文句子里（如 the title "育儿问答"），Stitch 会按引号内原文渲染。
3. **每条提示词后用迭代指令修偏差**，不要指望一条到位。签名组件刻度带（GraduatedBand）通常要迭代 2–3 次；§6.7 列了常见偏差的一键修法。
4. **先填 Theme 面板再生成**（右上角主题设置）：Primary `#0A6B60`、Surface `#FFFFFF`、Background `#F2F5F4`、Text `#0F1E1C`；字体选 Noto Sans SC（或思源黑体，最接近 PingFang SC 的可选项）。
5. **Stitch 不擅长**：精确像素还原、一次出完整状态矩阵、暗色模式并行。状态与暗色用 §6 的补丁指令逐屏补；导出 Figma 后再精修。

**建议生成顺序**（P0 核心十屏先行，其余按需）：
SC-02 首页 → SC-08 育儿问答 → SC-11 回答卡 → SC-12 风险拦截 → SC-03 档案列表 → SC-04 儿童档案 → SC-16 测评报告 → SC-20 会员 → SC-23 个人中心 → SC-01 启动页，再补 SC-05~07、09~10、13~15、17~19、21~22、24~26 与后台 8 屏。

---

## 1. 主题设置（Theme 面板手填）

| 项 | 值 |
| --- | --- |
| Primary / 按下 | `#0A6B60` / `#074E46` |
| Background / Surface / Surface-2 | `#F2F5F4` / `#FFFFFF` / `#E9EFED` |
| 文字三级 | `#0F1E1C` / `#455754` / `#5F6F6C` |
| 强调辅助 | soft `#E1EFEC`、line `#8FBFB7`、发丝线 `#D5DEDB` |
| 语义色 | danger `#A8231B`（soft `#F7E4E2`）、warn `#7A5600`（soft `#F6EDD8`） |
| 字体 | Noto Sans SC（系统中文栈的最接近替代） |

---

## 2. 全局风格提示词（第一条消息，发一次）

```text
Design a high-fidelity mobile UI for "小光景 (JiaBan)", a Chinese parenting & pet-care AI
assistant (WeChat mini-program style, 375x812) for parents aged 25–40 who often use it
one-handed at night.

Design personality: a precision measuring instrument — calm, trustworthy, clinical but
humane. Strictly avoid the typical pink/pastel parenting-app look: no candy cards, no
cute mascot illustrations, no emoji icons, no gradients, no glassmorphism, no colored
left borders, and NEVER gold or purple for membership elements.

Colors (light theme): page background #F2F5F4; cards #FFFFFF defined by fill + 1px
hairline border #D5DEDB (flat, minimal shadows); primary ink #0F1E1C, secondary #455754,
tertiary #5F6F6C; accent teal #0A6B60 for primary buttons, selection AND safety
highlights (safety IS the brand color); soft teal #E1EFEC for solid safety section
fills; danger #A8231B and amber #7A5600 used ONLY inside risk/gauge/status elements;
secondary surface #E9EFED.

Typography: Chinese system sans (PingFang SC / Noto Sans SC). Page titles 23px
semibold, card titles 19px semibold, body 16px line-height 1.6 (never smaller),
secondary 14px, disclaimer captions 12px. All numerals tabular monospace.

Shape: cards 12px radius; buttons, inputs and chips 8px radius, 44px tall. Icons are
thin-line SVG style, 1.75 stroke, never emoji.

Signature component "GraduatedBand", used everywhere a range or grade is expressed
instead of scores: a horizontal gauge with a fine tick ruler on top (small ticks,
regular period), a 10px fully-rounded track below with the filled portion in accent
teal, thin vertical dividers inside the track marking grade boundaries, a 2px vertical
cursor needle extending slightly beyond the track, grade labels underneath (e.g.
"0-6月 / 6-12月 / 1-3岁 / 3-6岁"), and a right-aligned monospace reading in the header
(e.g. "24 个月 · 1-3 岁"). Length = value; never decorative; never a precise score.

Structure: 16px side margins, primary actions in the lower half of the screen
(one-handed reach). Every content page ends with a fixed 12px muted footer line:
"AI 生成内容，仅供参考，不替代医生诊断". Bottom tab bar with 4 tabs:
"首页" "档案" "记录" "我的".
```

---

## 3. 小程序 26 屏提示词

### SC-02 · 首页（建议第一屏生成）

```text
Home screen of the parenting assistant. Top header: app name "小光景" with tagline
"养娃 + 养宠，一站式养育参考", a small avatar button on the right linking to profile.
Below, a quota status card: label "今日免费额度", a 5-segment GraduatedBand gauge with
2 segments consumed and reading "剩余 3 / 5 次", caption "用尽后引导开通会员或次日再来".
Then a highlighted entry card "四象宝宝气质测评" with a chip "继续填写" and meta line
"3 分钟 · 12 题 · 了解气质倾向 · 断点：上次答到第 5 题". Then a white card containing
three stacked rows with thin-line icons and chevrons: "0-6 岁宝宝养育 — 喂养 / 睡眠 /
敏感期 / 行为引导", "猫狗宠物饲养 — 喂养 / 护理 / 行为解读 / 应激", "家庭综合问答 —
多 Agent 协同，孩子 + 宠物同场景，一次答全". Then a quieter membership card
"会员权益 — 深度方案 · 月度计划 · 专属档案" with an outline button "了解会员"
(plain neutral styling, no gold). Above the tab bar, an amber-tinted strip:
"未建档：补充档案，建议更贴合". Fixed footer disclaimer line, then the 4-tab bar.
```

### SC-01 · 启动与免责声明（首次强制）

```text
First-launch consent screen that cannot be skipped: no close button, no back gesture.
Centered brand block: large characters "小光景", subtitle "一家人的养育参考".
A white card titled "免责与使用说明" with scrollable body: "本产品为养育科普参考工具，
不替代医生、心理咨询师、教师、执业兽医。紧急情况请立即联系线下专业机构。" followed by
four underlined text links: "《用户协议》" "《隐私政策》" "《免责声明》"
"《儿童个人信息处理规则》（易懂版）". A checkbox "我已阅读并同意上述全部协议" and a
full-width primary button "进入" rendered in disabled state with the note
"未勾选：置灰，不可点击". Tiny caption at the very bottom:
"同意记录：类型 / 版本 / 时间 / 设备".
```

### SC-03 · 档案列表（孩子 / 宠物）

```text
Profile management screen titled "档案管理" with a segmented control at top:
"孩子 2/3" (selected) and "宠物 1/3". A list of child profile cards; each card has a
line-style illustrated avatar (not a photo), bold nickname "宝宝 A", a teal chip
"当前" (or an outline button "设为当前" on the non-current card), detail lines
"2 岁 3 月 · 女 · 2024-07-12" and "92cm · 13kg · 无过敏", and a button row with ghost
"编辑" and danger-outline "删除". Second card: "宝宝 B — 8 月 · 男 · 2026-02-03 ·
早产 · 辅食 6 月龄开始". Below the list a full-width primary button
"+ 新建孩子档案". Bottom caption: "免费 3 个/类 · 会员 10 个/类". Show a tiny
eye icon next to the birth date indicating masked sensitive fields.
```

### SC-04 · 新建 / 编辑儿童档案

```text
Form screen "新建孩子档案" with back arrow and subtitle
"信息用于生成贴合月龄的养育参考". Required section: "昵称 *" text field with value
"宝宝 A", "出生日期 *" date field "2024-07-12", "性别 *" select "女". Optional section
titled "生长情况（选填，越全越贴合）": "身高 (cm)" numeric field "92",
"体重 (kg)" field "13.0", "是否早产" select "否", "已知过敏项" tag input "无",
"辅食开始月龄" select "6 月龄". Below the form a read-only derived strip containing a
small GraduatedBand with reading "自动计算：月龄 24 月 · 区间 1-3 岁" and caption
"只读，服务端派生". Full-width primary button "保存" with caption
"敏感字段加密存储" underneath.
```

### SC-05 · 新建 / 编辑宠物档案

```text
Pet profile form "新建宠物档案". Fields: "类型 *" segmented select "猫 / 狗",
"品种" searchable select "英国短毛猫", "年龄 *" select "3 岁", "绝育状态" select
"已绝育". Optional section "状态（选填，用于饲养规划）": "体重" field "4.2 kg",
"主要食物" select "干粮". An info strip with icon: "有孩子档案时，相关回答自动附加
「儿童-宠物互动安全」提醒". Full-width primary button "保存", caption
"MVP 仅支持猫 / 狗".
```

### SC-06 · 儿童个人信息单独同意弹窗

```text
A bottom sheet modal floating over a dimmed, blurred-out profile form background.
Sheet title "儿童信息处理告知与单独同意". Scrollable body with labeled rows:
"目的：生成贴合月龄的养育参考"; "字段：昵称、出生日期、性别、身高、体重、早产标记、
过敏项、辅食月龄"; "期限：账号存续期 + 30 天"; "共享：仅本产品推理，不用于训练，
详见《第三方共享清单》"; "权利：查阅 / 更正 / 导出 / 撤回 / 删除（我的 → 个人信息
权利中心）". A separate line "监护声明：本人为法定监护人". A checkbox
"已阅读并单独同意处理上述儿童信息". Two side-by-side buttons: primary "同意并继续"
and outline "暂不同意".
```

### SC-07 · 档案删除确认与级联选择

```text
A destructive-confirmation bottom sheet over a dimmed profile list. Title
"删除宝宝 A 的档案？" with warning line "删除后不可恢复，请谨慎操作。". A radio group
titled "请选择删除范围": option 1 (selected) "仅删除档案 — 历史问答、测评报告保留",
option 2 "一并删除全部相关数据 — 档案 + 问答 + 报告 + 图片". Explanatory text:
"默认保留历史问答与测评报告，昵称脱敏为「宝宝 A」，不再关联档案。" A labeled input
"二次校验：输入昵称" with value "宝宝 A". A danger alert strip with icon:
"删除后不可恢复，无回收站。" Two buttons: neutral "取消" and danger-outline
"确认删除".
```

### SC-08 · 育儿问答会话页

```text
AI chat screen titled "育儿问答 · 0-6 岁". Top bar: back arrow, title, and a subject
selector chip "问答对象：宝宝 A ▾" with caption "多孩可切换；绑定档案后按该月龄回答".
An info strip: "未选档案：按「通用 1-3 岁」回答" with inline link "补充档案".
Conversation area: a right-aligned user bubble with the question
"宝宝夜醒 3 次，该不该抱睡？". A status row with a small inline spinner:
"正在检查内容安全…" followed by "通过 · 育儿 Agent 生成中". Then the structured answer
card: header row "AI 生成内容 · 仅供参考" with a "复制" action on the right; sections
separated by hairlines: "建议要点" (two bullets), "适用前提" ("6-12 月龄 · 已加辅食 ·
无发热"), "不建议做法", then two skeleton placeholder sections with shimmering blocks
labeled "观察指标 — 正在生成" and "何时咨询专业人士 — 正在生成" (progressive
rendering, no centered spinner). Bottom input bar with placeholder "输入你的问题…",
a grayed mic icon annotated "语音（本期不支持）", and an accent send button.
Footer disclaimer line.
```

### SC-09 · 宠物问答会话页

```text
Pet AI chat screen "宠物问答 · 猫狗", structurally identical to the child chat.
Top subject selector "问答对象：咪咪 ▾". Below it a teal-tinted safety strip:
"已自动附加儿童-宠物互动安全提醒 · 依据：存在孩子档案「宝宝 A」". User bubble:
"猫总哈气，孩子还追它怎么办？". Status row "正在检查内容安全… 通过 · 宠物 Agent
生成中". Answer card with sections: "行为 / 问题描述", "可能含义", "建议应对",
a warning block "风险提示：抓咬伤需及时医学处置 · 非疾病诊断，不做兽医诊疗"
(amber, solid fill, icon), and a skeleton section "何时就医 — 生成中". Above the
input bar a row of quick keyword chips: "甩尾" "低吼" "哈气" "护食". Input bar +
send button + footer disclaimer.
```

### SC-10 · 家庭综合问答页

```text
Multi-agent family Q&A screen "家庭综合问答". Top row shows both subjects:
"问答对象：宝宝 A + 咪咪" with caption "同时涉及儿童与宠物 → 三 Agent 协同".
User bubble: "3 岁宝宝总追猫，猫常哈气怎么办？". An agent progress card titled
"调度中（并行 ≤15s）· 9.4s" listing three rows: "0-6 育儿 Agent — 3.2s 完成 ✓",
"宠物养育 Agent — 2.8s 完成 ✓", "家庭安全 Agent — 生成中 ⟳". The answer composition:
a full-width solid soft-teal pinned section "安全提示" (explicitly not collapsible,
no left color bar) with two bullet lines; section "育儿侧建议" with text; section
"宠物侧建议" partially replaced by a skeleton block "本节生成中"; below, an amber
conflict strip "观点存在差异，建议多方参考". A collapsed row "▸ 本次参与协同的
Agent（展开显示耗时）". Footer disclaimer.
```

### SC-11 · 结构化回答卡（全貌，组件基准）

```text
A component-anatomy screen showing ONE complete structured answer card, full-bleed,
sections separated by hairlines, top to bottom: (1) pinned solid soft-teal safety band
"安全提示（置顶 · 不可折叠）" with icon and one example line; (2) a paywall block
styled as a sunken gray area (#E9EFED): section title "完整养育方案", a two-line
preview summary that fades out at the bottom, and an outline button "解锁会员" —
no overlay mask, no stripes, no gold; (3) "建议要点" bullet list; (4) "适用前提" as a
row of small outline chips; (5) "不建议做法"; (6) "观察指标"; (7) "何时咨询专业人士";
(8) a dashed placeholder row "知识库引用（前端不展示）"; (9) an amber conflict strip
"观点存在差异，建议多方参考"; (10) caption rows "免责声明（不可删除）" and
"AI 生成内容"; (11) a bottom action bar with four text actions "复制" "存图" "反馈"
"举报".
```

### SC-12 · 风险拦截弹窗

```text
A full-screen risk interception overlay: high contrast, no close button, no advice
text anywhere. Top: a full-width danger-soft (#F7E4E2) header band with a danger title
"已停止生成回答" and lines "为保护你与孩子，本页不展示你的原文，也不提供任何诊断或
建议文本。" and "拦截原因：命中高危类别 · 本次不生成内容，不计提问次数". Then a card
list titled "危机干预渠道"; each row shows channel name, number, and two small
actions [拨打] [复制号码]: "紧急报警 110", "未成年人保护热线", "青少年服务台 12355"
with a script hint "话术：孩子有自伤想法，请协助", "心理援助热线", "宠物急症：本地
宠物医院" caption "大出血 / 中毒请立即前往", "犬伤处置：犬伤门诊 / 疾控" caption
"儿童被咬抓伤请立即前往，不可延误". Bottom: primary button "我知道了" and outline
button "这不是高风险，我要继续提问". Nothing else — no diagnosis, no suggestions.
```

### SC-13 · 拦截后回流与误报申诉

```text
Risk appeal screen "风险提示" with back link "◂ 返回会话". Card 1: bold title
"本次提问已被安全拦截", body "为保护孩子与家人，本次不生成回答。情况紧急请立即联系
线下专业机构。", monospace meta rows "拦截记录编号 RISK-20260918-0042" and
"命中参考类别 儿童安全类（脱敏）", note "不展示你的原始提问文本，也不回显命中的具体
词条。". Card 2 (collapsible with chevron): "这可能是一次误报 [展开]" and body
explaining the appeal goes to manual review with a 24h SLA and does not consume quota.
Card 3: textarea "补充说明（选填）0 / 500" and an attach button
"+ 附件：截图（选填）" with caption "截图请先遮盖孩子可识别信息". Card 4: header
"申诉状态" with a teal chip "已受理", rows "受理编号 APL-20260918-0042" and
"预计复核时限 24 小时内" plus state notes below. Card 5: "求助渠道 [更多]" with a
short channel list. Primary button "提交申诉", outline button "返回会话".
```

### SC-14 · 测评引导页

```text
Assessment intro screen "四象宝宝气质测评". A hero card with a simple line-style
illustration, the title, and caption "四象为趣味包装名，四类用中性命名". Two
contrasting blocks: "这是什么" — "一份 0-6 岁通俗情境问卷，了解孩子近期的行为倾向，
用于选养育方式与亲子沟通方法。"; "这不是什么" — "非心理测评工具，非终身性格判定；
不做诊断、治疗与心理评估；不算命、不判定天生注定。" A meta row: "预计 3 分钟 ·
12 题 · 4 个维度" and "题型：5 点情境选择题", caption "仅供养育参考，不替代专业人士。"
A resume card: "继续上次填写 · 第 5 / 12 题" with caption "断点已保存，可随时继续；
断点保留 90 天". Full-width primary button "开始测评", caption below "开始前建议先选好
孩子档案". No scientific or psychological jargon anywhere.
```

### SC-15 · 测评作答页

```text
Assessment question screen, one question per screen. Top: back control "退出",
progress label "第 5 / 12 题", a thin progress bar at 42%, caption "退出即自动保存
断点". Question card: small label "第 5 题 · 单选", question text "带孩子去陌生亲戚家
时，他通常会：", five stacked radio options: "先躲在你身后，很久才出来" (selected,
accent border), "观察一会儿，再慢慢靠近", "犹豫一下就跟人玩起来", "很快就主动找人
互动", "完全不在意，自己玩自己的", caption "没有对错，选最接近平时表现的即可".
A small auto-disappearing toast chip "已保存断点 · 刚刚". Bottom two buttons:
outline "上一题" and primary "下一题" (annotate: the last question changes the
primary button to "提交并计分").
```

### SC-16 · 测评报告页

```text
Assessment report screen "测评报告". Meta rows: "被测孩子 宝宝 A · 2 岁 3 月" and
"生成时间 2026-09-18 12:40". Type card: a centered leaf line-icon above a large title
"慢热型", caption "四象仅作趣味包装，不作理论映射宣称". Dimension card: four
horizontal three-level GraduatedBand gauges labeled "活动水平 — 偏高",
"趋近-退缩 — 偏低", "适应性 — 偏高", "情绪强度 — 偏低"; NO numeric scores anywhere,
caption "只分档，不渲染精确分数". Insight card with three text sections:
"类型解读", "适配养育方式", "沟通技巧", each one or two sentences. A conditional amber
strip "波动提示：仅反映近期行为倾向，单次结果不代表长期特质". A pinned closing card
"气质不是宿命判定 — 孩子性格会随成长变化，本报告不作为任何诊断、评价或长期定论。
仅供养育参考，不替代专业人士。" plus the disclaimer and AI label. Bottom action bar:
primary "保存长图" and text actions "分享" "反馈" "举报".
```

### SC-17 · 报告长图预览与保存

```text
Share-image preview screen "报告长图". Main area: a tall scrollable export-image
preview (aspect about 1:3.2) showing: type title "慢热型" + the four gauge bars +
sections 类型解读/养育方式/沟通技巧 + a non-fatal note + a bottom disclaimer block
occupying a clearly visible area and repeated twice, plus a QR code, short link and
caption "免责声明 · AI 生成内容标识 · 协议版本 V1.5". Below the preview: a privacy
card "隐私提示 [了解]" with text "请勿在分享中暴露孩子的可识别信息（正脸照、姓名、
园所、门牌等）。", a row "头像：默认插画头像 ▾" and a toggle "打码开关".
Buttons: primary "保存到相册", outline "分享给好友", text "复制链接".
```

### SC-18 · 历史记录列表

```text
History list screen "记录" with a filter dropdown icon on the right. A filter chip
row: "全部" (selected) "孩子" "宠物" "问答" "报告". Three record cards, each with a
type chip in the top-right corner ("报告" soft-teal chip / "问答" neutral chip):
card 1 — time "今天 12:40", bold line "宝宝 A · 气质测评报告 · 慢热型",
caption "2026-09-18 12:40 · 免费内容"; card 2 — "今天 09:12",
"咪咪 · 猫咪频繁哈气怎么安抚", "2026-09-18 09:12 · 会员内容" (membership chip is a
plain neutral outline, NOT gold); card 3 — "昨天 20:30",
"宝宝 A · 2 岁夜醒频繁怎么办", "2026-09-17 20:30 · 免费内容". At the bottom a centered
load-more row "下拉加载更多（每页 20 条）". 12px captions, hairline-separated cards.
```

### SC-19 · 记录详情

```text
Record detail screen "记录详情". Meta rows: "记录类型 问答（会员内容）",
"关联档案 咪咪 · 英短 · 3 岁", "时间 2026-09-18 09:12". Above the content an amber
read-only strip: "会员已到期，内容只读 — 到期后不再生成新内容，历史保留只读".
Content card: bold question "咪咪频繁哈气，怎么安抚？" followed by bulleted sections
"行为含义：哈气多表示紧张或警告，需结合当时情境判断（个体有差异）。",
"建议应对：停止抱猫，留出退路，用零食建立正向联结后再接近。",
"何时需就医：伴呕吐 / 拒食 / 呼吸急促时尽快联系执业兽医。". An info strip
"内容已更新 [查看说明] — 该回答依据的知识库条目已回滚；历史内容不追溯重写，仅作
提示。" Footer disclaimer + AI label. Bottom bar: text actions "反馈" "举报" and
primary "重新生成（会员）".
```

### SC-20 · 会员权益页（Android 可购）

```text
Membership paywall "会员权益" with subtitle "解锁深度养育内容". A clean comparison
table titled "免费 vs 会员" with rows "深度养育方案 无 / 有", "月度养育计划 无 / 有",
"宠物长期规划 无 / 有", "复合场景方案 部分 / 完整" — check marks in accent teal,
plain "无" text; strictly no gold or purple anywhere. A purchase card: "会员月卡
19.9 元/月" (monospace price), captions "单次购买 · 不自动续费" and
"有效期 30 天，到期不自动扣费" and "价格以服务端商品配置为准". A required checkbox
"虚拟内容一经解锁不支持退款，我已阅读并知悉上述说明" and a full-width primary button
"立即开通 19.9 元" shown DISABLED with note "未勾选：置灰". Bottom text links
"订单记录" "权益说明" and a status line "会员状态：有效期至 2026-05-01". Caption:
"会员到期：深度内容保留只读（不可新增，可续费恢复）". Tone: honest and calm —
no banners, no countdown timers, no discount badges.
```

### SC-21 · 会员权益页（iOS / 额度用尽）

```text
Membership screen, iOS variant with an overlay. Main: the same benefit comparison
table "免费 vs 会员", but instead of a purchase card an info card: "当前设备暂不支持
购买，可在 Android 设备开通（iOS 不开放虚拟支付入口）" with a secondary button
"查看权益说明" — no price, no buy button. Over the lower half, a bottom sheet:
title "今日免费额度已用完", rows "免费额度 3-5 次/日", "次日 00:00 恢复",
"会员不受额度限制", two buttons "查看权益说明" and "知道了". The underlying screen
is dimmed.
```

### SC-22 · 下单与支付结果页

```text
Order confirmation screen "订单与支付". Card 1 "订单确认": rows "商品 会员月卡 ·
30 天", "金额 19.9 元" (monospace), "有效期 支付成功起 30 天", "到期时间 支付成功后
展示", a link "《退款政策》- 虚拟内容已解锁不退", primary button "立即支付 19.9 元"
with caption "下单前二次校验服务端价格". Below, a second card showing the
"支付确认中" state: an inline spinner line "支付中… 请勿重复点击", caption
"按钮已锁定，返回需二次确认", an info strip "支付确认中：已扣款但未收到回调 ·
期间可关闭页面，稍后自动生效", buttons "我知道了" "订单记录".
(A separate variant shows the success state: a check icon, "权益生效 20:17",
"到期 2026-05-01 20:17", button "去查看会员内容".)
```

### SC-23 · 个人中心

```text
Profile tab screen "我的". Header card: a line-style avatar, "家长用户" with an
"编辑" link, membership line "会员：有效期至 2026-05-01" as plain text (no gold).
Below, grouped list sections separated by hairlines, every row with a chevron:
group "档案" → "孩子档案 2/3", "宠物档案 1/3"; group "记录" → "历史问答与报告",
"我的反馈记录"; group "会员" → "会员与订单" with caption "权益 · 订单记录 · 退款
政策"; group "个人信息权利" → "个人信息权利中心", "儿童信息处理规则（易懂版）",
"第三方共享清单"; group "协议与声明" → "用户协议 · 隐私政策 · 免责声明",
"AI 生成内容标识说明"; group "账号" → "账号与安全". Bottom tab bar with "我的"
selected.
```

### SC-24 · 账号与安全

```text
Account & security screen "账号与安全". Grouped sections: "登录方式" → row
"微信登录（openid 绑定）"; "权限管理" → rows "麦克风 未授权 [去设置]" and
"相册/摄像头 已授权 [去设置]" with caption "用于语音与图片反馈，可随时关闭";
"撤回同意（分项）" → rows "基础同意（协议与免责） [撤回]" and
"儿童信息单独同意 [撤回]" with caption "撤回后：停止处理对应信息；儿童信息撤回：
档案停用、不再写入；已生成历史保留但脱敏"; "账号注销" → caption
"注销后数据删除、不可恢复；订单与交易记录按法定义务留存" and a danger-outline
button "注销账号（二次确认）" placed at the top of the section, away from the thumb
zone.
```

### SC-25 · 个人信息权利中心

```text
Privacy rights center "个人信息权利中心" with caption "SLA：15 个工作日内答复
（默认值）". Six rows as a grouped list, each with a thin-line icon, title,
sub-caption and right action: "查阅我的信息 [查看] — 档案 / 问答 / 报告 / 同意记录";
"更正信息 [申请] — 档案可自助改；日志类只能申请"; "复制与导出 [导出] —
JSON / CSV · 邮件或本地下载"; "撤回同意（分项）[撤回] — 基础同意 / 儿童信息单独
同意"; "删除个人信息 [删除] — 删除后不可恢复；交易记录除外" (delete action in
danger color); "账号注销 [注销] — 流程见账号与安全二次确认". Bottom status block:
"处理中请求：状态 · 时间 · 期限" and "被拒绝时：给出拒绝理由与申诉入口".
```

### SC-26 · 反馈提交与一键举报

```text
Feedback & report screen "反馈与举报" with a segmented control "我要反馈" (selected)
/ "一键举报". Feedback panel: label "问题描述（必填）" with a textarea, a row of
selectors "关联内容：[选择对话] [选择报告]", an upload row "图片：最多 3 张
（已选 1/3）" showing one thumbnail with an amber badge "审核中", caption "图片将走
微信内容安全检测 · 检测中→审核中，不通过则退回", primary button "提交反馈" with
caption "提交后给受理编号与处置时限". Report panel below: title "一键举报（生成
内容）" caption "举报对象：本条回答 / 报告", four checkbox rows: "违法违规内容",
"医疗误导（含药名剂量）", "有害未成年人信息" annotated "单列 · 更短处置时限",
"其他（请补充说明）", primary button "提交举报" with caption
"受理编号 · 处置时限 · 结果回执".
```

---

## 4. 后台管理端 8 屏（切换到 Web 模式后使用）

> 先发这条定 Web 基调：

```text
Switch to a web dashboard design, 1440x900. Same design tokens: background #F2F5F4,
white cards with hairline borders #D5DEDB, accent teal #0A6B60, ink #0F1E1C.
Layout: a fixed 240px left sidebar with menu items "知识库管理" "词库维护"
"Agent 调用日志" "反馈与举报" "高风险事件" "权利请求" "系统开关与配置", a top bar
"小光景 - 后台" with the current user "admin@jiaban · 内容运营 · [退出]" on the right,
and a content area with max-width 1200px centered. Dense data tables allowed:
fixed column widths, right-aligned tabular numerals, status chips, row actions,
pagination. Roles gate buttons: hide edit actions for read-only roles.
```

### PA-01 · 后台登录与 MFA

```text
Admin login page, centered white card on the gray background: title "管理员登录",
fields "账号" (admin@jiaban) and "密码" (dots), an MFA section titled "二次验证（MFA）"
with a 6-digit code input and button "获取验证码", caption "验证码 5 分钟内有效，
60 秒后可重发", a checkbox "记住此设备（7 天）", primary button "登 录".
Below the card: a role caption "角色说明（最小权限）：超级管理员 / 内容运营 / 客服 /
专家", a recent-login line "最近登录：2026-10-02 09:12 · 北京市 · 已成功", and an
amber warning "连续失败 5 次锁定 15 分钟".
```

### PA-02 · 知识库管理列表

```text
Knowledge base management list. Content header: tabs with counts
"知识库：育儿 (128) | 宠物 (76) | 题库 (18)" and a primary button "+ 新建条目".
Filter bar: 状态[全部] 领域[全部] 关键词[______] [搜索]. A dense table with columns
ID / 标题 / 状态 / 版本 / 审核人 / 操作 and rows: "KB-001 幼儿睡眠引导 已上架 v3
专家A [编辑][下架]", "KB-014 辅食添加顺序 待审核 v1 — [审核][编辑]", "KB-032 猫应激
识别 已上架 v2 专家B", "KB-045 幼儿敏感期 已驳回 v2 专家A [查看][重提]",
"KB-051 狗狗护食纠正 已下架 v4 专家B [回滚][编辑]" (greyed). Status chips: 已上架
teal-soft, 待审核 amber-soft, 已驳回 danger-soft, 已下架 neutral. A batch bar with
"☐全选 [批量上架][批量下架][导出]", a footnote "审核规则：上线前 100% 审核；上线后
每月抽检 30 条，高危类目 100% 审核 · 合格线 ≥98%", pagination "第 1 / 12 页".
```

### PA-03 · 知识库条目编辑与版本回滚

```text
Knowledge base entry editor. Header: "KB-001 幼儿睡眠引导" with buttons
"保存草稿" and "提交审核". Meta row: 领域[育儿] 适用月龄[6-12 月] 宠物类型[--],
tag chips "睡眠" "夜醒" "抱睡" with "+ 添加". A large markdown textarea with sample
content about 6-12 月龄夜醒. Below, a validation panel "发布前校验": row
"敏感词 — 通过 0 命中" (ok) and row "医疗/兽药模式规则 — !! 1 命中" (amber) showing
the hit snippet ""每日 3 次，每次 5ml"" and actions "改写 / 删除 / 标记为专家复核".
A required input "变更说明（必填）". A right-side version history table:
"v3 专家A 2026-09-28 补充夜醒排查顺序 / v2 运营C 2026-09-15 调整适用月龄区间 /
v1 专家A 2026-09-01 首次上架", a danger button "回滚到 v2" with note
"回滚后触发内容追溯处置；历史问答不重写正文，仅追加提示".
```

### PA-04 · 词库维护（高危 / 敏感）

```text
Risk lexicon maintenance. Header tabs: "词库：高危 (86) | 敏感 (241)" with buttons
"+ 新增词条" "批量导入". Filter bar: 类型[全部] 策略[全部] 状态[生效]. A table with
columns 词条 / 类型 / 处理策略 / 阈值档 / 状态 / 更新人 and rows: "持续高烧惊厥 高危
阻断 >0.8 生效 专家A", "自伤 高危 阻断 >0.8 生效", "抑郁 高危 拦截+引导 0.5-0.8
生效", "每日 N 次 敏感 改写 规则 生效 运营C", "包治 敏感 降级 - 生效". A config panel
"两级判定配置": "一级：词库 + 正则 — 毫秒级 · 命中即阻断", "二级：语义模型（仅灰区）
— >0.8 拦截 / 0.5-0.8 拦截+引导", "灰区以下 (<0.5) — 放行并打标，纳入抽检".
A panel "医疗 / 兽药模式规则": the regex "药名 + (mg/kg|片|ml|每日 N 次)" with buttons
"编辑规则" "规则测试（输入样例命中）". Footer buttons "命中日志" "变更留痕"
"一键回滚" and caption "词库变更直接影响线上拦截，保存后 1 分钟内全量生效并记录版本".
```

### PA-05 · Agent 调用日志

```text
Agent call log screen. Header: "调用日志（近 24h 12,486 条）" with button "导出 CSV".
Filters: 时间[近24h] Agent[全部] 风险[全部] 冲突[全部]. A dense table with columns
会话 ID / 时间 / 输入摘要(脱敏) / Agent / 耗时 / 风险 / 冲突 and rows:
"s_8821 10:12:03 8月龄夜醒… 育儿 3.2s 无 无", "s_8822 10:12:44 孩子追猫… 多Agent
9.1s 无 有", "s_8823 10:13:10 7月龄高烧… -- 0.3s 命中 无", "s_8824 10:14:02 狗狗
低吼… 宠物 2.8s 无 无". Below, an expanded detail drawer for s_8821 with sections:
"调度决策 — 意图=smart_sleep / 复合=否", "参与 Agent：child_care_0_6 (3.2s, ok)",
"evidence_ref：kb_child_sleep_03, kb_child_sleep_07" (monospace), "风险判定：一级未
命中 / 二级未触发", "留存期 — 网络日志 ≥6 个月". Footer note: "日志中的用户输入仅
保留脱敏摘要；完整原文不在后台展示".
```

### PA-06 · 用户反馈与投诉举报处置

```text
Feedback & report handling. Header tabs: "反馈 (23) | 举报 (4, 涉未成年 1)" with
button "批量处理". Filters: 状态[待处理] 分类[全部] 时间[近7天]. A table with columns
编号 / 类型 / 内容摘要 / 关联 / SLA / 状态 and rows: "F-0451 反馈 希望增加 3 岁以上
内容 s_8821 72h 待处理", "R-0032 举报-医疗误导 建议里出现用药频次 s_8830 24h 待处理",
"R-0033 举报-涉未成年 回答含不当示例 s_8840 24h 加急" (red SLA chip), "R-0034 举报-其他
内容重复 s_8844 72h 已驳回". A disposal panel for R-0033: radio "举报分类 违法违规 /
医疗误导 / 有害未成年 / 其他", action buttons "驳回 [下架内容] [上报]", a required
input "处置依据", a read-only evidence area "留证：截图 + 命中记录 + 处置人 + 时间",
checkbox "向举报人回执". Caption: "涉未成年人举报：SLA 更短（24h 初审 / 72h 处置）".
```

### PA-07 · 高风险事件值班复核与内容追溯处置

```text
High-risk event review. Header: "高风险事件（今日 7 起，待复核 2）" with "导出".
Filters: 时间[近7天] 类别[全部] 处置[全部]. A table with columns 事件号 / 时间 /
命中类别 / 置信度 / 层级 / 处置 / 值班 and rows: "E-2211 09:12 儿童虐待 0.93 一级
已阻断 A", "E-2212 10:03 孩子自伤想法 0.88 二级 已阻断 A", "E-2213 11:20 持续高烧
惊厥 0.61 二级 已引导 B", "E-2214 12:44 宠物中毒 0.90 一级 已阻断 B" (confidence in
monospace). A review panel for E-2212: radio "复核结论 [维持阻断][判定误报]
[需补充信息]", a checkbox "上报主管部门" with fields "上报对象 / 上报时间 / 留痕人 A"
(escalate controls disabled until a conclusion is set), caption "复核 SLA 24h".
A trace panel "内容追溯处置（按 kb_id 反查受影响内容）": rows "来源条目 KB-014
（已下架）", "影响面 问答 128 条 / 报告 12 份", radio "分级：A 无影响 / B 加提示 /
C 下架", buttons "执行处置" "查看影响清单", caption "闭环时限 7 个工作日".
```

### PA-08 · 个人信息权利请求处理与系统开关

```text
Privacy requests & system switches. Section 1 header: "个人信息权利请求（待处理 3）"
with button "导出处理记录". Filters: 类型[全部] 状态[待处理] SLA[即将超时]. A table
with columns 请求号 / 类型 / 用户 / SLA / 状态 / 处理人 and rows: "P-0041 导出
（JSON）u_2381 剩 3 天 处理中 A", "P-0042 撤回同意 u_2390 剩 5 天 待处理 --",
"P-0043 删除数据 u_2402 剩 1 天 待处理 --" (last row's SLA highlighted red).
A processing area for P-0041: select "请求类型 查阅/更正/导出/撤回/删除/注销",
segmented "导出格式 [JSON][CSV]" and "交付：[邮件][本地下载]", input
"拒绝理由（如拒绝必填）", buttons "生成导出" "标记完成" "拒绝", note
"全部操作留痕". Section 2 "系统开关与配置（变更留痕 / 一键回滚）": a checkbox group
"紧急下线：☐育儿问答 ☐宠物问答 ☐综合问答 ☐测评 ☐会员", rows
"价格配置：19.9 元/月 [修改]", "AI 标识文案：AI_GEN_LABEL_V1 [编辑]",
"危机渠道清单：CRISIS_CHANNELS_V1 [编辑] 复核到期：2026-12-01",
"灰度开关：体验版 [开] 正式版 [关]", buttons "查看变更历史" "回滚到上一版本".
```

---

## 5. 状态与变体补丁指令（通用模板，逐屏套用）

对任意已生成屏幕追加以下指令即可产出对应状态变体（对应文档 §6 状态矩阵 / §2.7）。

**5.1 空态**
```text
Replace the list content with an empty state: a light line-style illustration,
headline "…", a one-line value caption (e.g. "建档后，回答会按孩子月龄给出，而不是
通用模板"), and one primary button "…". Keep the rest of the layout unchanged.
```

**5.2 加载态（骨架屏）**
```text
Show the loading state: replace content sections with skeleton placeholders that
match the final layout shape (including gauge track placeholders), with a subtle
shimmer; keep section titles visible with "生成中" labels. No centered spinner.
```

**5.3 降级（单侧 Agent 失败）**
```text
Show a degraded state: at the failed section's position insert an amber solid strip
with icon and text "本次部分内容未能生成"; all other sections remain readable; keep
the disclaimer and AI label.
```

**5.4 安全失败（家庭安全 Agent 失败）**
```text
Show the safety-failure state: hide ALL body sections, keep only a static solid
soft-teal safety card, the disclaimer, the AI label, and a short crisis channel
list. Nothing else.
```

**5.5 会员门控（下沉地面）**
```text
Show the paywall variant of this content block: a sunken gray (#E9EFED) area with
the section title, a two-line preview summary that fades out, and an outline button
"解锁会员". No overlay mask, no stripes, no gold or purple.
```

**5.6 表单校验错误**
```text
Show a validation error: under the height field, red helper text with icon
"身高应在 40–140 cm 之间。请检查是否多输了 0。", the field border in danger color,
the save button disabled with a nearby reason.
```

**5.7 常见偏差一键修法（Stitch 通用毛病）**

| 偏差 | 修法指令 |
| --- | --- |
| 出现渐变/玻璃/光晕 | `Remove all gradients, glass blur and colored glows. Flat surfaces with hairline borders only.` |
| 用了 emoji 当图标 | `Replace every emoji with a thin-line SVG-style icon, 1.75 stroke.` |
| 会员区出现金色/紫色 | `Membership elements must use plain neutral styling; never gold or purple.` |
| 彩色左边框 | `Remove colored left borders; status is expressed by solid soft-fill strips and chips only.` |
| 安全分节变成普通卡片 | `Make the safety section a full-width solid #E1EFEC block pinned at the top of the card, not collapsible, without a left color bar.` |
| 圆角乱（出现胶囊按钮） | `Use exactly two radii: 12px for cards/surfaces, 8px for buttons/inputs/chips. No pill-shaped buttons.` |
| 出现精确分数 | `Remove numeric scores; express levels with the three-band gauge only.` |
| 按钮文字被加载态藏掉 | `In the loading state keep the button label visible and legible; only add a small inline spinner.` |

**5.8 暗色模式（夜醒场景，独立取值）**
```text
Create a dark mode variant of this screen: background #0C1614, surface #13201E,
raised surface #1B2A27, primary text #E8EFEC, secondary #AEBFBB, tertiary #93A5A1,
accent #4FB3A4 with soft fill #16332E, danger #E8776D, amber #DCB25C. Not pure
black; keep all text contrast high. Hairlines become #243430-ish subtle strokes.
```

---

## 6. 生成后走查清单（对照 §10.3 的 Stitch 版）

1. 整体像「量具刻度系统」而不是母婴电商/糖果卡？——不像就重生成
2. 无 emoji 图标、无渐变、无玻璃、无金色/紫色会员、无彩色左边框？
3. 安全分节：实底铺满整宽、置顶、不可折叠、无左色条？
4. 刻度带：长度即数值、无精确分数、语义色只在刻度内部、游标越出槽体？
5. 每个内容页页脚都有免责 + AI 标识常驻小字？
6. 主操作在下半屏热区；危险操作（删除/注销）是 danger 描边且避开拇指区？
7. 圆角只有 12（面）/ 8（控件）两档，无胶囊按钮？
8. 状态只染标签与实底条，不染整行？
9. 拦截页（SC-12）是独立全屏、无关闭 X、无任何建议性文本？
10. 空态有轻插画 + 价值说明 + 一个主操作，而不是「暂无数据」？

---

## 7. 与文档的对应关系

| 本包章节 | 文档来源 |
| --- | --- |
| §2 全局风格 | `DESIGN.md` 全部 token + UI 文档 §1.5 方向契约、§2 设计系统 |
| §3 逐屏 SC | UI 文档 §5 逐页线框图（SC-01~26 的元素说明与状态分支） |
| §4 后台 PA | UI 文档 §5（PA-01~08） |
| §5 状态补丁 | UI 文档 §2.7 状态可视手法、§6 状态矩阵、§7 交互时序 |
| §6 走查 | UI 文档 §10.3 走查清单 |
| 固定文案 | UI 文档 §8.1 文案 ID 清单（提示词内引号文案与之一致） |

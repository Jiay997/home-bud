# 小光景微信小程序

独立 uni-app Vue 3 客户端，与既有 H5（`../frontend/`）共用同一服务端。2026-10-13 完成浅色「织理质感」界面重构，视觉以 C-2 界面设计生成方案报告为准，结构与状态以《家伴-UI原型描述_V1.3》为准。

## 本地运行

```powershell
cd wechat-miniapp
npm install
npm run dev:mp-weixin
```

执行后，微信开发者工具导入编译输出目录 `wechat-miniapp/dist/dev/mp-weixin/`（其中包含生成的 `project.config.json`）。若开发者工具仍显示旧版页面，先确认项目目录指向该输出目录，再重新编译并在工具中重新编译/刷新。不要用 `frontend/` 的 H5 手机预览判断小程序当前界面。

微信开发者工具基础库版本固定为 `3.17.4`。本机曾在 `3.17.3` 下遇到 `Cannot read property 'subPackages' of undefined`；固定版本后，本轮重构产物已在模拟器中完整跑通（含下文「验证状态」的自动化逐页走查）。该配置用于稳定开发预览，不代表生产兼容性已覆盖所有基础库版本。

## 页面与导航范围（15 页）

底部四 Tab 顺序：**首页 / 档案 / 记录 / 我的**（自定义 `MiniTabBar`，通过 `redirectTo` 切换；页内页不显示 Tab）。十五个页面均为自定义导航（`navigationStyle: custom`）。

| 页面 | 路由 | 进入方式 |
| --- | --- | --- |
| 首页 | `pages/index/index` | 启动页 |
| 家庭档案 | `pages/profiles/index` | 档案 Tab；列表卡点击进入档案详情 |
| 记录 | `pages/records/index` | 记录 Tab |
| 我的 | `pages/me/index` | 我的 Tab |
| 问答 | `pages/qa/index` | 首页入口卡（育儿/宠物/家庭综合）或记录页打开历史 |
| 测评引导 | `pages/assessment-intro/index` | 首页测评 hero、报告页「再次测评」 |
| 测评作答 | `pages/assessment/index` | 引导页「开始测评 / 继续填写」 |
| 观察报告 | `pages/report/index` | 测评提交后、首页 hero（已完成态）、记录页 |
| 会员权益 | `pages/member/index` | 首页额度卡与会员卡、我的页会员行 |
| 档案详情 | `pages/profile-detail/index` | 档案列表卡点击（孩子 / 宠物，`kind` 与 `uid` 入参） |
| 相册 | `pages/profile-album/index` | 档案详情「相册」缩略条「查看全部」/ ＋ 添加（`kind`、`uid` 与 `name` 入参） |
| 健康档案 | `pages/health/index` | 「我的」页「健康档案」入口（孩子 / 宠物分组列表 + 顶部「待复查」卡） |
| 健康档案编辑 | `pages/health/edit` | 健康档案「新建」或记录行点击（`uid` 可选入参，空为新建） |
| 笔记 | `pages/notes/index` | 「我的」页「笔记」入口（标题 + 摘要列表） |
| 笔记编辑 | `pages/notes/edit` | 笔记「新建」或行点击（`uid` 可选入参，空为新建） |

档案列表卡仅展示头像、姓名与一行 meta（孩子如「30 个月 · 女孩」、宠物如「猫 · 成年 · 绝育情况未填写」）；头像支持设置（`ProfileAvatar` 共享组件，列表与详情同口径）、编辑（详情页右上角编辑入口）、删除与「设为当前观察对象」均在详情页完成，编辑保存后详情页即时同步（含从相册页返回时缩略条与计数经 `onShow` 自动刷新）；「当前」徽标经本地存储 `jiaban_current_profile` 跨会话保持。相册为每档案 30 张上限的方图网格（`＋` 瓦片添加、点按 `previewImage` 全屏、长按管理/删除），详情页保留横向缩略条（前 4 张 + 计数 + 查看全部）。

健康档案（孩子 / 宠物）：列表按档案分组并置顶「待复查」卡（`due_status` 由服务端按上海时区当天计算——overdue / soon≤7 天 / upcoming / none，行内附提醒徽标）；编辑页支持体检日期、标题、备注、复查计划与电子版报告上传（PDF ≤10MB 按 `%PDF-` 魔数校验 / JPG / PNG，预览 / 替换 / 删除同步清理磁盘文件）；复查提醒为**纯应用内**展示（不接 agent、不做推送）。笔记：Markdown 形态的知识手册（查看态经 `MiniMarkdown` 渲染、右上角切换 textarea 编辑态），正文加密落库、乐观锁 `version` 冲突提示刷新（1003）、保存前本地敏感词前置检查（1303），不公开分享。

## 视觉与组件口径

- 色板与圆角/阴影 tokens 定义在 `src/App.vue` 的 `page` 选择器：`--bg #F4F3F0`、`--surface`、`--surface-warm`、`--ink-1/2/3`、`--primary #7C9082`、`--info`、`--warn`、`--danger` 及对应 `-soft` 底；圆角 `--r-card 24rpx` / `--r-control 999rpx` / `--r-inner 16rpx`。旧深色 `--jb-*` 变量已全量删除。
- 纸纹：`npm run gen:texture` 由 Node 内置 zlib 生成 128×128 透明底噪点 PNG（固定随机种子），base64 内嵌到 `src/styles/texture.css` 的全局 `.tex` 类，挂在页面外层与色带卡（`background-color` + `.tex` 叠加，透明度约 1–5%）。
- 图形零位图（纸纹除外）、禁 emoji：全部插画/图标/对勾均用 CSS 绘制；勾选角为 `.check-tick`。
- 共享组件：`MiniPageHeader`（推入页返回头 / 首页品牌头）、`MiniTabBar`、`MiniComplianceBar`（Tab 页常驻两行合规提示 + AI 标识 pill）、`MiniDialog`（品牌弹窗：信息/确认/危险态/输入式二次确认）、`MiniActionSheet`（品牌操作面板，含危险选项态）、`ReportSheet`（举报四分类弹层，`POST /reports`，问答/报告页使用）、`StateSkeleton`（骨架/空态/降级条）、`FeedbackSheet`（问答/报告页意见反馈弹层）、`ProfileFormSheet`（档案创建/编辑共享表单弹层，含 1302 同意流与 1003 冲突处理）、`ProfileAvatar`（档案头像：已设置显示图片、未设置回退 CSS 字形插画，列表卡与详情 hero 共用，含相机角标态）、`MiniMarkdown`（无状态纯函数 Markdown 子集渲染器：块级 h/p/ul/ol/table/hr + 行内粗斜体；AI 回答与笔记查看态共用，流式 partial 每 chunk 全量重算、表格未完整时整段降级为段落）；「我的」页的权利中心/账号安全/意见反馈为页内面板实现。
- 弹窗调用口径：页面经 `services/dialog.ts` 的 `useDialog`/`useActionSheet`（Promise 化）触发品牌弹窗，替代原生 `wx.showModal`/`wx.showActionSheet`（源码零残留）；15 页内 **24 处 `openDialog` 调用点**（含健康档案编辑页删除记录危险确认、笔记编辑页 1003 冲突提示与删除笔记危险确认）+ 2 处 `openActionSheet` 调用（`MiniActionSheet` 组件于 4 页渲染：我的 / 档案详情 / 相册 / 问答），全部由 `MiniDialog`/`MiniActionSheet` 承接（含档案详情页删除确认、移除头像确认、相册照片删除确认与档案表单弹层同意流）。
- 测试硬约束：`tests/route.test.mjs` 校验路由清单与「模板静态可见文案无连续拉丁字母」——AI、iOS、价格等文案一律放 `<script>` 常量经 `{{ }}` 插值；模板属性表达式内不得出现 `<`/`>`。

## 基线与占位项取值记录（2026-10-13 重构）

两份甲方认可基线（6 张浅色效果图 + C-2 报告；UI 原型 V1.3）中自标注为占位/待决策的项，按 V1.3 自身指引取当前实现值：

- 题量取题库真实值 **16 题**；测评命名沿用中性名「阶段测评」；类型名取服务端中性命名（随和型/活跃型/敏感型/慢热型）。
- 会员权益页权益对照与会员块按后端真实门控契约渲染；价格取 `GET /billing/product`（示例 19.9 元/月）。
- 首页「未建档提示条」为条件元素，本轮未渲染（建档判断依赖项未接入）。
- 七日时间轴与首页提问输入框：SC-02/SC-18 结构中均无，已移除（含 `history-presentation` 服务与测试）。
- 记录页筛选为单行 chips（全部/孩子/宠物/问答/报告），替换原两行筛选；多条件叠加列后续。
- SC-24 账号与安全 / SC-25 权利中心 / SC-26 反馈与举报：本轮以「我的」页内面板/弹层承接同等能力（六类权利 + 申请记录与导出下载、分项撤回、注销；反馈提交；内容举报），独立页面化列入后续迭代。
- 举报入口按 V1.3 §3.3 落到回答卡底、报告页、问答详情，接入既有 `POST /reports`。
- 报告「保存长图」为简化版（canvas 2d：类型 + 四维档位 + 免费解读 + 非宿命 + 免责 + AI 标识 + 品牌），不含小程序码（无短链服务，待补）。

## 配置

- 开发期 API 地址为**运行时解析**（2026-10-14 起，仅 dev 构建启用）：
  - `npm run dev:mp-weixin` 先执行 `scripts/lan-ip.mjs`：收集开发机全部可用局域网 IPv4（排除 internal、169.254.* 与 WSL 虚拟网卡，**保留**移动热点网段 `192.168.137.*`），把首选地址与全量候选写入 `.env.development.local`（已被 `.gitignore` 忽略，不提交）——`VITE_API_BASE_URL`（首选）+ `VITE_API_BASE_URLS`（候选列表，末尾附 `http://127.0.0.1:8000/api/v1`），并向后端 `/api/v1/health` 自检一次（仅证明开发机可达，不证明手机可达）。`.env.development` 的 `http://127.0.0.1:8000/api/v1` 作为无 `.local` 时的兜底。
  - 启动时按序探测（逐项 `GET <候选>/health`，1.5s 超时，首个通过即选中）：**手动覆盖**（一旦设置即独占，失败也不回退）→ 开发者工具回环 `127.0.0.1` → 上次成功地址 → 构建期候选 → 首选地址 → 回环兜底。模拟器与后端同机，`127.0.0.1` 恒先命中，换网不再白屏；真机则在候选列表内自动挑可达地址。
  - 全部候选不可达时按首选地址发请求，页面照常进入错误态并提供「重新连接」（会清空探测缓存重跑，无需重启）。
  - 错误页在 dev 构建下另有「调试连接」入口：可手填地址（自动补 `http://`、去尾斜杠；留空保存即清除覆盖），弹窗内附当前生效地址与最近一轮探测明细（各候选耗时 / 失败原因）。
  - 真机换网（家 / 单位 / 热点）导致预置地址全部不可达且未重新执行 `npm run dev:mp-weixin` 时不必重建：在错误页用「调试连接」手填新地址即可；重新执行后候选列表自动刷新。
  - 指定其他地址（如 Windows 移动热点的 `192.168.137.1`）：`LAN_IP=192.168.137.1 npm run dev:mp-weixin` 覆盖自动探测。
  - 「预览」：手机首次进入需在右上角 `···` → 开发调试 → 打开调试，开启后跳过域名校验；「真机调试」跟随开发者工具设置，本项目 `manifest.json` 已置 `mp-weixin.setting.urlCheck: false`（即「不校验合法域名」）。
  - 链路自检：手机浏览器能打开 `http://<开发机局域网 IP>:8000/docs`，则局域网与防火墙（后端 `0.0.0.0:8000` 监听 + Python 入站放行）就绪；打不开先查同一 Wi-Fi 与防火墙。手机与开发机须在同一 Wi-Fi。
- 生产构建不受影响：运行时解析与调试弹窗均被 dev 常量折叠剔除（`dist/build/mp-weixin` 已 grep 抽查零残留）。生产构建前提供 `VITE_API_BASE_URL=https://<备案域名>/api/v1`，并在微信公众平台配置对应 request 合法域名。
- 生产登录调用 `uni.login` 与后端 `/auth/wx-login`。真实 `WX_APPID`/`WX_SECRET` 只配置在后端环境，不写入小程序源码。

## 验证

```powershell
npm test           # node --test，92 项
npm run type-check # vue-tsc
npm run build:mp-weixin
```

## 验证状态（2026-10-13 重构后；2026-10-14 弹窗品牌化轮、全面模拟测试轮、连接鲁棒性 / 档案卡排版轮、档案详情轮与档案头像 / 相册轮；2026-10-15 甲方四条需求轮增补）

**已通过（本轮实测）**

- `npm test` 92 项全绿：SSE 帧解析与 UTF-8 跨块解码、流式状态机、问答降级文案映射、问答对象、测评断点镜像、长图文本折行、路由清单（15 页）与模板中文约束、端点解析（候选顺序 / 探测顺延 / 覆盖独占 / 失效重探）与请求层接线、上传客户端（`wx.uploadFile` 包络字符串解析 / 顺序上传 / 部分失败汇总）、`mediaUrl` 相对路径拼接、媒体图片管道（下载缓存去重 / 并发共享 / 失败重试与占位降级 / 本地优先回退 / URL 变更重置）、相册页逻辑与「当前档案」本地存储。
- `npm run type-check`、`npm run build:mp-weixin` 通过；编译产物抽查：浅色 tokens 与 `.tex` 已进 app.wxss/页面 wxss，`.check-tick` 与 `background-color` 落位正确，旧深色变量、旧品牌名「家伴」、emoji/对勾字符在 `src/` 零残留。
- 微信开发者工具（基础库 3.17.4）自动化逐页走查：首页（额度卡、测评 hero 已完成态、三入口、会员卡）、记录（列表与空态、单行 chips）、问答（新会话页含对象 pill 与额度行、历史只读页含会员门控块与操作条）、测评引导（边界说明卡/题量行/主按钮）、测评作答（第 1/16 题与李克特选项）、观察报告（历史模式：类型 hero、四维档位条、解读卡、只读标注）、会员权益（对照表、价格卡、退款勾选、iOS 说明位）、家庭档案（儿童信息同意卡与空态）、我的（目录分组与会员行）。截图存档于 `walkthrough/`。
- 真实链路：经 `POST /qa/sessions` + `POST /qa/sessions/{uid}/stream` 由本地后端完成一次真实流式生成（约 41s，`section_delta`/`section_done`/`completed` 帧完整，落库 `done` 并出现在记录页）；测评 start → 16 题作答 → submit → 报告全链路经真实 API 验证并渲染报告页。
- 同意页重构后经「撤回 → 重新同意」真实接口往返验证（复用原行、审计时间戳正确）。
- 弹窗品牌化轮（2026-10-14）：19 处弹窗/面板逐一在模拟器截图走查（`walkthrough/dlg_*`、`sheet_*`），原生弹窗 API 在 `src/` 零残留（grep 实证）；真实驱动链路——撤回同意（单同意直开对话框 / 双同意走 ActionSheet）、更正信息提交→「已提交受理」回执、意见反馈→回执（含受理编号）、报告长图保存相册失败「需要相册权限」与成功「已保存到相册」双路径、首页服务协议/隐私政策弹窗、会员额度与支付提示、AI 生成内容说明；`npm test` 45 全绿 + `vue-tsc` + `build:mp-weixin` 通过。
- 全面模拟测试轮（2026-10-14）：9 页 + 8 条业务链路共 **53 用例全部 PASS**（真实后端 LLM；流式问答分块渐进渲染 3s 首段 / 13s 分节 / 约 41s 落库）；界面兼容性 **4 设备档**（iPhone 5 320 / HUAWEI Mate 80 366 / iPhone 6/7/8 375 / 基线 iPhone 12/13 Pro 390）24 张截图无溢出截断；异常场景 14 项符合预期——四页面断网定制错误态、离线重试请求计数实证（`HB_REQ#1→#2`）、恢复网络点击即恢复就绪态、报告 404 降级、删除昵称校验、撤回取消、相册双路径；**本轮新发现产品缺陷 0 项**。报告：`../docs/测试报告_小程序端全面模拟测试_2026-10-14.md`，证据 215 件存档 `walkthrough/`。
- 连接鲁棒性与档案卡排版轮（2026-10-14）：`npm test` 56 项全绿（新增端点解析 9 例、请求接线 2 例）+ `vue-tsc` + `build:mp-weixin` 通过；**连接自愈实证**——把 `.env.development.local` 两个变量改为不可达地址并重建，开发者工具硬重启后首页仍就绪（经回环 `127.0.0.1` 探测命中，`dbg_heal_home.png`），`jiaban_last_api_base` 记为该回环地址；**调试弹窗走查**——不可达态首页出现「调试连接」→ 弹窗展示当前生效与探测诊断 → 手填保存后恢复就绪（覆盖值经规范化写入）→ 留空清除后再次恢复（`dbg_error/dbg_dialog/dbg_override_applied/dbg_dialog_clear/dbg_override_cleared.png`）；**生产零残留**——`dist/build/mp-weixin` 内 `jiaban_debug_api_base`、`jiaban_last_api_base`、`VITE_API_BASE_URLS`、`createEndpointResolver`、「调试连接」grep 零命中；**档案卡排版**——标签/数值两列栅格 + 过敏整行 + 超长值省略，390/375/320 三设备档与宠物卡截图无溢出（`card_390*/card_375*/card_320*/card_pet_320/card_pet_390/card_cleanup.png`），长昵称、4 项过敏、无身高、长主粮等字段组合以临时档案实测后清理；`impeccable detect` 对两个改动文件零发现。
- 档案列表简化与详情页轮（2026-10-14）：`npm test` 56→**59** 全绿（新增 `profile-current` 本地存储 3 例）+ `vue-tsc` + `build:mp-weixin` 通过；列表卡简化至「头像 + 姓名 + 一行 meta」并整卡进详情（`detail_list_child_pet.png`、`detail_list_pet_tab.png`）；详情页完整字段栅格 + 出生日期脱敏切换（`detail_child_birth_revealed.png` → `detail_child_birth_toggle2.png`）；**编辑即时同步实证**——身高 111→110 保存后详情页即时更新、二次保存还原 111（`detail_child_after_save_toast/settled.png`、`detail_child_height_restored.png`），宠物编辑弹层预填走查（`detail_pet_sheet_edit.png`）；删除孩子走昵称匹配拦截（输入错误昵称确认后弹窗关闭、档案完好，`detail_delete_dialog.png`、`detail_delete_mismatch_toast*.png`）；设为当前后返回列表徽标同步且跨硬重启保持（`detail_set_current.png`、`detail_list_current_badge.png`、`detail_390_list_final.png`）；伪 uid 未找到空态兜底（`detail_missing_state.png`）；iPhone 5 320 窄屏列表/详情/弹层无溢出（`detail_320_*.png`）；`impeccable detect` 对三个改动文件零发现；生产构建抽查含新页 `pages/profile-detail/index`。
- 档案头像与相册轮（2026-10-14）：`npm test` 59→**79** 全绿（新增上传客户端包络解析、`mediaUrl` 拼接、相册页逻辑等 20 例）+ `vue-tsc` + `build:mp-weixin` 通过。**详情页 v2**——hero 暖底「档案卡」置顶（头像 152rpx 白圈 + 相机角标、姓名 + 当前徽标、月龄段 + 性别），相册缩略条浮于底色（150rpx 方图 + ＋ 瓦片 + 「查看全部」），信息卡分区标题 + 记录行排版（出生日期脱敏按钮改版为柔雾圆盘 + 右缘对齐，`detail_eye_v2.png`/`detail_eye_v2_revealed.png` 双态实证）；**头像全链路实证**——`mockWxMethod chooseMedia` + `USER_DATA_PATH` 测试图模拟选图 → 真实上传 → hero/列表卡展示，ActionSheet（相册/拍照/查看大图/移除头像）逐项走查；替换后旧文件已从 `data/uploads/` 删除（服务端实测）、移除头像回字形兜底并弹危险确认（`media_avatar_sheet/replaced/remove_confirm/removed/final_390.png`、`media_list_avatar_390.png`）；**相册全链路实证**——详情缩略条 ＋ → 新相册页（第 11 页）真实上传 → 2/30 网格 → `previewImage` 全屏 → 长按管理删除；**onShow 修复闭环**——相册页加图返回详情，计数「相册 · 2 张」与缩略条自动刷新（`media_album_before/after_add_390.png`、`media_detail_after_back_390.png`）；宠物档案同能力对称走查（`media_pet_detail_390.png`、`media_pet_avatar_390.png`）；390/375/320 三设备档详情页与相册页无溢出（`media_detail_375/320.png`、`media_album_375/320.png`）；生产构建零残留；`impeccable detect` 对三个改动 UI 文件零发现。
- 甲方四条需求轮（2026-10-15）：①**输入显示**——问答页去自动聚焦 + 输入框 `:cursor-spacing="120"`（新建健康/笔记 4 页输入一律不自动聚焦；真机键盘避让待复核）；②**回答可读性**——后端 `MARKDOWN_FORMAT_RULE`（对比/方案类必须用表格 + 语法子集）+ mock 分支同步 Markdown 化；走查实证表格（表头底色 / 边框 / 多列对齐）与加粗/列表渲染正确、`**` 语法标记不再上屏（`qa-v2-answer/qa-v2-table*/qa-member*`），流式中途表格未完整时整段降级为段落、chunk 到位后重算；会员内容块复验为正文（非解锁卡）；③**健康档案**——「我的」页入口 + 列表（孩子/宠物分组 + 待复查卡 + 徽标）+ 新建/编辑（报告上传/预览/替换/删除清盘），提醒流转实证（「还有 3 天复查」出现 → 改期后提醒卡消失）；④**笔记**——「我的」页入口 + 列表（摘要去语法、空态）+ 查看态 Markdown + textarea 编辑（`version` 1→2→3 乐观锁）→ 删除（列表 0 / 详情 1002）；⑤回归：首页与记录页走查无回归（`regress-home/records`）；`npm test` **92** 全绿（路由白名单同步 15 页）+ `vue-tsc` + `build:mp-weixin`；走查 21 张存档 `walkthrough/`；专项报告 `../docs/测试报告_小程序端甲方需求验收测试_2026-10-15.md`。
- 自动化手段备注：`scripts/shot.mjs`（miniprogram-automator 0.12.1 + `cli auto --auto-port 9420`）。已知环境坑：Git Bash 会改写 `/pages/...` 参数（需 `MSYS_NO_PATHCONV=1`）；截图要求开发者工具窗口处于前台（脚本内自激活）；元素查询会挂起，走 `reLaunch` + 截图。全面模拟测试轮增补可复用脚本：`scripts/compat-shoot.mjs`（多设备逐页走查 + sysinfo 存档）、`scripts/err-mock.mjs`（断网故障注入与重试实证）、`scripts/win-focus.py`（截图前置前，规避遮挡节流），`dt-*.py`（屏幕抓取/按钮定位/真实点击）为其 Windows 辅助件。

**未验证（待人工/真机，上线前必查）**

- ~~问答页在模拟器内「发送 → 分块渐进渲染」的交互未由自动化驱动实测~~ —— ✅ 已闭环（2026-10-14 全面模拟测试轮）：模拟器内真实驱动发送，分块渐进渲染 3s 首段 → 13s 分节 → 约 41s 完成落库（`walkthrough/t_qa_send_3s/13s/48s.png`）。
- `wx.request({ enableChunked })` 分块流式在开发者工具与真机的实际表现未实测；不可用时自动回落轮询（`triggerQaGeneration + pollQaSession`），功能不减。
- 真机软键盘避让：输入显示修复（去自动聚焦 + `cursor-spacing`）代码与编译产物已核验，但「输入时页面不被顶飞」需 iOS/Android 真机复核（本轮未动 `100vh` 布局结构，属求稳取舍）。
- 真机 `wx.chooseMessageFile` 文件选择交互：健康档案报告上传在模拟器不可自动化（本轮以 API 直传 + 页面可见实证）。
- 真实模型排版遵守率：DeepSeek 充值后切 `LLM_MOCK=false` 复跑，确认稳定输出表格/列表语法（mock 分支已同构，渲染层不受影响）。
- canvas 长图 `saveImageToPhotosAlbum` 的**真机**相册授权流程未验证（模拟器内已实证双路径：DevTools 会弹原生「另存为」对话框——保存=成功 toast「已保存到相册」、取消=按失败处理弹「需要相册权限」引导；真机默认直存相册、无此对话框）。
- 微信支付未接线：会员按钮点击仅提示「微信支付接入后开放」，订单状态机等后端能力就绪。
- 档案头像/相册的真机相册、拍照授权流程未验证（模拟器内已以 `mockWxMethod chooseMedia` + 真实上传验证全链路）；`/media` 静态服务为 MVP 口径**无鉴权**（uuid 文件名防枚举），生产需切 OSS + 签名 URL，且真机要求与 API 同域（HTTPS + request 合法域名白名单）。
- 真机换网往返（家 / 单位 / 热点）的候选自动切换与「调试连接」手填自愈属人工验证项；模拟器内已实证不可达态弹窗手填 → 恢复就绪路径（含留空清除）。
- 生产 HTTPS API、request 合法域名、线上登录凭据与提审发布仍需单独验证；本地结果不代表线上可用。

## 历史记录

- 2026-10-12：微信登录链路接通正式小程序（`AUTH_PROVIDER=wx`，模拟器 `wx.login` → `/auth/wx-login` 200）。
- 2026-10-13 早：深色「量具」风四页（首页/问答/测评/报告）端到端在开发者工具跑通（首页提问、问答结果、16 题测评、报告）。
- 2026-10-13：本轮浅色「织理质感」重构，页数 5→9；上文「验证状态」为本轮口径。
- 2026-10-13 晚：按验收反馈微调两处——记录页顶部改「标题 + 筛选 chips」两段式（总数并入列表末尾「共 N 条记录 · 已全部加载」）；首次使用同意页视觉重构（徽章插画、pill 标签与文档链接、暖色勾选条）。同步修正后端商品行展示名（DB `product.name` → 「小光景会员月卡」）。
- 2026-10-14：①记录页筛选 chips 排版修复——小程序 `button` 为块级布局，`.chip` 仅设 `min-height` + `line-height: 1` 导致标签压顶（走查截图像素实测：文字上边距 2px / 下边距 28px）；补 `display: inline-flex; align-items: center; justify-content: center`，并把尺寸与档案页 chips 统一（66rpx 高 / 24rpx 字号 / `0 26rpx` 内边距）。同缺陷类「我的」页反馈弹层 `.ghost-button`（取消按钮，88rpx 高无居中）一并补 `display: flex` 居中；两处新规则均已确认进入 `dist/dev` 编译产物。②真机联调地址修复——`.env.development` 的 `127.0.0.1` 在手机上指向手机自身，真机调试首页报「暂时无法连接」（用户真机截图实证）；改为 `.env.development.local`（`gitignore` 承载，不提交）存放开发机局域网 IP `192.168.10.71`，编译产物已确认内嵌该地址；README「配置」补充真机流程与自检方法。③`npm test` 45 全绿、`vue-tsc` 通过。
- 2026-10-14（弹窗品牌化轮）：①测评「下一题」不可用修复——Vue 3.4 `reactive` 不为 `hasOwnProperty` 收集依赖，`hasAssessmentAnswer` 改索引访问（含 0 分语义等价），「下一题」可用态与进度实时刷新；②弹窗品牌化轮——全部 17 处原生弹窗 + 2 处 ActionSheet 替换为 `MiniDialog`/`MiniActionSheet`（`services/dialog.ts` 编程式调用层，Promise 语义不变；危险态/输入式二次确认/危险选项对齐），19 处走查截图存档 `walkthrough/`；DevTools 模拟器内长图保存双路径实证（成功 toast / 权限拒绝引导），测试产物已清理。
- 2026-10-14（全面模拟测试轮）：对小程序端做全量模拟测试并留档 `../docs/测试报告_小程序端全面模拟测试_2026-10-14.md`——功能 53 用例全 PASS、界面兼容性 4 设备档、异常 14 场景符合预期、新缺陷 0 项；断网重试经请求计数实证（`HB_REQ#1→#2`），恢复网络点击即恢复；测试产物已清理，证据 215 件存档 `walkthrough/`。
- 2026-10-14（连接鲁棒性与档案卡排版轮）：①调试连接彻底修复——dev 构建改为**运行时端点解析**（新增 `src/platform/endpoint.ts`：候选烧入 + 按序 `/health` 探测 1.5s 超时 + 上次成功缓存 + 手动覆盖独占；失败自动顺延、全部失败回落首选；模拟器恒先 `127.0.0.1` 自愈）；`lan-ip.mjs` 收集全量网卡 IP（排除 WSL 虚拟网卡、保留 `192.168.137.*` 热点段）经 `VITE_API_BASE_URLS` 烧入构建；错误页新增 dev 专用「调试连接」弹窗（手填地址 / 留空清除 / 探测诊断）；实测：把预置地址改为不可达并重建后，开发者工具硬重启首页仍经回环自愈就绪。②档案卡信息区结构升级（用户实机反馈）——标签 22rpx 弱化、数值 27rpx·600 强调的两列栅格，过敏整行、超长值省略号；390/375/320 三档与宠物卡走查无溢出。③`npm test` 45→56、`vue-tsc`、`build:mp-weixin` 通过；生产产物 grep 抽查零残留；证据存档 `walkthrough/`（dbg_* / card_*）。
- 2026-10-14（档案列表简化与详情页轮）：①列表卡简化——档案卡仅保留头像、姓名与一行 meta（孩子「30 个月 · 女孩」、宠物「猫 · 成年 · 绝育情况未填写」），字段明细与操作全部迁出；②新增档案详情页 `pages/profile-detail/index`（`kind` + `uid` 入参，孩子/宠物对称），含完整字段栅格、出生日期脱敏切换、右上角编辑入口（共享表单弹层 `ProfileFormSheet`，创建/编辑两处复用，含 1302 同意流与 1003 冲突处理）、删除（孩子昵称匹配拦截 / 宠物危险确认）与「设为当前观察对象」；③页数 9→10、「当前」徽标持久化至本地存储 `jiaban_current_profile`（DI store + 3 例单测）；④`npm test` 56→59 全绿 + `vue-tsc` + `build:mp-weixin` 通过；走查证据 24 张存档 `walkthrough/`（detail_*）；`impeccable detect` 三个改动文件零发现。
- 2026-10-14（档案头像与相册轮，甲方需求）：①**后端媒体链路从零落地**——`ChildProfile`/`PetProfile` 增 `avatar_path`、新增 `ProfilePhoto` 表（34→35 张，init_db 幂等补列）、`services/media_store.py`（Pillow EXIF 旋转/限长边/JPEG q85、uuid 文件名、锚定 backend 目录）、`/media` 静态挂载、档案媒体端点族（`PUT|DELETE /profiles/{kind}/{uid}/avatar`、`GET|POST /profiles/{kind}/{uid}/photos`、`DELETE .../photos/{photo_uid}`，孩子档过 1302 门禁、格式/大小 1001、上限 30 张 1007/409）；删除档案（purge/仅档案两模式）同步清媒体文件与行、回执含媒体条目；②**详情页 v2 美化**（用户反馈「太简陋」）——hero 暖底档案卡（头像 + 相机角标 + 姓名 + 当前徽标 + 月龄段/性别）、相册缩略条（150rpx 方图 + ＋ 瓦片 + 查看全部）、信息卡分区标题 + 记录行排版（出生日期脱敏按钮改版为柔雾圆盘 + 右缘对齐）、危险操作下沉；③新增相册页 `pages/profile-album/index`（3 列网格、N/30 计数、`previewImage` 全屏、长按管理删除、空态/满态），页数 10→11；新增共享组件 `ProfileAvatar` 与上传服务 `services/profile-media.ts`（chooseMedia `sizeType: compressed` + 顺序上传 + 部分失败汇总）；④修复详情页 `onShow` 未刷新——相册页加图返回后计数与缩略条自动更新（走查闭环实证）；⑤`npm test` 59→79 全绿（上传客户端包络解析、`mediaUrl`、相册逻辑等 20 例）+ `vue-tsc` + `build:mp-weixin` 通过；走查证据 16 张 `media_*` 存档 `walkthrough/`（头像全链路含服务端文件增删实证、390/375/320 三档、宠物对称）；`impeccable detect` 三个改动 UI 文件零发现。偏差记录：信息卡最终采用记录行列表（非计划两列栅格）；本地联调口径 `/media` 无鉴权（uuid 防枚举，生产切 OSS + 签名 URL）；详见计划与评估文档 v5.13。
- 2026-10-15（甲方四条需求轮）：①输入显示——问答页去自动聚焦 + 输入框 `:cursor-spacing="120"`（新建 4 页一律不自动聚焦）；②回答可读性——后端 `MARKDOWN_FORMAT_RULE` 注入儿童/宠物 Agent + mock 分支 Markdown 化 + `MiniMarkdown` 渲染器（问答/笔记共用）+ `stripMarkdown` 长图去语法；③健康档案——新表 `health_record` + 6 端点（`due_status` 上海时区三态）+ `pages/health/index|edit` +「我的」页入口，复查提醒纯应用内；④笔记——新表 `note`（正文加密 + 乐观锁 1003 + 敏感词 1303）+ 5 端点 + `pages/notes/index|edit` + 入口；⑤本轮修复 6 项缺陷（含 RB-06 儿童同意撤回后健康档案未同步停展）；`npm test` 79→92 全绿（路由白名单同步 15 页）+ `vue-tsc` + `build:mp-weixin`；走查 21 张存档 `walkthrough/`；专项报告 `../docs/测试报告_小程序端甲方需求验收测试_2026-10-15.md`；页数 11→15、组件 10→11。

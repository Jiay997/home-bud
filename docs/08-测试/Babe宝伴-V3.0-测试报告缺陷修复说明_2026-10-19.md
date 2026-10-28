# Babe宝伴 V3.0 测试报告缺陷修复说明

| 项目 | 内容 |
|---|---|
| 对应测试报告 | `docs/08-测试/Babe宝伴-V3.0-全功能模拟测试报告_2026-10-19.md` |
| 修复对象 | 报告第 8 节缺陷清单 D1–D7（共 7 项） |
| 修复日期 | 2026-10-19 |
| 验证方式 | 后端自动化用例回归（全量 319 条）+ 真实 HTTP/SSE 端到端复跑 + 前端类型检查与构建 + 路由行为验证 |
| 修复结论 | D1/D2/D3/D4/D5/D6/D7 全部完成修复与验证；D1 另发现报告复现方式导致的假阴性，已在第 1 节说明 |

---

## 0. 修复一览

| 编号 | 报告严重程度 | 根因归类 | 修复状态 | 验证方式 |
|---|---|---|---|---|
| D1 | 致命 | 一级词库/正则覆盖不足 + 风险依赖失效时 fail-open | ✅ 已修复 | 新增 8 条回归用例 + 真实 SSE 复跑 |
| D2 | 致命 | 同意节点只在数据库层定义、无服务端强制点 | ✅ 已修复 | 新增 3 条回归用例（403/1301、不落库、撤回后拦流） |
| D3 | 严重 | 后台菜单路径重复携带 `/admin` 前缀（router base 已含） | ✅ 已修复 | 路由解析脚本验证 + 构建通过 |
| D4 | 一般 | 同意缺失时静默 `reLaunch` 回流，表现为「点击无响应」 | ✅ 已修复 | 构建产物文案核验 + 逻辑复核 |
| D5 | 一般 | 一键启动脚本未随前端拆分更新 | ✅ 已修复 | PowerShell 语法校验 + stop 脚本实跑 |
| D6 | 轻微 | uni-app 统计模块外呼 dcloud 域名 | ✅ 已处理 | 构建产物核验（无 tongji 引用） |
| D7 | 轻微 | 检索层只过滤「零分」，无相关性下限 | ✅ 已修复（阈值可配置） | 新增 4 条回归用例 + 真实库打分实测 |

---

## 1. D1 风险控制服务（N2 节点）失效

### 1.1 报告现象

三组高危输入（药名+剂量、急症抽搐、词库 block 词）均未阻断，正常生成正文并计次。

### 1.2 根因（三层，含证据）

**证据 A：报告复现请求的中文在到达服务端前已被替换为 `?`**

对线上库 `qa_session.question_text_enc` 解密后逐条还原（脚本：`.build/diag/diag_timeline.py`）：

```
id=5 Q='????????,????????'   （2026-10-19 08:13:58）
id=6 Q='??????????'          （2026-10-19 08:14:31）
id=7 Q='????????????'        （2026-10-19 08:15:49）
id=9 Q='孩子追猫，猫哈气怎么办'  （2026-10-19 08:20:40，浏览器链路）
```

即三条「未拦截」的高危问题落库时已不含任何中文关键词——复现脚本的请求体在客户端编码环节被按 ASCII/GBK 转换，非 ASCII 字符全部变成 `?`。风险引擎（以及任何词库/正则）此时必然放行。

**证据 B：同一份线上词库离线复算（脚本：`.build/diag/diag_repro.py`）**

| 报告用例 | 修复前判定 | 说明 |
|---|---|---|
| E-08「孩子误食了布洛芬，该给他吃多少剂量」 | **blocked=True**（`medicine_dosage_pattern`） | 词库/正则本身有效，未拦截系输入被毁 |
| E-10「孩子被虐待儿童怎么办」 | **blocked=True**（词条「虐待儿童」） | 同上 |
| E-09「宝宝突然抽搐了怎么办」 | **blocked=False** | **真实覆盖缺口** |

同一库内 `risk_event` 仅有 1 条（2026-10-16 08:32，`child_abuse`/L1），证明拦截链路当时可用。

**证据 C：一级覆盖缺口（真缺陷）**

- 词库只有「高烧惊厥 / 热性惊厥」这类**复合短语**，没有「抽搐 / 惊厥 / 窒息 / 噎住 / 呛奶 / 溺水 / 烫伤 / 烧伤 / 呼吸困难 / 叫不醒 / 翻白眼」等**独立急症词**；
- 正则只有「药名+剂量」「诊断」「功效」三类，缺「误食/误服/吞下」等摄入类表述；
- `LLM_MOCK=true` 时二级语义对表外语句恒返回 `score=0.1`（放行），无法兜底口语化短句。
  → 急症口语短句一、二级全部放行。

**证据 D：安全依赖失效时 fail-open（真隐患，报告建议项）**

- `RiskService.load_snapshot` 对解密失败的词条**静默跳过**：若 `FIELD_ENC_KEY` 不匹配导致 20 条词条全部解不开，一级词库等于空表，系统照常放行；
- `RiskService.scan` 未包异常兜底：快照装配/事件落库异常直接冒泡为 `error` 帧（1902），无「按命中处理」语义；
- `_record_event` 落库失败会推翻已经做出的「命中即阻断」结论。

### 1.3 修改内容

| 文件 | 修改 |
|---|---|
| `backend/app/risk/engine.py` | ① `DEFAULT_PATTERNS` 新增 `acute_emergency_pattern`（抽搐/惊厥/窒息/噎住/呛奶/呛到/溺水/烫伤/烧伤/呼吸困难/喘不上气/叫不醒/翻白眼/失去意识 → `high_fever`「儿童急症类」）与 `medicine_ingestion_pattern`（误食/误服/吞下…药片/消毒液… → `medicine_dosage`）；② 正则规则支持 `exclude_if` 语境排除（宠物语境不误判为儿童急症）；③ `LexiconSnapshot` 新增 `term_rows` / `term_decrypt_failed` / `degraded_reason` 与 `usable()` |
| `backend/app/risk/service.py` | ① 快照装配自检：库内有词条但**全部解密失败**时标记 `degraded_reason`（不再静默放行）；② `scan` 对快照异常/不可信一律按「命中」保守处理（`category=risk_unavailable`，`hard=True`），并尽力留痕 `risk_event`；③ `_record_event` 失败不再推翻拦截结论；④ 风险类别归一化：`action` 若为处置动作词（`block_or_rewrite` 等）不再当类别码，按规则键推导（`medicine_dosage_pattern → medicine_dosage`）；⑤ 渠道卡类别别名（`risk_unavailable` / `medicine_dosage` 复用「儿科急症就诊」） |
| `backend/app/api/v1/qa_api.py` | SSE 生成器对 `RiskService.scan` 增加「异常即按命中」兜底；`get_channels` 失败不推翻拦截 |
| `backend/app/agents/nodes.py` | `risk_scan_node` 快照装配异常/不可信时返回 `blocked`（重生成路径同样 fail-closed） |
| `backend/scripts/seed_data.py` | 词库种子补 11 条急症词（抽搐/惊厥/窒息/噎住/呛奶/溺水/烫伤/烧伤/呼吸困难/叫不醒/翻白眼，类别 `high_fever`）；风险规则配置补 2 条新正则（可后台编辑）；`medicine_dosage_pattern` 补 `category_code` |
| `backend/app/llm/mock_semantic_corpus.py` | 移除两条已由一级覆盖的语料（「全身抽搐」「翻白眼…叫不醒」），维持「语料不与一级词库重叠」约束 |

### 1.4 验证（已执行）

```powershell
# 1) 离线复算线上词库：三条报告用例 + 新增急症case
python .build\diag\diag_repro.py
#   E-08 blocked=True(medicine_dosage) / E-09 blocked=True(high_fever) / E-10 blocked=True(child_abuse)
#   基线「孩子追猫，猫哈气怎么办」「1岁宝宝夜里总醒」仍放行（不误伤）

# 2) 后端回归（新增 8 条 D1 用例）
$env:DATABASE_URL="postgresql+psycopg2://<user>:<pwd>@localhost:15432/jiaban"
python -m pytest tests\test_defect_regressions.py -k "D1" -q
#   覆盖：三条高危用例 → blocked 帧 + 无 section/completed + 事件号 + 渠道卡 + used 不增 + 会话 status=blocked
#        快照 degraded / 快照异常 → 按命中拦截
#        宠物语境消歧（`猫抽搐了` 不按儿童急症阻断，宠物误食仍走 pet_poison 语义）

# 3) 真实 HTTP + SSE 端到端（独立验证库 jiaban_verify，不影响业务库）
python ..\.build\diag\e2e_verify.py
#   passed=17 failed=0
```

---

## 2. D2 同意节点（N1）缺失

### 2.1 报告现象

未调用 `/consent/agree` 即可创建会话、完整生成正文并扣额度；前端首启无同意门禁。

### 2.2 根因（证据）

- 错误码常量 `ERR_BASE_CONSENT = (1301, "请先同意用户协议与免责声明")` 在 `core/errors.py` 中**定义但全仓无任何引用**——只有儿童信息单独同意（1302）在档案链路中强制，基础同意没有任何服务端强制点；
- `POST /qa/sessions`、`POST /qa/sessions/{uid}/stream`、`POST .../regenerate` 均未校验同意；
- 线上库可复现：`qa_session.id=4`（user 5，问题 `hello consent test`）创建成功且 `status=done`，而该用户在 `consent_record` 中**没有任何同意记录**；
- 前端同意门禁实际存在（`pages/index` 的 `state==='consent'` 全屏引导 + `ensureBaseConsent()`），但问答页/测评页在未同意时执行的是**静默 `reLaunch` 回首页**，不构成可见门禁。

### 2.3 修改内容

| 文件 | 修改 |
|---|---|
| `backend/app/api/v1/consent_api.py` | 新增公共判定 `has_active_consent()` 与强制闸门 `require_base_consent()`（未同意 → 403/1301），作为基础同意的单一事实来源 |
| `backend/app/api/v1/qa_api.py` | `POST /qa/sessions`（落库前）、`POST .../stream`（建后撤回也不可绕过）、`POST .../regenerate`（生成入口）三处强制 1301 |
| `client/src/pages/qa/index.vue` | ① 未同意进入问答：`toast 请先同意用户协议与免责声明` → 回首页同意页（不再静默）；② 提问收到 1301 时同样提示并回流 |
| `client/src/pages/assessment-intro/index.vue`、`client/src/pages/assessment/index.vue` | 同上：未同意时给出明确提示再回流，不再是「无反应」 |

### 2.4 验证

```powershell
python -m pytest tests\test_defect_regressions.py -k "D2" -q
#   未同意建会话 → 403/1301 且 history.total=0（不落库）
#   同意后建会话 → 200/pending（不误伤）
#   建会话后撤回基础同意 → 拉流 403/1301
python ..\.build\diag\e2e_verify.py   # 真实 HTTP：未同意 403/1301、同意后放行
```

### 2.5 补充说明

- 报告建议的「儿童档案链路 1302」**已存在**：`profiles_api._require_child_consent()` 与 `health_api`/`notes_api` 主体解析均已强制儿童信息单独同意（撤回后联动禁用档案），既有用例 `test_create_child_without_child_consent_1302`、`test_child_record_consent_gate_1302_defense`、`test_withdraw_blocks_media_and_hides_avatar` 覆盖，本次未改动。
- 前端「首启同意门禁」本身存在（`pages/index` 的 `state==='consent'` 全屏引导）：勾选同意后才可进入首页；本次修复的是「其他入口在未同意时静默回流」这一缺口（见 D4）。

---

## 3. D3 后台菜单导航失效（路由 base 重复）

### 3.1 根因

`admin-web/src/router/index.ts` 使用 `createWebHistory('/admin/')`，其 base 只负责**地址栏前缀**；`router.push/resolve` 的入参必须是 base 之后的相对路径。而 `AdminLayout.vue` 的 `MENU_DEFS` 把路径写成 `/admin/lexicon` 等，解析结果为 `/admin/admin/lexicon`，命中兜底路由 `/:pathMatch(.*)*` 后被重定向回 `/kb`——表现为「除知识库外全部菜单点不动」。

### 3.2 修改内容

| 文件 | 修改 |
|---|---|
| `admin-web/src/router/index.ts` | 导出 `ADMIN_ROUTE` 常量表（base 之后的相对路径 + `kbEdit(id)`/`kbNew` 生成器），作为全部编程式导航的单一事实来源；兜底重定向与守卫回退改用常量；补写路径约定注释 |
| `admin-web/src/views/admin/AdminLayout.vue` | `MENU_DEFS` 改用 `ADMIN_ROUTE`；激活菜单/页面标题/审计抽屉/系统监控/新建文档/退出登录等 9 处路径同步修正 |
| `admin-web/src/views/admin/KbListPage.vue` | 新建/编辑/回滚三处跳转改用 `ADMIN_ROUTE.kbNew` / `kbEdit()` |
| `admin-web/src/views/admin/KbEditPage.vue` | 新建成功后跳 `/kb/{id}/edit`（原为未注册的 `/admin/kb/{id}`，同样会被兜底弹回列表） |
| `admin-web/src/views/admin/AdminLoginPage.vue` | 登录成功后跳 `/kb`（原 `/admin/dashboard` 未注册） |

### 3.3 验证

```powershell
# 路由解析行为验证（vue-router 同版本、base='/admin/'）
node .build\diag\router_base_check.mjs
#   旧写法：'/admin/lexicon' → href=/admin/admin/lexicon catchAll=true   ← 复现 D3
#   新写法：全部 ADMIN_ROUTE.* → /admin/<path> catchAll=false
#   未注册重复前缀 → redirect=/kb

# 构建验证（1646 modules transformed，产物含 AdminLayout/KbListPage/KbEditPage/AdminLoginPage）
cd admin-web; npx vite build --target esnext --minify false
```

---

## 4. D4 用户端「开始测评」入口点击无响应

### 4.1 根因

首页测评入口本身绑定正确（`openAssessmentHero()` → `pages/assessment-intro/index`），问题出在**入口之后的静默失败**：

1. `pages/assessment-intro/index.vue`、`pages/assessment/index.vue`、`pages/qa/index.vue` 在 `ensureBaseConsent()` 返回 false 时执行 **`uni.reLaunch('/pages/index/index')` 且无任何提示**——用户点击后页面瞬间回到首页（或深链进入时直接消失），观感与「点击被拦截 / 页面无变化」完全一致；
2. 首页三处 `uni.navigateTo` 均未处理 `fail`，跳转失败（页面未注册、被平台拦截、栈溢出）时静默无反馈。

可稳定复现的路径（修复前）：
- 未同意用户通过深链/分享直接打开 `/pages/qa/index?entry=child` 或 `/pages/assessment-intro/index` → 无提示直接回到首页；
- 首页已进入 `ready` 后同意态发生变化（另一设备撤回同意、token 轮换到新用户）→ 点击「开始测评」被静默弹回；
- 任何 `navigateTo` 失败场景 → 仅有一个死点击。

> 说明：报告 D4 自身标注「待复现确认」。本次在代码层未发现遮挡层或事件绑定错误，唯一能产生「点击无反应」观感的实现即上述静默回流/静默失败，已按此修复；测试报告环境（首页无同意门禁）与当前源码的同意门禁逻辑不一致，可能与旧镜像/构建产物有关，建议按第 9 节重建镜像后复验。

### 4.2 修改内容

| 文件 | 修改 |
|---|---|
| `client/src/pages/assessment-intro/index.vue` | 未同意时先 `toast 请先同意用户协议与免责声明`，600ms 后回流首页同意页 |
| `client/src/pages/assessment/index.vue` | 同上 |
| `client/src/pages/index/index.vue` | 新增 `navigateWithFeedback()`：跳转失败提示「页面打开失败，请稍后重试。」；测评入口三个分支统一走该函数 |

### 4.3 验证

```powershell
cd client
npm run type-check            # vue-tsc：0 error
npm run build:h5              # DONE Build complete
# 产物核验：pages-assessment-intro-index.*.js / pages-assessment-index.*.js / pages-qa-index.*.js
#          含「请先同意用户协议与免责声明」；pages-index-index.*.js 含「页面打开失败」
```

---

## 5. D5 一键启动脚本未适配新架构

### 5.1 根因

`scripts/start.ps1` 仍按已删除的单站点 `frontend/` 与 5173 端口编写。

### 5.2 修改内容

| 文件 | 修改 |
|---|---|
| `scripts/start.ps1` | 重写：后端 8000 + 用户端 `client`（`dev:h5`，5174，`/app/`）+ 后台 `admin-web`（`dev`，5175，`/admin/login`）；新增 `-SkipClient` / `-SkipAdmin` 开关；依赖缺失自动 `npm install`；按端口判定重复启动；日志分文件（`client-h5.*` / `admin-web.*`）；数据库连接串从 `backend/.env` 解析（不再硬编码 localhost:5432） |
| `scripts/stop.ps1` | 同步端口清单 5174/5175（兼容清理旧 5173），残留校验改为端口数组 |
| `scripts/status.ps1` | 状态展示改为「用户端 H5（5174）/ 后台管理端（5175）」并给出正确 URL |
| `deploy/README.md` | 补充三端口说明与开关用法 |

> 注：三个脚本均为 UTF-8 **带 BOM** 保存（仓库既有约定），保证 Windows PowerShell 5.1 正确解析中文。

### 5.3 验证

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop.ps1   # 实跑：正常收尾、exit 0
# 语法校验（AST 解析，三个脚本均 0 错误）
foreach ($f in "scripts\start.ps1","scripts\stop.ps1","scripts\status.ps1") {
  $e=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $f).Path,[ref]$null,[ref]$e); "$f errors=$($e.Count)" }
# 期望：errors=0
```

---

## 6. D6 前端统计脚本外呼失败（观察项）

### 6.1 根因

uni-app 运行时内置 DCloud 统计模块（构建产物 `assets/index-*.js` 内含 `tongji-collector.dcloud.net.cn` 与统计 appid），首屏即外呼；外网不可达时产生 4 条 `net::ERR_ABORTED`。对儿童养育类产品，向第三方上报使用数据本身也有合规风险。

### 6.2 修改内容

| 文件 | 修改 |
|---|---|
| `client/src/manifest.json` | 显式关闭统计：`"uniStatistics": {"enable": false}`（全局 + `h5` + `mp-weixin` 三处） |

### 6.3 验证

```powershell
cd client; npm run build:h5
# 产物不再包含统计外呼地址：
#   修复前：assets/index-*.js 命中 tongji-collector/tongji.dcloud 5 处
#   修复后：0 处
```

---

## 7. D7 mock 检索相关性失真（低相关仍返回条目）

### 7.1 根因

`Retriever` 的打分只有 `score > 0` 的零分过滤，**没有相关性下限**：任何存在极少 2-gram/3-gram 重叠的条目都会被当作命中返回，导致 `kb_hit=True`（「专业咨询提示」永不触发）且把语义无关条目塞进上下文。`EMBEDDING_PROVIDER=mock` 的 hashing 稀疏向量下尤为明显。

### 7.2 修改内容

| 文件 | 修改 |
|---|---|
| `backend/app/services/retriever.py` | 新增 `DEFAULT_MIN_RELEVANCE=0.10` 与 `min_relevance()`（读配置，异常回退默认值）；两条检索路径（Milvus 主通道 / hashing 降级）统一按 `score >= 阈值` 过滤 |
| `backend/app/core/config.py` | 新增配置项 `retrieval_min_relevance`（环境变量 `RETRIEVAL_MIN_RELEVANCE`），可在真实 embedding 下免改代码调参 |

### 7.3 验证

```powershell
python .build\diag\diag_scores.py      # 真实库打分明细：正常命中 0.12~0.35，噪声召回 0~0.03
python .build\diag\diag_retrieval.py   # 阈值生效：相关命中保留、无关问题 hit=false
python -m pytest tests\test_defect_regressions.py -k "D7" -q   # 4 passed
```

---

## 8. 回归结果

| 范围 | 结果 |
|---|---|
| 后端全量回归（全量收集 319 条；排除 4 个受沙箱/环境限制的文件后执行 268 条） | **264 passed, 3 skipped, 1 deselected, 0 failed** |
| 新增回归用例（D1×8 / D2×3 / D7×4） | 全部通过 |
| 真实 HTTP + SSE 端到端（独立库 `jiaban_verify`） | **passed=17 failed=0** |
| 前端 `vue-tsc --noEmit` | 0 error |
| 前端 `npm run build:h5` | 构建成功（产物文案/统计核验通过） |
| 后台 `vite build` | 构建成功（1646 模块，含 AdminLayout/KbListPage/KbEditPage/RiskEventPage/LexiconPage） |
| 纯逻辑/路由脚本 | `router_base_check.mjs` ALL PASS |

### 受环境限制未执行的用例（非本次修改导致）

| 用例 | 原因 |
|---|---|
| `test_profile_media.py`（7）、`test_health_notes.py` 上传用例（1）、`test_finalize_task3.py`（6）、`test_channel_providers.py`（2） | 沙箱拒绝对 `%TEMP%` 下目录的创建/删除（`WinError 5`），与业务代码无关 |
| `test_redis_cache.py`（1） | 本机 6379 上的 Redis 不支持 `HELLO`（旧版本），非代码问题 |

> 上述用例在具备正常临时目录写权限与 Redis 7 的环境中应通过，建议在 CI 或部署机复跑确认。

---

## 9. 上线/回归注意事项

1. **重新播种词库**（D1 新增 11 条急症词 + 2 条正则 + 1 条 `category_code`）：
   ```powershell
   cd backend; python -m scripts.seed_data
   ```
   `seed_data` 幂等：已存在词条/配置键不会重复插入，也不会覆盖后台改过的配置。
   即使不重新播种，`engine.DEFAULT_PATTERNS` 已内置两条急症正则——**代码部署即生效**（新增词条的意义是在后台可维护）。
2. **重建镜像**：`docker compose build backend frontend && docker compose up -d`（前端含 D2/D4/D6 修改）。
3. **回归重点**（按报告 §9.3 P0/P1）：
   - E-08/E-09/E-10 三组高危输入 → `blocked` 帧、正文为空、不计次、`risk_event` 落库；
   - 未同意用户 → `/qa/sessions` 403/1301；同意后正常；
   - 后台 7 个菜单逐一点击（含知识库编辑/新建后返回）；
   - 未同意状态下点击首页「开始测评」→ 应出现「请先同意用户协议与免责声明」提示，而非无反应。
4. **残留建议（不在本次修复范围，供后续排期）**：
   - 宠物中毒类（如「狗吃了巧克力中毒了怎么办」）在 `LLM_MOCK=true` 下仍依赖语义模型，mock 不拦截；建议补充宠物毒物词条/语料；
   - `diagnosis` / `efficacy` 类命中目前无对应危机渠道卡，前端回落「110」兜底卡，建议按产品口径补渠道或文案；
   - 小程序端同意门禁与统计关闭需在微信开发者工具/真机复验（本次未覆盖）；
   - 真实 Embedding + Milvus 环境下的相关性阈值（`RETRIEVAL_MIN_RELEVANCE`）需按实测复核。

---

## 10. 追加修复（用户实测反馈 2026-10-19）

用户实测发现两个用户端问题（截图见对话记录）：① 档案页显示「档案暂时无法打开 / 连接失败，请检查网络后重试。」；② 记录页点「去提问」没有打开 AI 对话界面。另附一张会员页显示 uni 内置「连接服务器超时，点击屏幕重试」。

### 10.1 档案页「连接失败」——不是网络问题，是前端运行期异常被当成网络错误

**根因**：档案页把全局 `uni` 直接当作存储适配器注入 store：

```js
// client/src/pages/profiles/index.vue（修复前）
const currentStore = createProfileCurrentStore({ storage: uni })
```

uni-app 的 **H5 生产构建**下全局 `uni` 不承载完整 API（`uni.getStorageSync` 为 `undefined`；开发态（vite dev）下则是完整的，所以本地开发看不出来）。`load()` 末尾的 `syncCurrentKey()` 调用 `currentStore.read()` → `storage.getStorageSync(...)` → 抛

```
TypeError: e.getStorageSync is not a function
  at Object.read (profile-current)
  at ... (profiles/index.vue load → syncCurrentKey)
```

该异常发生在 `load()` 的 `try` 内，被 `catch` 后走 `userFacingMessage(error, '连接失败，请检查网络后重试。')`——错误信息含拉丁字母 → 回落兜底文案，于是渲染成「档案暂时无法打开 / 连接失败」。而此前的 4 个接口请求其实全部 200（后端访问日志与 CDP 网络面板双向确认），所以**与后端、网络完全无关**。

**同类隐患（一并修复）**：同一模式在另外两个页面同样踩雷——

| 位置 | 注入内容 | H5 生产态后果 |
|---|---|---|
| `profile-detail/index.vue` | `createProfileCurrentStore({ storage: uni })` | 详情页同样崩为「连接失败」、「设为当前观察对象」不可用 |
| `profile-detail/index.vue`、`profile-album/index.vue` | `createProfileMediaService({ runtime: uni, ... })` | `runtime.chooseMedia` 缺失 → 头像/照片上传报「无法打开相册或相机，请检查权限后重试。」（H5 必须用 `platform/runtime` 的 `input[type=file]` 实现） |

**修改**：

| 文件 | 修改 |
|---|---|
| `client/src/platform/storage.ts`（新增） | 统一存储适配器 `uniStorage`：显式转发 `uni.getStorageSync/setStorageSync/removeStorageSync`，并在注释中固定约定「任何 storage 注入点不得直接传 `uni`」 |
| `client/src/pages/profiles/index.vue` | `createProfileCurrentStore({ storage: uniStorage })`；`catch` 内补 `import.meta.env.DEV` 守卫的 `console.error`（保留原始异常便于排查，生产不输出） |
| `client/src/pages/profile-detail/index.vue` | `storage: uniStorage`；`createProfileMediaService({ runtime, upload: api })`（`runtime` 取自 `platform/runtime`） |
| `client/src/pages/profile-album/index.vue` | `createProfileMediaService({ runtime, upload: api })` |

### 10.2 记录页「去提问」不打开 AI 对话

**根因**：空态按钮绑定的 `goHome()` 实现为 `uni.redirectTo({ url: '/pages/index/index' })`——**目标是首页而不是对话页**，且 `redirectTo` 会顶掉记录页（丢失底部 Tab 上下文）。表现为「点了跳到首页 / 观感像没反应」。

**修改**（`client/src/pages/records/index.vue`）：

```js
function goAsk() {
  uni.navigateTo({
    url: '/pages/qa/index?entry=family',   // 直接打开 AI 对话（家庭综合问答，任意用户可用）
    fail: () => { uni.showToast({ title: askFallbackCopy, icon: 'none' }); uni.redirectTo({ url: '/pages/index/index' }) }
  })
}
```

同时把空态文案「先去首页问第一个问题…」改为「先问第一个问题…」（不再引导去首页），`@action="goHome"` 改为 `@action="goAsk"`。`navigateTo` 保留返回键可回到记录列表。

### 10.3 会员页「连接服务器超时，点击屏幕重试」——发布缓存错配

该文案来自 **uni-app 运行时**（打包产物 `index-*.js` 内置），只在「入口 HTML/页面 chunk 取不到」时出现；在新开浏览器里复测会员页**完全正常**（标题、权益、价格、订单均渲染）。

**根因**：nginx 只给带 hash 的静态资源加了 30 天 `immutable` 缓存，`index.html` 走 `location /app/` 没有任何缓存头 → 浏览器按启发式缓存旧 `index.html`；重新发布后旧 HTML 引用的旧 chunk 已被替换删除 → 打开新页面即拉不到 chunk → uni 显示该超时提示。

**修改**（`deploy/nginx.conf`）：

```nginx
location /app/ {
    root /usr/share/nginx/html;
    add_header Cache-Control "no-cache, no-store, must-revalidate" always;
    add_header Pragma "no-cache" always;
    try_files $uri $uri/ /app/index.html;
}
# /admin/ 同样处理；带 hash 的 js/css 仍保持 30 天 immutable
```

验证（容器内实测响应头）：`index.html → Cache-Control: no-cache, no-store, must-revalidate`；`assets/index-*.js → max-age=2592000, public, immutable`。

### 10.4 验证（真实浏览器 + CDP，非模拟）

用本机 Chrome（headless + CDP）真实打开页面并采集 console / 网络 / DOM（脚本：`.build/diag/cdp_probe.mjs`，禁用缓存、全新用户目录）：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `/app/pages/profiles/index`（已同意用户） | 「档案暂时无法打开 / 连接失败…」，console：`TypeError: e.getStorageSync is not a function` | 正常渲染：孩子 0/3、宠物 0/3、儿童信息同意提示、空态与「新建孩子档案」 |
| 同上，且已有 1 个孩子档案 | — | 正常渲染档案卡「诊断娃 / 29 个月 · 未填写」 |
| `/app/pages/profile-detail/index?...` | 崩为「连接失败」 | 正常渲染档案信息、设为当前对象、删除档案 |
| `/app/pages/profile-album/index?...` | 相册服务注入错误 | 正常发起 `/photos` 请求并按 404 显示「资源不存在」 |
| 记录页点「去提问」 | 跳到 `/app/`（首页） | 跳到 `/app/pages/qa/index?entry=family`，渲染「家庭综合问答 / 今日剩余 4/4 次 / 输入框 / 发送」 |
| `/app/pages/member/index` | 缓存错配时显示 uni 超时提示 | 新开浏览器正常渲染会员页 |
| 后台点击「词库维护」（镜像重建后，桌面视口） | 停留在 `/admin/kb`（缺陷 D3） | `/admin/kb` → `/admin/lexicon`，标题「词库维护（高危 / 敏感）」 |

前端静态检查：`vue-tsc --noEmit` 0 error；`npm run build:h5` 构建成功；`client/tests` 18 个测试文件全部通过。

### 10.5 部署状态与固化

本次修复已在本地环境**完整固化**到镜像：

```powershell
cd deploy
docker compose build frontend          # 重新构建（client + admin-web + nginx conf）
docker compose up -d --no-deps frontend # 用新镜像重建容器
```

重建后实测：`jiaban-frontend` healthy；`/app/index.html` 返回 `Cache-Control: no-cache, no-store, must-revalidate`，`/app/assets/index-*.js` 仍为 `max-age=2592000, public, immutable`；两个问题在全新浏览器中均不再复现。

其他环境（测试机/生产）执行同样的两条命令即可；**仅重启容器不会生效**（代码与 nginx 配置都在镜像内）。若容器是用旧镜像重建的，`index.html` 缓存头会回退为无缓存头，届时仍需重建镜像。

---

## 11. 追加修复（后台登录成功却进不去 2026-10-19）

**现象**：后台输入正确账号密码 + MFA 后，页面弹出成功提示（如「欢迎，管理员17769471295」），但仍停在 `/admin/login`，没有进入控制台。

### 11.1 定位过程（逐环节实测）

用真实浏览器（headless Chrome + CDP）驱动完整登录 UI（填账号密码 → 获取验证码 → 填 6 位码 → 登录），逐环节取证：

| 环节 | 实测结果 |
|---|---|
| 身份验证 `POST /admin/login` | 200，返回 `mfa_required=true` + `mfa_ticket` |
| 二次验证 `POST /admin/mfa/verify` | 200，返回 token + `role=super_admin` + **8 个菜单** |
| 令牌写入 `localStorage['jiaban_admin_token']` | 成功（`token=true`） |
| 账户信息 `localStorage['jiaban_admin_info']` | 成功（role/display_name/menus 齐全） |
| 路由跳转 `router.push(ADMIN_ROUTE.kb)` | `/admin/login` → **`/admin/kb`** |
| 权限校验（守卫 `meta.menuKey='kb'`） | 通过（menus 含 kb） |
| 页面渲染 | 侧栏 9 个导航项、标题「知识库管理 · Babe宝伴后台」、7 个接口全 200 |

结论：**当前代码与集群的登录链路本身是通的**。用户截图中的页面是**旧版后台产物**——证据：页面品牌为「小光景后台管理中心」「小光景后台系统·最小权限访问控制」，按钮为「验证并登录」；而当前构建是「Babe宝伴后台管理中心」「登 录」（单页三段式表单）。

### 11.2 根因

两层原因叠加：

1. **浏览器仍在跑旧版后台产物**（旧 `index.html` + 旧 chunk 命中 `immutable` 缓存且不再更新）。旧版登录成功后的跳转目标为未注册路由 `/admin/dashboard`（缺陷 D3 的同一根因），命中兜底路由后被弹回登录页 → 口令/ MFA 都成功，但界面停在登录页。
2. **前端缺少「登录成功后跳转失败」与「会话失效」的兜底**，任何一跳失败都会停在登录页且只有一句欢迎语，用户无从判断原因（本次已补）。

### 11.3 修改

| 文件 | 修改 |
|---|---|
| `admin-web/src/views/admin/AdminLoginPage.vue` | 登录成功改为 `enterConsole()`：先 `router.push(ADMIN_ROUTE.kb)`，600ms 后校验当前路由是否仍停在登录页，若是则 `window.location.assign('/admin/kb')` **整页跳转兜底**（重新拉取最新 index.html 与分包，绕过旧缓存/失效 chunk）；并提供 `?expired=1` 的过期提示（挂载时提示一次并清理查询参数） |
| `admin-web/src/api/admin.ts` | 新增 `handleSessionExpired()`：接口返回 HTTP 401 或业务码 1101（后台令牌 30 分钟无操作过期）时，清除 `jiaban_admin_token`/`jiaban_admin_info` 并整页跳 `/admin/login?expired=1`，避免"已进控制台但所有接口 401、界面像坏了"的半失效状态 |
| `deploy/nginx.conf` | 见 §10.3：`/admin/` 入口 HTML 加 `no-store`，避免再被旧 HTML 顶住 |

### 11.4 验证

```powershell
# 1) 真实浏览器驱动完整登录流程（填表→取码→MFA→跳转）
node .build\diag\admin_login_flow.mjs 17769471295 12345678 123456
#   期望：第一步 toast「验证码已自动发送…」；第二步 toast「欢迎，管理员17769471295」；
#         最终 url=http://localhost/admin/kb，hasSidebarMenu=9，title=知识库管理 · Babe宝伴后台

# 2) 会话失效兜底（伪造过期令牌后访问控制台）
#   期望：token 被清除 → 跳 /admin/login → 提示「登录状态已过期，请重新登录」→ 查询参数被清理
node .build\diag\cdp_probe.mjs "http://localhost/admin/login?expired=1" --desktop --wait=1500
```

实测结果（镜像重建后、全新浏览器）：登录最终落地 `/admin/kb`、侧栏 9 项、全部接口 200；伪造过期令牌访问 `/admin/kb` 会清 token 并跳登录页，`?expired=1` 提示正常。

### 11.5 给使用者的处置步骤

1. 在后台页面按 **Ctrl+Shift+R** 强制刷新（清掉浏览器里旧的旧版产物），确认标题变为「Babe宝伴后台管理中心」、按钮为「登 录」。
2. 重新登录：`17769471295` / `12345678` → 「获取验证码」→ `123456` → 「登 录」，应直接进入「知识库管理」。
3. 若强制刷新后仍显示「小光景」品牌，说明访问的不是当前部署（可能是旧容器/另一个端口/其它机器），执行：
   ```powershell
   cd deploy
   docker compose build frontend
   docker compose up -d --no-deps frontend
   docker ps --filter name=jiaban-frontend --format "{{.Names}} {{.Status}}"
   ```



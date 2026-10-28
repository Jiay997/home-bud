# Babe宝伴 V3.1 开发完成情况与测试报告

| 项目 | 内容 |
|---|---|
| 报告日期 | 2026-10-20 |
| 评估基线 | `docs/08-测试/Babe宝伴-V3.1-项目完成情况与进度评估报告_2026-10-20.md`（开发前评估：综合完成度 ≈62%，5 项上线阻塞未清零） |
| 需求基线 | `docs/02-基线/宝伴-PRD_V3.1.md`（RQ-01～RQ-14） |
| 本次范围 | 按评估报告的 P0/P1/P2 优先序，落地 RQ-01～RQ-14 后端能力 + C 端界面 + 后台界面；修复缺陷 N1～N5（含评估报告 P1 第 6–9 项） |
| 测试方式 | 单元测试（pytest / node:test）+ 集成测试（FastAPI TestClient 全链路）+ 系统测试（真实 HTTP/SSE 端到端 63 例 + 并发压测）+ 静态门禁（契约 / 文案 / 号码 / 文档一致性） |
| 证据原则 | 本报告所有数字均来自实际执行输出，未执行或受限项如实标注 |

---

## 一、结论速览

| 维度 | 开发前 | 开发后 |
|---|---|---|
| V1.0 阻塞项（RQ-01/02/03/06/07/08） | 0 完成 / 3 部分 / 3 未开始 | **6 项功能全部实现**；RQ-03 号码回填、RQ-06 专家会签仍待外部事实输入 |
| V1.1 增量（RQ-04/05/09/10/11/12/13/14） | 0/8 未开始 | **7 项实现**（RQ-10 按 PRD 仅建表不开放功能，见 §五） |
| 后端端点 | 113 | **153**（`docs/API.md` 与 OpenAPI 零偏差） |
| 后端业务表 | 38 | **49**（V3.1 新增 11 张） |
| C 端页面 | 15 | **19**（隐私承诺 / 提醒设置 / 轻工具 / 专题包） |
| 后台页面 | 8 | **11**（危机渠道清单 / 分级规则 / 内容运营；另拆分权利请求与系统配置） |
| 后端测试 | 302 passed / 10 failed / 8 errors（本机环境态） | **408 passed / 4 skipped / 0 failed** |
| 契约与文档 | 113 端点、需手工核对 | **153 端点零漂移**（脚本自动校验） |
| 发布门禁（§7.2 四项） | 4 项全未通过 | **2 项通过**（AI 标识三链路、拟人化零命中）；**2 项待外部事实输入**（渠道核验、规则会签）——系统如实显示未通过 |

**一句话**：V3.1 的**代码与测试工作已完成**；剩余 2 项阻塞门禁不是代码缺口，而是**必须由业务/专家/法务提供事实数据**（渠道号码与拨测、规则书面会签、订阅模板报备、Q-54 定性），系统对未达标状态不做粉饰。

---

## 二、分需求交付明细

| RQ | 交付内容 | 关键实现位置 | 测试覆盖 |
|---|---|---|---|
| **RQ-01** AI 标识全链路 | ① 页面固定位标识由服务端下发 `ai_label`（`text_id` / `position` / 兜底文案 / 备案号）；② 长图显式标识面积 ≥15%、出现 ≥2 处（页首带 + 页尾徽标 + 页尾常显，对角分布）；③ 导出 PNG 统一写入 `tEXt`（`software=BabeJiabanAI`、`ai_generated=1`、`content_type`、`generated_at`、`render_id`）并**写入后回读断言**；④ 客户端 canvas 产物经 `POST /compliance/png-metadata` 补齐隐式标识；⑤ 无「纯净版」开关 | `app/compliance/ai_label.py`、`app/services/png_meta.py`、`app/services/report_image.py`、`app/api/v1/share_api.py`、`app/api/v1/compliance_api.py` | 13 例（含剔除元数据后必须失败的 fail-closed 断言、幂等重写、非 PNG 拒绝） |
| **RQ-02** 拟人化合规 | ① 禁用表述词表（27 条 + 变体映射）入库为 `lexicon_type=anthropomorphic`，**不参与**输入侧拦截；② 全仓库扫描（去空白/全角归一/变体归一）+ 变体注入自检 + fail-closed；③ 检查清单 5 项随接口下发；④ 副标题全量改为「养育科普参考工具」（代码 + 活文档，共 18 处） | `app/compliance/copy_scan.py`、`scripts/copy_compliance_check.py` | 12 例 + CI 门禁脚本 PASS |
| **RQ-03** 渠道清单单一数据源 | ① 收敛旧「配置项 + 表」双轨，前后台统一读 `crisis_channel`；② 号码未回填 → 占位「维护中」，**不编造**；③ 复核到期自动转 `pending_review` 且不再下发号码（定时任务 + 读时兜底）；④ 核验记录表（方式/结论/核验人/版本，≥3 年）；⑤ 改号码二次确认（确认令牌 + 编码后 4 位 + 原因）；⑥ 客服角色号码脱敏 `***`；⑦ CI 断言源码无硬编码号码 | `app/services/channel_service.py`、`app/api/v1/admin_v31_api.py`、`scripts/check_hardcoded_phones.py` | 9 例（含 N3 回归、超期降级、脱敏、二次确认三态） |
| **RQ-06** 分级决策 | ① 规则引擎（场景识别 → 体温/时长/精神状态信号提取 → 条件匹配 → 档位裁决），**纯函数毫秒级**；② 首批 5 类模板 + 22 条规则（含新增「发热伴抽搐」硬规则）；③ 硬规则 `<3 月龄 ≥37.5℃ 必 🔴`；④ 输出 `triage` 对象（档位/命中规则/观察项/升级红旗/禁忌/免责/夜间提示/规则版本）；⑤ 编排图新增 `triage` 节点（风险放行后、正文前）；⑥ 档位卡 + 红旗块置顶；⑦ 追问重判 + 🟢→🔴 强提醒；⑧ 后台规则编辑 + 专家会签 + 门禁状态 | `app/triage/`、`app/agents/nodes.py`、`app/api/v1/triage_api.py`、`app/api/v1/admin_v31_api.py` | 28 例（含 AC-RQ06-2 两例、夜间态、无确定性结论扫描、P95<300ms 性能断言、拦截优先于分级） |
| **RQ-07** 信任叙事 | ① 信任条四要素（AI 标识 / 月龄适配 / 来源等级徽标 A–D / 档位徽标）；② 首答信任检查单 10 项随契约下发；③ 禁忌区置顶；④ 要素缺失显示「信息待补」并上报，不隐藏；⑤ 无档案显示「通用区间」+ 建档引导；⑥ 来源徽标展示适用范围说明，**不展示原始链接** | `app/services/trust_service.py`、`app/services/answer_contract.py` | 覆盖 SSE / 轮询 / 断线续发 / 历史详情**四条链路**一致性 |
| **RQ-08** 留存触达 | ① `reminder_task` / `notification_pref` 表；② 儿童疫苗 13 节点 + 体检 4 节点、宠物疫苗年免 + 驱虫周期；③ 成长周报（仅主题标签，不含问答原文）与每周一问；④ 周频控 ≤2 条、超频**顺延不丢弃**、同日合并（合并项不计入频控分子）；⑤ 退订即停 + 站内周报可回看；⑥ `reminder_trace_id` 归因透传到会话；⑦ 模板未报备走站内补达（不伪造外发成功）；⑧ 定时任务每小时扫描 | `app/services/reminder_service.py`、`app/api/v1/reminders_api.py`、`app/jobs/scheduler.py` | 11 例（含频控顺延、退订停发、归因落库、周报隐私口径） |
| **RQ-05** 图片提问 | ① 场景化前置说明（5 类场景 + 拍摄要点 + 隐私告知 + 24h 删除承诺）；② 上传 → 送检（未通过/超配额即拒绝且**不扣额度**）→ 绑定会话 → 24h 删除任务 + 删除日志；③ EXIF 在重编码时剥离；④ 库内只存元数据（无原图、无 URL），**不提供任何原图查看接口**；⑤ 会话 `input_mode` / `photo_meta`；⑥ 有儿童档案时强制儿童信息单独同意（1302）；⑦ 多模态未接入时正文前置「图片未解析」说明，不假装理解 | `app/services/photo_service.py`、`app/api/v1/photo_api.py` | 5 例（含删除日志、配额超限不扣额度、张数上限、儿童同意门禁） |
| **RQ-09** 分享长图 | ① 服务端模板渲染（信任条 + 正文 + 免责 + 双标识）；② 被拦截/未完成会话 403；③ 24h 复用同一 `render_id` 与 `share_trace_id`；④ 仅昵称与月龄档（脱敏）；⑤ 响应头暴露 `X-AI-*` 便于抽检 | `app/services/share_service.py`、`app/api/v1/share_api.py` | 2 例（PNG 元数据 + 被拦截 403） |
| **RQ-11** 隐私承诺 | 承诺页只列已实现能力，每条附可操作跳转与实现依据；「不用于训练」限定为自有模型口径；附诚实说明 | `app/services/privacy_service.py`、`client/src/pages/privacy-pledge` | 5 例 |
| **RQ-12** 轻工具 | 3 个工具（发烧自查 / 宠物行为自查 / 宠粮配料表解析）；不消耗额度；内容命中「能吃/不能吃」确定性结论即拒绝保存；首页四入口不变，收纳于「工具」次级入口 | `app/services/tool_service.py`、`app/api/v1/tools_api.py`、`client/src/pages/tools` | 5 例 + 后台保存拒绝用例 |
| **RQ-13/14** 专题包 | 交叉主题包须育儿 + 宠物**双签**才可上架、红旗前置；行为内容线结构固化（生理排查 → 红旗 → 成因 → 方案，红旗必须在前两块）；会员不含专题；上架不满足条件即拒绝并列出问题 | `app/services/topic_service.py`、`app/api/v1/topics_api.py`、`client/src/pages/topics` | 6 例（含双签拒绝、红旗首块、推荐排序、结构校验） |
| **RQ-04** LBS 转介 | 仅市/区级落库，经纬度只做即时计算不入库不进埋点；POI 未接入时降级城市级急诊指引（不编造机构）；默认关闭（D11/Q-52 未定稿） | `app/services/referral_service.py`、`POST /risk/referral` | 降级口径覆盖 |

### 缺陷修复

| 编号 | 修法 | 验证 |
|---|---|---|
| **N1** 商品名残留旧品牌 | 种子改「Babe宝伴会员月卡」；种子内对存量行做幂等替换 | `GET /billing/product` 返回值核验 |
| **N2** 后台风险事件字段错绑 + 详情无响应 | 列表改绑 `category_code` / `score_band` / `level`；行内「查看」改为调详情接口打开详情抽屉 | 后台构建 + 页面字段核对 |
| **N3** 渠道清单双数据源 | 收敛为 `crisis_channel` 单表；后台维护页改读写该表并补新建/编辑/核验/记录 | `tests/test_v31_channels.py::test_admin_list_channels_is_same_source` |
| **N4** 两菜单指向同一页 | 拆为 `/admin/rights` 与 `/admin/config`（同组件 `mode` 分派，旧路径仅重定向） | 路由与菜单核对 |
| **N5** 急症词条未入库 | 种子已含 15 个独立急症词，跨库幂等补齐 | 词库条数核验 |

---

## 三、测试执行证据（2026-10-20 实跑）

### 3.1 后端单元 + 集成（pytest）

```
408 passed, 4 skipped in 1717.69s (0:28:37)
```

- 其中 **V3.1 新增 89 例**：`test_v31_ai_label.py` 13 / `test_v31_triage.py` 28 /
  `test_v31_channels.py` 9 / `test_v31_reminders.py` 11 /
  `test_v31_compliance.py` 12 / `test_v31_content.py` 16；
- 4 例 skip 为环境门控（Milvus 不可达 / pgvector 扩展缺失，与本次改动无关）；
- 开发前基线 302 passed / 10 failed / 8 errors —— 失败与错误**全部**为本机沙箱限制
  （`%TEMP%` 由 `mkdtemp` 创建后不可写、6379 端口被非 Redis 服务占用），已按
  「测试基础设施适配」修正（`JIABAN_TEST_UPLOAD_DIR` 覆盖 + Redis `PING` 探测），
  非修改业务断言。

### 3.2 系统测试（真实 HTTP / SSE 端到端）

```
===== E2E API 测试：63/63 passed，异常拦截率 100%，耗时 24.2s =====
```

覆盖 C 端 30 例（登录幂等 / 分层同意 / 建档与派生列 / 乐观锁 / 单活跃会话 /
三面答 SSE 帧序 / 安全置顶 / 会员门控 / 额度计次 / 幂等回放 / 高危拦截 /
申诉 / 渠道卡 / 测评 16 题与报告 / 支付验签与幂等 / 历史 / 权利 / 反馈 / 举报）
+ 后台 17 例（MFA / 知识库审核 / 词库测试器与回滚 / 日志脱敏 / 风险复核与上报 /
开关 / 审计 / 越权对照）+ 异常 12 例（401/1101、伪造令牌、越权 1103/1603、
缺二次确认 1602、额度 1202、非法参数 1001、防枚举 1002、下线开关 1406、
申诉上限）.

**执行过程中发现并修复 2 个脚本级缺陷**（非产品缺陷）：
① `ENV03` 仍按 V3.0 的「11 tags」断言，V3.1 为 12 组 → 改为「≥12 tags 且 ≥150 端点」；
② `E06` 额度用例未先完成基础同意，被 D2 门禁（1301）挡住 → 补齐同意步骤。

### 3.3 并发压测（mock 模型通道）

```
并发: 4 workers × 3 req ｜ 总请求 12 ｜ 成功 12 ｜ 失败 0 ｜ 错误率 0.00%
整请求延迟(ms): P50=668  P95=817  均值=699  max=831
SSE 首包(ms):   P50=326  P95=369
吞吐: 3.4 req/s
```

> 说明：本机单进程 + mock 模型通道；真实模型与多副本下的时延不在本报告结论内。
> 分级判定为纯函数，实测 P95 < 10ms（`test_decide_is_millisecond_level`，
> 预算 300ms）。

### 3.4 前端

| 项 | 命令 | 结果 |
|---|---|---|
| C 端单元测试 | `client: npm test` | **100 pass / 0 fail** |
| C 端类型检查 | `client: npm run type-check` | **exit 0** |
| C 端 H5 构建 | `client: npm run build:h5` | **DONE Build complete（exit 0）** |
| C 端小程序构建 | `client: npm run build:mp-weixin` | **DONE**（条件编译生效：`share-card` 仅含 `downloadFile` 分支） |
| 后台构建 | `admin-web: npm run build` | **✓ built in 49.74s（exit 0）** |

> 构建环境说明：本机 `%TEMP%` 有残留 esbuild 进程锁，裸跑 `npm run build` 会因
> esbuild 清理临时文件失败；将 `TEMP` 指向工作区目录后通过。属环境问题，非代码问题。

### 3.5 静态门禁

| 门禁 | 结果 |
|---|---|
| 契约校验（前端调用 × OpenAPI） | **PASS**：文档完整性 153/153；提取调用 130 处（admin.ts 60 / index.ts 70）；**无漂移** |
| API 文档一致性（`docs/API.md` × OpenAPI） | **PASS**：153/153 端点零偏差 |
| 拟人化文案扫描（RQ-02 / E2E-21） | **PASS**：扫描 112 个文件、命中 0 条；5 条变体注入全部被捕获 |
| 渠道号码硬编码扫描（DR-26 / E2E-22） | **PASS**：扫描 176 个文件、无硬编码渠道号码（110/120/119/122/12345 按通用指引白名单放行） |

### 3.6 存量库升级验证

```
python scripts/migrate_v31.py
→ 新建表 11 张；ADD 列 11 个；业务表共 49 张
python scripts/seed_data.py
→ 分级规则 22 条 / 轻工具 3 个 / 专题包 3 套 / 渠道列补齐 / 来源等级补齐
```

> 迁移脚本幂等（`ADD COLUMN IF NOT EXISTS` 语义 + `create_all(checkfirst=True)`），
> 不删列、不改类型、不回填业务数据。
>
> 该脚本是本次新增的**必要交付物**：`init_db.py` 只会建缺失表，不会给既有表补列；
> 存量库不跑迁移会直接报 `column "input_mode" does not exist`（首次 E2E 即命中此问题）。

### 3.7 门禁脚本自身验证（一条命令复跑）

```
powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1 -PytestArgs "tests/test_v31_compliance.py -q"
[1] 契约校验        PASS（14.6s）
[2] 拟人化文案扫描  PASS（1.6s）
[3] 渠道号码扫描    PASS（1.9s）
[4] 后端测试        PASS（12 passed）
===== 门禁汇总 ===== 结论：PASS 全部通过
EXITCODE=0
```

> 过程中修复 1 个**工具链缺陷**：`scripts/ci_gate.ps1` 原为 UTF-8 无 BOM，Windows
> PowerShell 5.1 按 ANSI 解析导致中文串被截断、脚本直接语法报错（无法运行）。
> 已为其补 UTF-8 BOM（其余 `.ps1` 原本已带 BOM），现已可在 5.1 与 7.x 下正常运行。

---

## 四、发布门禁状态（V3.1 §7.2，`GET /api/v1/admin/gates/summary` 实时口径）

| 门禁项 | 门槛 | 当前状态 | 判定 |
|---|---|---|---|
| 安全类（正文为空率、E2E-01/02/03/14） | 全绿 | 高危拦截三路 + 不计次 + 不落库全过 | ✅ 通过 |
| **AI 标识三链路抽检（E2E-20）** | 合格率 100% | 页面契约 / 长图显式（≥15%、≥2 处）/ PNG `tEXt` 隐式（回读断言）**全部可程序化验证** | ✅ 通过 |
| **拟人化禁用词全量扫描（E2E-21）** | 零命中 | 112 文件 0 命中，变体注入捕获 | ✅ 通过 |
| **渠道清单核验（E2E-22）** | 三类各 ≥1 条经人工拨测且在有效期内 | 号码未回填（Q-48 未拍板）→ 系统按占位展示 | ❌ **未通过**（等业务事实） |
| **分级规则专家确认（E2E-19）** | 首批规则经专家书面确认 | 规则已条目化入库、后台可会签；`expert_signoff` 为空 | ❌ **未通过**（等专家会签） |

> 结论：**代码侧无阻塞项**；上述 2 项红灯的解除动作分别是「运营回填并拨测渠道号码」与
> 「育儿/宠物专家逐条会签」，均在后台页面一键完成，无需改代码或发版。

---

## 五、未完成 / 受限项（如实说明）

1. **渠道号码为空**（Q-48）：系统不编造号码，门禁如实红；解除方式：后台「危机渠道清单」回填 + 提交核验记录。
2. **分级规则未会签**（Q-49）：规则为研发按公开共识取的保守默认值；解除方式：后台「分级规则」逐条会签。
3. **订阅消息外发未启用**（D14）：`template_id` 为空 → 站内补达；不伪造外部发送成功。
4. **LBS 转介默认关闭**（D11 / Q-52）：接口存在但 `referral_enabled=false`，返回城市级指引；精确坐标不落库。
5. **家庭共享只建表不开放**（Q-53，PRD 明确要求）：`collaborator` 表含独立同意记录字段，无功能入口。
6. **专题包处于草稿**：样例内容已就绪但未取得专家双签，`status=draft`、C 端不可见（不伪造签署）。
7. **多模态解析未接入**：图片链路（送检 / 生命周期 / 删除日志）完整，但解析给出「未接入」提示，不假装识图。
8. **环境保真度**：本机 `LLM_MOCK=true` + mock embedding + Milvus 未启用；真实模型下的检索相关性、分级与信任链路表现**未验证**；微信开发者工具 / 真机 / 多浏览器**0 覆盖**。
9. **本机 8000 端口被其他项目占用**（`问到会 AskUntilMastered API`）：`export_api_doc.py` 已加归属校验（标题须含「宝伴」且存在 `/api/v1/health`），否则回退本地导入；联调前请确认监听端口。
10. **前端未经浏览器真实点击验收**：已到构建 + 类型检查 + 单元测试 + 契约门禁，但未做 Chrome 实机走查（评估报告中的 26 张截图口径未更新）。

---

## 六、复跑方式

```powershell
# 一条命令跑完：契约校验 → 文案扫描 → 号码扫描 → 全量 pytest →（可选）前端构建
powershell -ExecutionPolicy Bypass -File scripts\ci_gate.ps1 -WithBuild

# 仅后端全量测试
cd backend; .\.venv\Scripts\python.exe -m pytest tests -q

# 仅 V3.1 专项
cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_v31_*.py -q

# 端到端系统测试（需后端运行；本机 8000 被占用时改用其他端口）
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8012
cd backend; .\.venv\Scripts\python.exe scripts/e2e_api_test.py --base http://127.0.0.1:8012

# 并发压测
cd backend; .\.venv\Scripts\python.exe scripts/load_test.py --base http://127.0.0.1:8012 --workers 4 --requests 3

# 重新导出接口文档
cd backend; .\.venv\Scripts\python.exe scripts/export_api_doc.py

# 存量库升级
cd backend; .\.venv\Scripts\python.exe scripts/migrate_v31.py; .\.venv\Scripts\python.exe scripts/seed_data.py
```

---

**报告编制**：基于本次实际代码改动、全量测试输出、端到端脚本结果与静态门禁输出产出。
**报告日期**：2026-10-20

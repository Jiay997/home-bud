# .build — 家伴文档生成工作区

用脚本把片段（parts）**机器组装**成最终的 PRD / UI 原型描述文档，保证章节编号、附录、决策台账、阻塞项摘要不靠手写。

## 一、产出物与脚本

| 脚本 | 输入 | 输出 |
|---|---|---|
| `assemble2.py` | 21 个来源片段 + `gen-appendix.md` + `gen-blockers.md` | `../docs/02-基线/家伴-PRD_V1.2.md` |
| `assemble.py` | `ui-1.md` + 6 个 `frag-*.md` + `ui-2.md` | `../docs/02-基线/家伴-UI原型描述_V1.2.md` |
| `ledger.py` | 决策台账数据 | PRD 附录 A/B/C 与 §6.16（PRD 头部声明"禁止手写"） |
| `gen.py` → `gen-*.md` | 台账/映射数据 | 生成附录、变更映射（`gen-changes.md`）、FR 决策状态（`gen-fr-status.md`）、阻塞项（`gen-blockers.md`） |
| `render.py` / `wirelib.py` | 页面定义 | 线框片段 `frag-*.md` |
| `m_*.py` | 页面/场景定义 | 对应的 `frag-*.md` 片段 |
| `check.py` / `check12.py` | — | 一致性、编号自洽性检查（分别读归档版 PRD V1.1 与基线版 PRD V1.2） |
| `_*.py` | — | 构建过程中的一次性修补脚本（`_normalize` / `_renumber` / `_fixrefs` / `_terms` / `_final` / `_ui_*` 等） |

## 二、文件分类

- **PRD 主体**：`prd-1.md` ~ `prd-5.md`（分卷）
- **新增章节**：`add-*.md`（api / arch-block / assess / baseline / compliance / events / kb / loop / perm / protocol / refund / terms）
- **机器生成章节**：`gen-*.md`
- **定向补章**：`sec-*.md`（`sec-617` / `sec-71` / `sec-79`）
- **UI 首尾**：`ui-1.md`（规范 + 页面清单）、`ui-2.md`（状态 / 时序 / 文案 / 组件 / 交付）
- **UI 线框分片**：`frag-sc0106` / `frag-sc0712` / `frag-sc1319` / `frag-sc2026` / `frag-pa_a` / `frag-pa_b`
- **`_archive/`**：整理时移出的中间产物，见其 README

`assemble2.py` 会把所有片段按 `## x` / `### x.y` 标题切成键值块后**按键号数值排序**输出，因此插入新章节会自动落到正确位置，且会检测重复编号（`!! DUPLICATE key`）。

## 三、复现方式

```powershell
cd D:\HomeBud\.build
python assemble2.py     # 重建 PRD 基线
python assemble.py      # 重建 UI 原型描述基线
```

脚本以 `dirname(__file__)` 定位 `.build`，再取其父目录为项目根；输出路径已指向 `docs/02-基线/`。

> ⚠️ **重建会覆盖 `docs/02-基线/` 下的基线文档。** 基线正文在组装之后还经过多轮人工/脚本修补（见 `_*.py` 与 `_normalize.py` 中的正文替换），片段不保证与当前基线逐字节一致。重建前请先备份基线，或在临时目录验证 diff。

## 四、整理记录（2026-10-05）

- 6 个 `_tmp_*.md` 与 `__pycache__/` 移入 `_archive/`（未删除）
- `assemble.py` / `assemble2.py` / `check.py` / `check12.py` 的读写路径改指 `docs/` 新位置
- 本目录结构保持扁平，脚本的 `ROOT` 推导逻辑未改

## 五、文档链一致性核对器（`check_docs.py`）

```powershell
cd D:\HomeBud
python .build\check_docs.py            # 完整报告
python .build\check_docs.py --quiet    # 只打印 FAIL / WARN（适合 CI）
```

**退出码**：0 = 无 FAIL；1 = 存在 FAIL。

**检查七项**

| # | 检查 | 说明 |
|---|---|---|
| 1 | 文件名引用可解析 | 文中提到的 `家伴-*.md` 是否真实存在（抓悬空引用） |
| 2 | 不把旧版当现行 | 引用非最新版时，该行/该章节必须带归档、变更、修订等语境；否则报警 |
| 3 | 基线声明指向 | 「唯一需求基线 / 唯一界面基线 / 关联文档 / 配套」等声明行必须指向现行版 |
| 4 | 旧口径回归守卫 | 9 项「必须清零」的历史口径（旧延迟表值、D18 前高危清单、幽灵 `G1`、越权表述、题量区间旧值…） |
| 5 | 一级章号序列 | PRD 章号 0–24 是否连续无重复 |
| 6 | § 引用可解析 | PRD 内 `§N.M` 是否能对应到实际标题（指向 V1.0 需求文档的会列为 WARN） |
| 7 | 台账一致性 | 跑 `ledger.py` 取数，与 PRD §22 的三行数字比对 |

**为什么需要它**：V1.5 收口时，人工核对漏掉了 **22 处**不同步（版本引用停在 V1.3、UI 决策索引状态过时、D18 未同步、内容值旧、以及 PRD 自己的 §0.7.1 效力顺序表写成 `V1.3（本文档）`）。这些都是脚本发现的——**每次改版本号、重命名或改状态口径后请跑一次**。

**豁免规则**（避免把历史记录当漂移）：章节标题含「归档 / 变更 / 修订 / 修正 / 同步 / 交付 / 冻结 / 附录 D」的，整个章节豁免版本漂移判定；行内含「被取代 / 归档 / 错命名 / 变更登记 / 修正 T-」等关键词的单行同样豁免。

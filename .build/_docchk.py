import io
# .build/README.md 增补检查器章节
p=r"D:\HomeBud\.build\README.md"
t=io.open(p,encoding="utf-8").read()
SEC = """

## 五、文档链一致性核对器（`check_docs.py`）

```powershell
cd D:\\HomeBud
python .build\\check_docs.py            # 完整报告
python .build\\check_docs.py --quiet    # 只打印 FAIL / WARN（适合 CI）
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
"""
if "check_docs.py" not in t:
    t = t.rstrip("\n") + SEC
io.open(p,"w",encoding="utf-8",newline="\n").write(t)
print("OK .build/README.md 已增补")

# 主 README 增补
p2=r"D:\HomeBud\README.md"
t2=io.open(p2,encoding="utf-8").read()
SEC2 = """

### 8.4 一致性核对器（新增）

改完版本号 / 重命名 / 改状态口径后，**跑一次这个**：

```powershell
python .build\\check_docs.py
```

检查 7 项：文件名引用可解析 · 不把旧版当现行 · 基线声明指向 · 9 项旧口径回归守卫 · 一级章号序列 · § 引用可解析 · 台账与 §22 一致。

> V1.5 收口时人工核对漏了 **22 处**不同步，其中包括 **PRD §0.7.1 效力顺序表写成 `V1.3（本文档）`**——这些都是这个脚本查出来的。用法与豁免规则见 `.build/README.md` 第五节。
"""
if "check_docs.py" not in t2:
    t2 = t2.rstrip("\n") + SEC2
io.open(p2,"w",encoding="utf-8",newline="\n").write(t2)
print("OK README.md 已增补")

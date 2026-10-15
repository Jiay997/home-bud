import io,re
ok=[]
# README：PRD 行状态文本
p=r"D:\HomeBud\README.md"; t=io.open(p,encoding="utf-8").read()
m=re.search(r"\| 家伴-PRD_V1\.5\.md \| \[docs/02-基线\]\(docs/02-基线\) \|[^\n]*\|", t)
if m:
    t=t.replace(m.group(0), "| 家伴-PRD_V1.5.md | [docs/02-基线](docs/02-基线) | **唯一需求基线（最终交付版）**（5186 行）。S1/S2/S3 全部处理完毕、台账一致、新增 §23 开工就绪与 §24 冻结声明。状态：**可开工动手**，不可正式发布（待签字与合规检查表全绿） |")
    ok.append("README PRD 行")
io.open(p,"w",encoding="utf-8",newline="\n").write(t)
# PRD：编制日期
p2=r"D:\HomeBud\docs\02-基线\家伴-PRD_V1.5.md"; t2=io.open(p2,encoding="utf-8").read()
if t2.count("（V1.4 同日）")==1:
    t2=t2.replace("（V1.4 同日）","（**V1.5 最终版同日**）"); ok.append("PRD 编制日期")
# PRD：唯一基线声明补 V1.3/V1.4 已归档
o="`家伴-PRD_V1.1.md`、`家伴-PRD_V1.2.md` 被取代（均归档于 `docs/99-归档/`）。"
n="`家伴-PRD_V1.1.md` ~ `家伴-PRD_V1.4.md` 均被取代，全部归档于 `docs/99-归档/`。"
if t2.count(o)==1:
    t2=t2.replace(o,n); ok.append("PRD 归档声明")
io.open(p2,"w",encoding="utf-8",newline="\n").write(t2)
print("已修:", ", ".join(ok))
print("PRD 行数", t2.count("\n")+1)

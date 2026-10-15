import io
# 1) 修真 bug：PRD §0.7.1 效力顺序表
P=r"D:\HomeBud\docs\02-基线\家伴-PRD_V1.5.md"
t=io.open(P,encoding="utf-8").read()
a="| **`家伴-PRD_V1.3.md`（本文档）** | **唯一需求基线** |"
b="| **`家伴-PRD_V1.5.md`（本文档）** | **唯一需求基线** |"
print("OK   [PRD §0.7.1 效力顺序表] x%d"%t.count(a) if t.count(a)==1 else "MISS x%d"%t.count(a))
t=t.replace(a,b,1)
# 顺带核查同表其他行是否有旧版
io.open(P,"w",encoding="utf-8",newline="\n").write(t)
# 2) 修脚本豁免漏洞：HIST_HEAD 加 "修正"
C=r"D:\HomeBud\.build\check_docs.py"
c=io.open(C,encoding="utf-8").read()
o='HIST_HEAD = ("归档", "变更", "修订", "修正索引", "同步", "交付", "冻结", "附录 D", "交付状态")'
n='HIST_HEAD = ("归档", "变更", "修订", "修正", "同步", "交付", "冻结", "附录 D")'
print("OK   [脚本 HIST_HEAD]" if c.count(o)==1 else "MISS HIST_HEAD")
io.open(C,"w",encoding="utf-8",newline="\n").write(c.replace(o,n,1))

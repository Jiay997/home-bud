import io
P=r"D:\HomeBud\docs\02-基线\家伴-UI原型描述_V1.3.md"
t=io.open(P,encoding="utf-8").read()
n=t.count("犬伤处置门诊 / 疾控中心（V1.4）")
t=t.replace("犬伤处置门诊 / 疾控中心（V1.4）","犬伤处置门诊 / 疾控中心（V1.5）")
io.open(P,"w",encoding="utf-8",newline="\n").write(t)
print("UI 剩余 V1.4 标记已修 x%d"%n)
R=r"D:\HomeBud"
import glob,os
docs=[p for p in glob.glob(R+r"\docs\*\*.md")+glob.glob(R+r"\docs\*\*\*.md")+[R+r"\README.md"]
      if not any(k in p for k in ("99-归档","01-需求来源","05-审核","_原始检索"))]
print("\n=== 交叉引用矩阵（最终）===")
for p in sorted(set(docs)):
    t=io.open(p,encoding="utf-8").read()
    import re
    refs=sorted(set(re.findall(r"家伴-(?:PRD_V[\d.]+|UI原型描述_V[\d.]+|架构设计文档_V[\d.]+|数据模型文档_V[\d.]+)\.md",t)))
    print("  %-46s %s"%(os.path.basename(p), " , ".join(refs) if refs else "（无版本化引用）"))

import io,re
def ctx(p,ln):
    L=io.open(p,encoding="utf-8").read().split("\n")
    h=""
    for i,x in enumerate(L[:ln],1):
        if re.match(r"^#{2,4} ",x): h="L%d %s"%(i,x)
    print("  %s L%d  所属标题: %s"%(p.split("\\")[-1],ln,h))
    print("      行内容: %s"%L[ln-1].strip()[:110])
ctx(r"D:\HomeBud\README.md",86)
ctx(r"D:\HomeBud\docs\02-基线\家伴-PRD_V1.5.md",240)

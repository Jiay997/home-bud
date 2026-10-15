import io,re
D=r"D:\HomeBud"; p=D+r"\docs\02-基线\家伴-PRD_V1.4.md"
t=io.open(p,encoding="utf-8").read()
fr=io.open(D+r"\.build\gen-fr-status.md",encoding="utf-8").read().rstrip("\n")
pat=re.compile(r"### 6\.16 FR 决策状态与可开发边界.*?(?=\n### 6\.17 )",re.S)
assert len(pat.findall(t))==1
t=pat.sub(lambda m: fr+"\n\n", t, count=1)
io.open(p,"w",encoding="utf-8",newline="\n").write(t)
print("§6.16 已重新拼接")

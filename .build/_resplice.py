import io,re
D=r"D:\HomeBud"; p=D+r"\docs\02-基线\家伴-PRD_V1.4.md"
t=io.open(p,encoding="utf-8").read()
bl=io.open(D+r"\.build\gen-blockers.md",encoding="utf-8").read().rstrip("\n")
pat=re.compile(r"(## 22\. 当前阻塞项摘要（机器生成）\n\n).*?(?=\n---\n\n## 23\.)",re.S)
assert len(pat.findall(t))==1, len(pat.findall(t))
t=pat.sub(lambda m: m.group(1)+bl+"\n", t, count=1)
io.open(p,"w",encoding="utf-8",newline="\n").write(t)
print("§22 已重新拼接，行数",t.count("\n")+1)

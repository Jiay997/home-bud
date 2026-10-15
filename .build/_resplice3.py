import io,re
D=r"D:\HomeBud"; p=D+r"\docs\02-基线\家伴-PRD_V1.5.md"
t=io.open(p,encoding="utf-8").read()
fr=io.open(D+r"\.build\gen-fr-status.md",encoding="utf-8").read().rstrip("\n")
ap=io.open(D+r"\.build\gen-appendix.md",encoding="utf-8").read().rstrip("\n")
bl=io.open(D+r"\.build\gen-blockers.md",encoding="utf-8").read().rstrip("\n")
p1=re.compile(r"### 6\.16 FR 决策状态与可开发边界.*?(?=\n### 6\.17 )",re.S)
p2=re.compile(r"### 附录 A：假定基线登记册（AS）.*?(?=\n### 附录 D：修正索引)",re.S)
p3=re.compile(r"(## 22\. 当前阻塞项摘要（机器生成）\n\n).*?(?=\n---\n\n## 23\.)",re.S)
for pat,new,lab in ((p1,fr+"\n\n","6.16"),(p2,ap+"\n\n","附录A-C")):
    assert len(pat.findall(t))==1, (lab,len(pat.findall(t)))
    t=pat.sub(lambda m:new,t,count=1)
assert len(p3.findall(t))==1
t=p3.sub(lambda m:m.group(1)+bl+"\n",t,count=1)
io.open(p,"w",encoding="utf-8",newline="\n").write(t)
print("重生章节已拼接，行数",t.count("\n")+1)

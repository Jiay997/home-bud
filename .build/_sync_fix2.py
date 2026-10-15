import io,os
R=r"D:\HomeBud"
fixes=[
 (R+r"\docs\04-工程\家伴-架构设计文档_V1.1.md","**v1.1**（对应 PRD V1.4）","**v1.1**（对应 PRD V1.5）"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","V1.3（**与 PRD V1.4 配套**","V1.3（**与 PRD V1.5 配套**"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md",
  "| PA-07 | 抓咬伤是否入高危清单 | CG18 | 待专家确认 | 未决策，不得开发（清单条目） |",
  "| PA-07 | 抓咬伤已入高危清单 | CG18 | **已闭环（D18，PRD V1.5）** | 🟢 已决策，可开发：**归入硬类别**，命中即阻断不生成正文，渠道必须含犬伤处置门诊 / 疾控中心（PRD §8.2 / §8.2.1） |"),
]
for p,a,b in fixes:
    t=io.open(p,encoding="utf-8").read(); c=t.count(a)
    if c==1:
        io.open(p,"w",encoding="utf-8",newline="\n").write(t.replace(a,b)); print("OK   [%s] %s"%(os.path.basename(p),a[:36]))
    else:
        print("MISS [%s] x%d : %s"%(os.path.basename(p),c,a[:46]))

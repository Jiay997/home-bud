import io,os
R=r"D:\HomeBud"
F=[
 (R+r"\docs\04-工程\家伴-数据模型文档_V1.1.md","## 附：V1.1 同步说明（对应 PRD V1.4）","## 附：V1.1 同步说明（对应 PRD V1.5）"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","犬伤处置门诊 / 疾控中心（V1.4）","犬伤处置门诊 / 疾控中心（V1.5）"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","不得分支判断（幂等，V1.4）","不得分支判断（幂等，V1.5）"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","**已冻结（V1.4）：16 题","**已冻结（V1.5）：16 题"),
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","仅同步受 S1 修复影响的界面口径：首包阈值、`blocked` 幂等语义、测评题量、会员交付物）",
  "仅同步受 S1 修复影响的界面口径：首包阈值、`blocked` 幂等语义、测评题量、会员交付物、**抓咬伤犬伤渠道（D18）**、决策依赖索引状态）"),
]
for p,a,b in F:
    t=io.open(p,encoding="utf-8").read(); c=t.count(a)
    if c==1:
        io.open(p,"w",encoding="utf-8",newline="\n").write(t.replace(a,b)); print("OK   [%s] %s"%(os.path.basename(p),a[:40]))
    else:
        print("MISS [%s] x%d : %s"%(os.path.basename(p),c,a[:46]))

import io,os
R=r"D:\HomeBud"
fixes=[
 (R+r"\docs\02-基线\家伴-UI原型描述_V1.3.md","`家伴-PRD_V1.3.md`（唯一需求基线","`家伴-PRD_V1.5.md`（唯一需求基线"),
 (R+r"\docs\06-机构方向\机构工作台方向-收敛与验证方案_V0.1.md","`docs/02-基线/家伴-PRD_V1.3.md` **§1.7.2**","`docs/02-基线/家伴-PRD_V1.5.md` **§1.7.2**"),
 (R+r"\docs\06-机构方向\机构工作台方向-收敛与验证方案_V0.1.md","`docs/02-基线/家伴-PRD_V1.3.md`（唯一需求基线）","`docs/02-基线/家伴-PRD_V1.5.md`（唯一需求基线）"),
 (R+r"\docs\07-竞品调研\README.md","`docs/02-基线/家伴-PRD_V1.3.md` **§1.4 竞品分析**","`docs/02-基线/家伴-PRD_V1.5.md` **§1.4 竞品分析**"),
 (R+r"\docs\07-竞品调研\上市竞品调研_育儿与宠物.md","`docs/02-基线/家伴-PRD_V1.3.md` **§1.4.7","`docs/02-基线/家伴-PRD_V1.5.md` **§1.4.7"),
 (R+r"\docs\07-竞品调研\开源竞品调研_多智能体与安全护栏.md","`docs/02-基线/家伴-PRD_V1.3.md` §1.4","`docs/02-基线/家伴-PRD_V1.5.md` §1.4"),
 (R+r"\docs\03-设计\PRODUCT.md","气质测评（12–16 题 / 4 维度 / 三档 + 交叉判定）","气质测评（**16 题**（§12.2 冻结）/ 4 维度 / 三档 + 交叉判定）"),
]
for p,a,b in fixes:
    t=io.open(p,encoding="utf-8").read()
    c=t.count(a)
    if c==1:
        io.open(p,"w",encoding="utf-8",newline="\n").write(t.replace(a,b))
        print("OK   [%s] %s"%(os.path.basename(p),a[:38]))
    else:
        print("MISS [%s] x%d : %s"%(os.path.basename(p),c,a[:50]))

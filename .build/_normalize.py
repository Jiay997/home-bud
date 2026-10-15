# -*- coding: utf-8 -*-
"""规范化插入章节的标题层级，并改写文档头为 V1.2。"""
import io
import os
import re

B = os.path.dirname(os.path.abspath(__file__))


def fix(name, pairs):
    p = os.path.join(B, name)
    if not os.path.exists(p):
        print("skip(missing)", name)
        return
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        if a not in s:
            print("  WARN %s: not found %r" % (name, a))
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("normalized", name)


# 章内小节统一为 ###
fix("add-baseline.md", [("## 0.7 唯一基线声明", "### 0.7 唯一基线声明")])
fix("add-compliance.md", [
    ("## 11.9 ", "### 11.9 "), ("## 11.10 ", "### 11.10 "), ("## 11.11 ", "### 11.11 "),
])
fix("sec-617.md", [("## 6.17 ", "### 6.17 ")])
for f, num in (("gen-changes.md", "0.6"), ("gen-fr-status.md", "6.16")):
    p = os.path.join(B, f)
    s = io.open(p, encoding="utf-8").read()
    s = re.sub(r"^#{2,3}\s+" + re.escape(num), "### " + num, s, count=1, flags=re.M)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("normalized", f)

# 第 6 章：把 §6.16/6.17 追加到 prd-2 的 §6 块——由 assemble2 的排序自动完成，
# 但 prd-2 的 §6 块末尾与 §6.16 之间需要空行，assemble2 已用 \n\n 连接。

# 文档头改写为 V1.2
p = os.path.join(B, "prd-1.md")
s = io.open(p, encoding="utf-8").read()
old_head_start = s.index("> **文档版本**")
old_head_end = s.index("## 0. 文档信息与阅读指引")
new_head = """> **文档版本**：V1.2（唯一需求基线 · 决策闭环与跨文档一致性修订版）
> **文档状态**：待业务方签字冻结。**当前不具备正式开工条件**（见文末阻塞项摘要）
> **编制日期**：2026-10-03
> **唯一基线声明**：见 §0.7。本文档是研发、测试、设计、验收的**唯一需求基线**；`家伴-家庭养育多智能体助手_需求说明文档_V1.0.md` 降为**历史来源**，`家伴-PRD_V1.1.md` 被取代。
> **配套文档**：`家伴-UI原型描述_V1.2.md`（唯一界面基线）｜`DESIGN.md`（唯一视觉 token 真源）｜`家伴-设计系统样式瓦片.html`（可视证据）
> **变更映射**：见 §0.6（继承 / 修改 / 删除 / 新增 / 废弃编号）
> **决策台账**：附录 A/B/C 与 §6.16 由 `.build/ledger.py` 机器生成，禁止手写
> **产品形态**：微信小程序（C 端，优先）+ 后台管理 Web；Web 端用户侧列后续版本
> **产品定位**：家庭养育科普参考工具。覆盖分龄儿童养育 + 伴侣宠物科学饲养。**输出仅作养育参考，不替代医生、心理咨询师、学校教师、执业兽医。**

---

"""
s = s[:old_head_start] + new_head + s[old_head_end:]

# 修订记录追加 V1.2 行
s = s.replace(
    "| V1.1 | 2026-10-02 | 产品 | 本 PRD：采纳评审推荐决策为 AS 假定基线；修正 M1–M10 与 I1–I10；补齐 N1–N9；合规缺口 CG1–CG18 需求化；新增决策/待确认/修正三本登记册 |",
    "| V1.1 | 2026-10-02 | 产品 | 采纳评审推荐决策为 AS 假定基线；修正 M1–M10 与 I1–I10；补齐 N1–N9；合规缺口 CG1–CG18 需求化；新增决策/待确认/修正三本登记册 |\n"
    "| **V1.2** | **2026-10-03** | 产品 | **决策闭环与一致性修订**：① 冻结唯一基线并新增变更映射（§0.6/§0.7）；② 引入三态决策门槛，FR 逐条给出可开发边界（§6.16）；③ 重写风险拦截与申诉状态机（§7.9）；④ 新增问答响应协议 v1（§7.5）；⑤ 延迟预算改为四张表并冻结口径（§7.7）；⑥ 降级矩阵与 UI 对齐（§7.8）；⑦ 儿童信息合规闭环（§11.9）；⑧ 删除与留存优先级表（§11.10）；⑨ 模型供应商与版本清单（§11.11）；⑩ 知识库上线标准（§12.1）；⑪ 测评配置冻结（§12.2）；⑫ 会员与退款边界（§12.9）；⑬ 后台权限矩阵（§16）；⑭ 埋点事件字典（§17）；⑭ 接口清单（§18）；⑮ 评审意见闭环对照表（§19）；⑯ 架构分层重构，风险预警改为风险控制服务（§7.1）；⑰ 超范围拒答口径统一（§6.17） |",
)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("prd-1.md header -> V1.2")
print("has V1.2 revision row:", "| **V1.2** |" in s)
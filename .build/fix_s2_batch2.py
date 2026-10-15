# -*- coding: utf-8 -*-
"""S2 第二批：T-07 orphaned 枚举 / T-09 埋点字段登记 / T-12·T-13 订单与审核驳回状态 / T-05 Q-40·41 状态"""
import io

PRD = r"D:\HomeBud\docs\02-基线\家伴-PRD_V1.4.md"
log = []
t = io.open(PRD, encoding="utf-8").read()


def rep(old, new, exp, lab):
    global t
    n = t.count(old)
    if n != exp:
        log.append("  MISS [%s] 期望%d 实际%d" % (lab, exp, n))
        return
    t = t.replace(old, new)
    log.append("  OK   [%s] x%d" % (lab, n))


# ==================== T-07：orphaned 补进 status 枚举与状态机
rep('"status": "streaming | done | blocked | degraded | failed",',
    '"status": "streaming | done | blocked | degraded | failed | orphaned",', 1, "T-07 §7.4 契约枚举")
rep("| 返回 | §7.3 的 `status`（`streaming`／`done`／`blocked`／`degraded`／`failed`）、`render_order`、各节 `blocks`、`last_sequence` |",
    "| 返回 | §7.3 的 `status`（`streaming`／`done`／`blocked`／`degraded`／`failed`／**`orphaned`**）、`render_order`、各节 `blocks`、`last_sequence` |",
    1, "T-07 §18.5.6 枚举")
rep("| 已生成 | 用户追问 | 待提交 | 同一会话内二次提问计数 |",
    "| 已生成 | 用户追问 | 待提交 | 同一会话内二次提问计数 |\n"
    "| 推理中 / 渲染中 | **断线超过 5 分钟未重连** | **已孤立（`orphaned`）** | 由定时任务 A-050 扫描标记：**仍落库、可在 SC-19 回看**；**不计入失败率**、不影响额度（§7.5.4）。**V1.4 修正 T-07**：原枚举与状态机均无此状态，而错误码 1405 / C-022 / A-050 都在用它 |",
    1, "T-07 §8.6 状态机")

# ==================== T-09：字段登记进 schema
rep("`client_request_id`、`request_type`、`agent_count`、`agent_ids[]`、`is_conflict`、`is_degraded`、`first_packet_ms`、`is_member_content` | str、enum、int、enum[]、bool、bool、int、bool |",
    "`client_request_id`、`request_type`、`agent_count`、`agent_ids[]`、`is_conflict`、`is_degraded`、`first_packet_ms`、`is_member_content`、**`gray_triggered`** | str、enum、int、enum[]、bool、bool、int、bool、**bool** |",
    1, "T-09 qa_result_view 补 gray_triggered")
rep("| `app_launch` | 小程序冷启/热启 | `launch_scene`、`is_new_user`、`network` | enum、bool、enum | `U`+`session_id` | `B` | `N1`；`launch_scene` 只允许白名单枚举，**禁止上报 scene 原始串（含 query）** | `L6M` | FR-B4、NFR-5.1 | 新用户 7 日留存、入口点击率分母、分享带来新增 |",
    "| `app_launch` | 小程序冷启/热启 | `launch_scene`、`is_new_user`、`network`、**`share_trace_id`** | enum、bool、enum、**str** | `U`+`session_id` | `B` | `N1`；`launch_scene` 只允许白名单枚举，**禁止上报 scene 原始串（含 query）**；**`share_trace_id` 为随机短链 token，不含用户标识**（**V1.4 补登记，修正 T-09**） | `L6M` | FR-B4、NFR-5.1、§12.8 | 新用户 7 日留存、入口点击率分母、**分享带来新增（归因口径见 §12.8）** |",
    1, "T-09 app_launch 补 share_trace_id")
rep("| P95 响应时长 | 分位数，无分子分母；按单领域/复合/灰区分别统计 | `qa_result_view` | 请求 | **有**（字段级） | 补字段：`request_type`、`first_packet_ms`、`gray_triggered` |",
    "| P95 响应时长 | 分位数，无分子分母；按单领域/复合/灰区分别统计 | `qa_result_view` | 请求 | **有**（字段级） | **已补齐（V1.4，修正 T-09）**：`request_type`、`first_packet_ms`、`gray_triggered` 均已登记进 §17.3，灰区 P95 **可算** |",
    1, "T-09 缺口表回填")

# ==================== T-12 / T-13：订单驳回状态
rep("| 退款申请中 | 驳回 | 已支付 | 展示驳回理由 |",
    "| 退款申请中 | 驳回 | **已驳回** | 展示驳回理由；**不再回到\"已支付\"**（**V1.4 修正 T-12**：原写法目标状态写\"已支付\"，而 FR-J4 / C-055 / §12.9.1 都承诺存在\"已驳回\"状态，导致 UI 无法表达） |",
    1, "T-12 订单驳回状态")
rep("| 已支付 | 到期 | 已过期 | 深度内容转只读（AS-22） |",
    "| 已支付 | 到期 | 已过期 | 深度内容转只读（AS-22） |\n"
    "| **已驳回** | **用户补充材料后重新申请** | 退款申请中 | **合法重审路径**（**V1.4 修正 T-13**）；同一订单最多重申 2 次，第 3 次起只显示客服入口 |\n"
    "| **已驳回** | 用户放弃 / 7 天内未重申 | 已支付 | 权益保持有效（等同未退款）；驳回记录与理由留痕 ≥3 年 |",
    1, "T-13 订单驳回出边")

# ==================== T-13：§8.9 标题与出边
rep("### 8.9 知识库上架与申诉工单状态机（新增，支撑 D5）",
    "### 8.9 知识库上架与审核工单状态机（新增，支撑 D5）\n\n> **V1.4 修正 T-13**：原标题含\"申诉工单\"，但本表内并无申诉状态——**用户侧误报申诉在 §7.9.1**（blocked→appeal_submitted→pending_review→…），本节只管知识库条目的上架与审核工单。",
    1, "T-13 §8.9 标题")
rep("| 待审核 | 专家驳回 | 已驳回 | 记录驳回理由；条目不可上架 |",
    "| 待审核 | 专家驳回 | 已驳回 | 记录驳回理由；条目不可上架 |\n"
    "| **已驳回** | **运营 / 专家重新编辑并重申** | 待审核 | **合法重审路径**（**V1.4 修正 T-13**：原表\"已驳回\"无出边，条目被驳回后永久无法再上架）；每次重审写审核记录，重申次数不限 |\n"
    "| **已驳回** | 放弃 | 草稿（归档） | 保留驳回理由供复盘与专家工时统计 |",
    1, "T-13 §8.9 出边")

# ==================== T-05：Q-40 / Q-41 状态口径
rep("| Q-40 | 条目数量目标 | 最低门槛合计 **662 条/题**、目标值合计 **1074 条/题**",
    "| Q-40 | 条目数量目标（**Q-40 已于附录 C 关闭**） | 最低门槛合计 **662 条/题**、目标值合计 **1074 条/题**",
    1, "T-05 Q-40 表头")
rep("| Q-41 | 抽检评分标准与合格线 | 一票否决项 5 条 + 六维度 100 分制；单条 ≥80（高危 ≥90）+ 无一票否决；批次通过率 ≥98%；每月 30 条 + 高危 100% + 每周 200 条 |",
    "| Q-41 | 抽检评分标准与合格线（**Q-41 已于附录 C 关闭**） | 一票否决项 5 条 + 六维度 100 分制；单条 ≥80（高危 ≥90）+ 无一票否决；批次通过率 ≥98%；每月 30 条 + 高危 100% + 每周 200 条 |",
    1, "T-05 Q-41 表头")

# ==================== §0.6.2 登记
rep("| 17 | **S2 批次修复（V1.4 追加）**",
    "| 18 | **S2 第二批修复（V1.4 追加）**：T-07 `orphaned` 状态未定义（错误码 1405 / C-022 / A-050 都在用，但 status 枚举与状态机均无）；T-09 `gray_triggered`、`app_launch.share_trace_id` 未登记进 schema（灰区 P95 与分享归因算不出）；T-12/T-13 订单与审核工单的「已驳回」无目标状态、无出边；T-05 Q-40/Q-41 状态口径与附录 C 不一致 | §7.4、§8.6、§8.8、§8.9、§17.3、§17.9.2、§12.2 | 修改 |\n"
    "| 17 | **S2 批次修复（V1.4 追加）**",
    1, "§0.6.2 追加第 18 行")

io.open(PRD, "w", encoding="utf-8", newline="\n").write(t)
print("\n".join(log))
print("行数 %d" % (t.count("\n") + 1))

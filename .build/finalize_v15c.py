# -*- coding: utf-8 -*-
"""V1.5 最后三处：T-14 接口插入、合稿提示章号、US-xx 残留。"""
import io, re

P = r"D:\HomeBud\docs\02-基线\家伴-PRD_V1.5.md"
t = io.open(P, encoding="utf-8").read()
log = []

# 1) T-14：找 A-050 行并插入 A-051/A-052
m = re.search(r"^\| API-A-050 \|.*$", t, re.M)
if m:
    row = m.group(0)
    add = ("\n| **API-A-051** | `POST /api/v1/admin/accounts/{admin_id}/devices/clear` | **超管清除某账号的「已记住设备」** | FR-K8、NFR-7.4 | PA-01 | 后台 | `client_request_id` | 否 | **V1.5 新增（修正 T-14）**：§16.9 要求该能力（PA-01 ③），原接口清单无对应条目；必填原因 + 写审计 |"
           "\n| **API-A-052** | `POST /api/v1/admin/accounts/{admin_id}/unlock` | **超管解锁被锁定的后台账号** | FR-K8、NFR-7.4 | PA-01 | 后台 | `client_request_id` | 否 | **V1.5 新增（修正 T-14）**：对应 §16.9 锁定策略与 PA-01 ④；必填原因 + 写审计 |")
    t = t.replace(row, row + add, 1)
    log.append("OK   [T-14 A-051/A-052]")
else:
    log.append("MISS [T-14] 未找到 API-A-050 行")

# 2) 合稿提示章号
old = "> **合稿提示**：V1.1 中 `## 17` 为「追溯矩阵」。合稿时本章插入为 §17，原「追溯矩阵」顺延为 §18，§17.1 的「需求 → 页面 → 埋点 → 验收」表保持不动。"
if t.count(old) == 1:
    t = t.replace(old, "> **合稿提示（章号已按当前版本更正，V1.5）**：本章为 §17「埋点事件字典」；追溯矩阵现为 **§21**（不是 §17，也不是 §18）。§21.1 的「需求 → 页面 → 埋点 → 验收」表内容未变。", 1)
    log.append("OK   [合稿提示章号 §17→§21]")
else:
    log.append("MISS [合稿提示] 锚点未命中（残留 %d）" % t.count("§17 追溯矩阵"))

# 3) US-xx 残留
n = len(re.findall(r"US-[A-O]\d*", t))
t2 = re.sub(r"US-([A-O])(\d*)", r"FR-\1\2", t)
if t2 != t:
    t = t2
    log.append("OK   [US-xx → FR-xx 全文] x%d" % n)
else:
    log.append("SKIP [US-xx] 无残留")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
log.append("行数 %d" % (t.count("\n") + 1))
print("\n".join(log))

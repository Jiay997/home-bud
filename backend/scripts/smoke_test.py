# -*- coding: utf-8 -*-
"""端到端冒烟测试脚本：验证Babe宝伴核心业务链路真实可用。

覆盖链路：登录 → 同意 → 建档 → 高危拦截 → 正常问答(SSE) → 测评 →
支付开通会员 → 会员内容解锁 → 额度查询 → 后台登录。

用法：python scripts/smoke_test.py  （需后端已运行在 localhost:8000）
"""
import json
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://localhost:8000/api/v1"
PASSED: list = []
FAILED: list = []


def step(name: str, ok: bool, detail: str = "") -> None:
    """记录并打印一个冒烟步骤结果。

    Args:
        name: 步骤名。
        ok: 是否通过。
        detail: 附加信息。
    """
    mark = "PASS" if ok else "FAIL"
    (PASSED if ok else FAILED).append(name)
    print(f"[{mark}] {name}" + (f" | {detail}" if detail else ""))


def main() -> None:
    """执行全部冒烟步骤。

    Raises:
        SystemExit: 存在失败步骤时以退出码 1 结束。
    """
    client = httpx.Client(timeout=60)
    client.request_id = str(uuid.uuid4())

    # 1. 健康检查
    r = client.get(f"{BASE}/health").json()
    step("健康检查", r["code"] == 0 and r["data"]["db_connected"], f"whitelist={r['data']['model_whitelist']}")

    # 2. 开发登录
    r = client.post(f"{BASE}/auth/dev-login", json={"device_id": f"smoke-{uuid.uuid4().hex[:8]}"}).json()
    step("C端登录", r["code"] == 0 and r["data"]["access_token"], r["data"]["user_uid"])
    token = r["data"]["access_token"]
    user_uid = r["data"]["user_uid"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. 文案下发
    r = client.get(f"{BASE}/texts", params={"ids": "DISCLAIMER_V1,AI_GEN_LABEL_V1"}).json()
    step("文案下发", r["code"] == 0 and "DISCLAIMER_V1" in r["data"]["texts"])

    # 4. 基础同意
    r = client.post(f"{BASE}/consent/agree", json={"consent_type": "base", "consent_version": "V1"}, headers=headers).json()
    step("基础同意", r["code"] == 0)

    # 5. 未单独同意建档 → 1302
    r = client.post(f"{BASE}/profiles/children", json={"nickname": "测试宝", "birth_date": "2025-04-08"}, headers=headers).json()
    step("未单独同意建档被拒(1302)", r["code"] == 1302, f"message={r['message']}")

    # 6. 单独同意后建档成功 + 派生列
    client.post(f"{BASE}/consent/agree", json={"consent_type": "child_personal_info", "guardian_name": "测试家长"}, headers=headers)
    r = client.post(f"{BASE}/profiles/children", json={"nickname": "测试宝", "birth_date": "2025-04-08", "gender": "female"}, headers=headers).json()
    step("建档成功", r["code"] == 0, r.get("data", {}).get("profile_uid", ""))
    child = r.get("data", {})
    step("派生列 age_months=18/1-3y", child.get("age_months") == 18 and child.get("age_band") == "1-3y",
         f"age_months={child.get('age_months')}, band={child.get('age_band')}")

    # 7. 宠物档案
    r = client.post(f"{BASE}/profiles/pets", json={"pet_type": "cat", "breed": "英短", "age_band": "adult"}, headers=headers).json()
    step("宠物建档", r["code"] == 0)

    # 8. 高危输入拦截（SSE blocked 帧，正文为空）
    r = client.post(f"{BASE}/qa/sessions", headers=headers,
                    json={"entry": "child", "question": "孩子被打到出血怎么办", "client_request_id": str(uuid.uuid4())}).json()
    blocked_ok = r["code"] == 0
    blocked_uid = r.get("data", {}).get("session_uid", "")
    if blocked_uid:
        with client.stream("POST", f"{BASE}/qa/sessions/{blocked_uid}/stream", headers=headers) as resp:
            events = []
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
        body_empty = all(e != "section_delta" for e in events)
        step("高危拦截 blocked", "blocked" in events and "section_delta" not in events,
             f"events={events}, 正文空={body_empty}")
        # 申诉
        r = client.post(f"{BASE}/risk/appeals", headers=headers,
                        json={"session_uid": blocked_uid, "appeal_note": "误会，我是问处理伤口的方法"}).json()
        # 注意：补充说明若命中硬类别则不予受理（animal_bite 涉咬伤；"处理伤口"不在硬词库）
        step("申诉提交", r["code"] == 0, f"appeal_no={r.get('data', {}).get('appeal_no')}, status={r.get('data', {}).get('status')}")
    else:
        step("高危拦截 blocked", False, str(r))

    # 9. 正常问答（SSE 渐进；llm_mock=false 走 DeepSeek 真实调用，失败则降级帧）
    client.post(f"{BASE}/profiles/current", json={"profile_type": "child", "profile_uid": child.get("profile_uid")}, headers=headers)
    successful_rid = str(uuid.uuid4())
    r = client.post(f"{BASE}/qa/sessions", headers=headers,
                    json={"entry": "child", "question": "1岁宝宝夜里总醒怎么办", "client_request_id": successful_rid}).json()
    if r["code"] == 0:
        uid = r["data"]["session_uid"]
        events, sections = [], {}
        with client.stream("POST", f"{BASE}/qa/sessions/{uid}/stream", headers=headers) as resp:
            ev, buf = None, ""
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    ev = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and ev:
                    try:
                        payload = json.loads(line.split(":", 1)[1].strip())
                    except Exception:
                        payload = {}
                    events.append(ev)
                    if ev == "section_done":
                        sections[payload.get("section_key")] = payload
                    ev, buf = None, ""
        has_completed = "completed" in events
        has_safety = "safety" in sections
        step("正常问答 SSE", has_completed, f"events={list(dict.fromkeys(events))[:6]}")
        step("安全分节置顶", has_safety, f"sections={list(sections.keys())}")
        # 会员门控：免费用户 block 块无 content
        gated_ok = all("content" not in b for s in sections.values()
                       for b in (s.get("blocks") or []) if b.get("access_tier") == "block")
        step("会员门控裁剪", gated_ok, f"sections={list(sections.keys())}")
        # 幂等回放：同一 client_request_id 再次提交（首次流已完成→幂等键已置 done）
        r3 = client.post(f"{BASE}/qa/sessions", headers=headers,
                         json={"entry": "child", "question": "1岁宝宝夜里总醒怎么办",
                               "client_request_id": successful_rid}).json()
        r3_data = r3.get("data") or {}
        step("幂等回放", r3["code"] == 0 and r3_data.get("idempotent_replay") is True,
             f"replay={r3_data.get('idempotent_replay')}")
    else:
        step("正常问答 SSE", False, str(r))

    # 10. 额度查询
    r = client.get(f"{BASE}/billing/quota", headers=headers).json()
    step("额度查询", r["code"] == 0, f"used={r['data'].get('used')}/{r['data'].get('limit')}")

    # 11. 测评：start → 全部答 4 → submit
    r = client.get(f"{BASE}/assessment/questions", params={"age_band": "1-3y"}, headers=headers).json()
    step("测评题库16题", r["code"] == 0 and len(r["data"]["questions"]) == 16, f"n={len(r.get('data', {}).get('questions', []))}")
    r = client.post(f"{BASE}/assessment/start", json={}, headers=headers).json()
    a_uid = r.get("data", {}).get("assessment_uid", "")
    if a_uid:
        q_resp = client.get(f"{BASE}/assessment/questions", params={"age_band": "1-3y"}, headers=headers).json()
        for q in (q_resp.get("data") or {}).get("questions", []):
            client.put(f"{BASE}/assessment/{a_uid}/answer", json={"q_no": q["q_no"], "raw_score": 4}, headers=headers)
        r = client.post(f"{BASE}/assessment/{a_uid}/submit", json={"client_request_id": str(uuid.uuid4())}, headers=headers).json()
        step("测评提交计分", r["code"] == 0 and r.get("data", {}).get("type_code") in ("easy", "active", "sensitive", "slow_warm"),
             f"type={r.get('data', {}).get('type_code')}")
        report_uid = r.get("data") or {}
        report_uid = report_uid.get("report_uid", "")
        if report_uid:
            r = client.get(f"{BASE}/history/report/{report_uid}", headers=headers).json()
            rdata = r.get("data") or {}
            content = rdata.get("content") or {}
            blocks = content.get("blocks", rdata.get("blocks", [])) if isinstance(content, dict) else []
            if isinstance(blocks, dict):
                member_blocks = [b for b in blocks.values() if isinstance(b, dict) and b.get("access_tier") == "block"]
            else:
                member_blocks = [b for b in (blocks or []) if isinstance(b, dict) and b.get("access_tier") == "block"]
            step("报告会员区块裁剪", all("content" not in b for b in member_blocks), f"member_blocks={len(member_blocks)}")
    else:
        step("测评提交计分", False, str(r))

    # 12. 下单 + 模拟支付（含验签与幂等）
    import hashlib
    r = client.get(f"{BASE}/billing/product", params={"platform": "web"}, headers=headers).json()
    pdata = r.get("data") or {}
    products = pdata.get("products") or []
    step("商品查询", r["code"] == 0 and bool(products), f"price_micro={products[0]['price_micro'] if products else 'N/A'}")
    r = client.post(f"{BASE}/billing/orders", headers=headers,
                    json={"product_code": "member_monthly", "platform": "web", "contract_confirm": True,
                          "client_request_id": str(uuid.uuid4())}).json()
    order_ok = r["code"] == 0
    order_no = r.get("data", {}).get("order_no", "")
    step("下单幂等", order_ok, f"order_no={order_no}")
    if order_no:
        tx = f"TX{uuid.uuid4().hex[:12]}"
        sign = hashlib.sha256((tx + "jiaban-pay-mock-sign-key").encode()).hexdigest()
        r = client.post(f"{BASE}/billing/orders/{order_no}/mock-pay", json={"transaction_id": tx, "sign": sign}, headers=headers).json()
        first_pay = r["code"] == 0
        r = client.post(f"{BASE}/billing/orders/{order_no}/mock-pay", json={"transaction_id": tx, "sign": sign}, headers=headers).json()
        step("支付验签+幂等", first_pay and r["code"] == 0, f"repeat={r.get('data', {}).get('idempotent') or r.get('data', {}).get('already_paid') or 'ok'}")
        r = client.get(f"{BASE}/billing/subscription", headers=headers).json()
        step("会员生效", r.get("data", {}).get("member_status") == "member", f"status={r.get('data', {}).get('member_status')}")

    # 13. 权利请求
    r = client.post(f"{BASE}/rights/requests", json={"request_type": "export"}, headers=headers).json()
    step("权利请求受理", r["code"] == 0, f"request_no={r.get('data', {}).get('request_no')}")

    # 14. 反馈 + 举报
    r = client.post(f"{BASE}/feedback", json={"content": "希望增加辅食专题"}, headers=headers).json()
    step("反馈提交", r["code"] == 0, f"feedback_no={r.get('data', {}).get('feedback_no')}")
    r = client.post(f"{BASE}/reports", json={"object_type": "answer", "object_id": "sess_x",
                                             "category": "medical_misleading", "description": "测试举报"}, headers=headers).json()
    step("举报提交", r["code"] == 0, f"report_no={r.get('data', {}).get('report_no')}")

    # 15. 后台登录（MFA 模拟码）
    r = client.post(f"{BASE}/admin/login", json={"username": "admin", "password": "Admin@123456"}).json()
    ticket = r.get("data", {}).get("mfa_ticket", "")
    r = client.post(f"{BASE}/admin/mfa/verify", json={"mfa_ticket": ticket, "code": "123456"}).json()
    admin_token = r.get("data", {}).get("token", "")
    step("后台登录+MFA", r["code"] == 0 and admin_token, f"role={r.get('data', {}).get('role')}")
    if admin_token:
        ah = {"Authorization": f"Bearer {admin_token}"}
        r = client.get(f"{BASE}/admin/kb/entries", headers=ah).json()
        step("后台知识库列表", r["code"] == 0, f"total={r.get('data', {}).get('total', len(r.get('data', {}).get('entries', [])))}")
        r = client.get(f"{BASE}/admin/agent-logs", headers=ah).json()
        step("Agent 日志", r["code"] == 0, f"items={len(r.get('data', {}).get('logs', r.get('data', {}).get('items', [])))}")
        r = client.get(f"{BASE}/admin/risk-events", headers=ah).json()
        step("高风险事件列表", r["code"] == 0)
        # 客服越权写配置 → 1602/1103
        r = client.post(f"{BASE}/admin/login", json={"username": "support", "password": "Admin@123456"}).json()
        t2 = client.post(f"{BASE}/admin/mfa/verify", json={"mfa_ticket": r.get("data", {}).get("mfa_ticket", ""), "code": "123456"}).json()
        if t2.get("data", {}).get("token"):
            r = client.put(f"{BASE}/admin/configs/switch.entry.child", json={"snapshot": {"enabled": False}, "reason": "越权测试"},
                           headers={"Authorization": f"Bearer {t2['data']['token']}"})
            step("客服越权写开关被拒", r.status_code == 403, f"http={r.status_code}")

    # 汇总
    print(f"\n===== 冒烟结果：{len(PASSED)} passed, {len(FAILED)} failed =====")
    if FAILED:
        print("失败项：", FAILED)
        sys.exit(1)


if __name__ == "__main__":
    main()

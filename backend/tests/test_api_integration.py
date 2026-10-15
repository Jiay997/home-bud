# -*- coding: utf-8 -*-
"""API 集成测试（spec Task 6.1）。

基于独立测试库 jiaban_test + TestClient(app) 端到端验证业务端点契约：
- dev-login 幂等（同 device_id 同 user_uid）；
- 儿童档案：未单独同意建档 1302、派生列（age_months/age_band）、
  乐观锁冲突 1003/409；
- 问答 SSE：高危词 blocked 帧序（无任何 section 帧）、mock 正常帧序
  （started→section_delta/section_done→completed）、同幂等键回放
  idempotent_replay=true；
- 风险申诉：同会话上限 2 次，第 3 次 1001；
- 气质测评全链路：16 题 → 全 4 分提交 → type=active → 免费用户
  4 个会员区块无 content；
- 商业化：下单 + mock-pay 幂等 + member 生效；
- 后台权限矩阵三连：客服写开关 1103/403、专家跨域 1603、
  缺二次确认 1602。
"""
import json
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import mock_pay_sign, parse_sse  # noqa: E402

API = "/api/v1"

# 高危问题（包含种子词库词条「打孩子打到出血」→ child_abuse 硬类别阻断）
RISK_QUESTION = "打孩子打到出血了怎么办"
# 正常问题（mock 网关语义分 0.1 → 放行）
SAFE_QUESTION = "两岁孩子晚上睡觉不踏实总翻来覆去怎么办"


# ---------------------------------------------------------------------------
# 认证：dev-login
# ---------------------------------------------------------------------------
class TestDevLogin:
    """dev-login 幂等与响应结构。"""

    def test_dev_login_idempotent_same_user(self, client):
        """同 device_id 多次登录恒定映射同一 user_uid（幂等登录）。"""
        r1 = client.post(f"{API}/auth/dev-login", json={"device_id": "it-dev-01"})
        r2 = client.post(f"{API}/auth/dev-login", json={"device_id": "it-dev-01"})
        assert r1.status_code == 200 and r2.status_code == 200
        b1, b2 = r1.json(), r2.json()
        assert b1["code"] == 0 and b2["code"] == 0
        assert b1["data"]["user_uid"] == b2["data"]["user_uid"]
        # 响应携带令牌对与会员状态
        assert b1["data"]["access_token"]
        assert b1["data"]["member_status"] == "free"

    def test_dev_login_different_device_new_user(self, client):
        """不同 device_id 映射不同用户。"""
        r1 = client.post(f"{API}/auth/dev-login", json={"device_id": "it-dev-a"})
        r2 = client.post(f"{API}/auth/dev-login", json={"device_id": "it-dev-b"})
        assert r1.json()["data"]["user_uid"] != r2.json()["data"]["user_uid"]


# ---------------------------------------------------------------------------
# 儿童档案：同意门控 / 派生列 / 乐观锁
# ---------------------------------------------------------------------------
def _agree_all(client, headers):
    """签署 base + child_personal_info 两层同意。

    Args:
        client: TestClient。
        headers: 鉴权头。

    Returns:
        None。

    Raises:
        AssertionError: 同意接口失败。
    """
    for ctype in ("base", "child_personal_info"):
        resp = client.post(
            f"{API}/consent/agree", json={"consent_type": ctype}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["code"] == 0


def _create_child(client, headers, nickname="小伴", birth_date="2025-04-08"):
    """创建儿童档案并返回 data。

    Args:
        client: TestClient。
        headers: 鉴权头。
        nickname: 昵称。
        birth_date: 出生日期。

    Returns:
        响应 data 字典（含 profile_uid/version/age_months/age_band）。

    Raises:
        AssertionError: 创建失败。
    """
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": nickname, "birth_date": birth_date},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


class TestChildProfile:
    """儿童档案同意门控、派生列与乐观锁。"""

    def test_create_child_without_child_consent_1302(self, client, user_token):
        """仅同意 base 未单独同意儿童信息 → 建档 1302。"""
        headers, _ = user_token()
        resp = client.post(
            f"{API}/consent/agree", json={"consent_type": "base"}, headers=headers
        )
        assert resp.json()["code"] == 0
        resp = client.post(
            f"{API}/profiles/children",
            json={"nickname": "小伴", "birth_date": "2025-04-08"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1302

    def test_create_child_derived_columns(self, client, user_token):
        """建档返回派生列：age_months 服务端计算、age_band 落 1-3y 档。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        data = _create_child(client, headers, birth_date="2025-04-08")

        # 月龄与本地按东八区重算一致（任务口径：2026-10-08 恰为 18 个月）
        today = date.today()
        months = (today.year - 2025) * 12 + (today.month - 4)
        if today.day < 8:
            months -= 1
        months = max(0, months)
        assert data["age_months"] == months
        assert data["age_months"] == 18
        assert data["age_band"] == "1-3y"
        assert data["profile_uid"]
        assert data["version"] == 1

    def test_update_child_optimistic_lock_conflict_1003(self, client, user_token):
        """PUT 携带过期 version → 1003 / http 409；正确 version 更新后 version+1。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        data = _create_child(client, headers)
        uid = data["profile_uid"]

        # 过期版本：冲突 1003
        resp = client.put(
            f"{API}/profiles/children/{uid}",
            json={"version": 999, "nickname": "改名了"},
            headers=headers,
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == 1003

        # 正确版本：成功且 version 递增
        resp = client.put(
            f"{API}/profiles/children/{uid}",
            json={"version": 1, "nickname": "改名了"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        updated = resp.json()["data"]
        assert updated["nickname"] == "改名了"
        assert updated["version"] == 2

    def test_base_consent_agree_idempotent(self, client, user_token):
        """重复同意同版本 base 协议幂等返回（不重复落库）。"""
        headers, _ = user_token()
        r1 = client.post(
            f"{API}/consent/agree", json={"consent_type": "base"}, headers=headers
        ).json()
        r2 = client.post(
            f"{API}/consent/agree", json={"consent_type": "base"}, headers=headers
        ).json()
        assert r1["code"] == 0 and r2["code"] == 0
        assert r1["data"]["idempotent"] is False
        assert r2["data"]["idempotent"] is True


# ---------------------------------------------------------------------------
# 问答 SSE：blocked 帧序 / 正常帧序 / 幂等回放
# ---------------------------------------------------------------------------
def _create_qa_session(client, headers, question, client_request_id, entry="child"):
    """创建问答会话。

    Args:
        client: TestClient。
        headers: 鉴权头。
        question: 问题原文。
        client_request_id: 幂等键。
        entry: 入口（child/pet/family）。

    Returns:
        (http resp, data 字典)。

    Raises:
        AssertionError: 响应非 200 或 code 非 0。
    """
    resp = client.post(
        f"{API}/qa/sessions",
        json={
            "entry": entry,
            "question": question,
            "client_request_id": client_request_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return resp, body["data"]


def _run_stream(client, headers, session_uid):
    """执行 SSE 流式问答并返回解析后的帧序列。

    Args:
        client: TestClient。
        headers: 鉴权头。
        session_uid: 会话 UID。

    Returns:
        [(event, data), ...] 帧列表。

    Raises:
        AssertionError: 流响应非 200。
    """
    resp = client.post(
        f"{API}/qa/sessions/{session_uid}/stream", headers=headers
    )
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


class TestQaStream:
    """问答 SSE 流式帧序（高危拦截与 mock 正常流）。"""

    def test_blocked_frame_sequence_no_section_frames(self, client, user_token):
        """高危词命中：started → blocked，正文为空，无任何 section/completed 帧。"""
        headers, _ = user_token()
        _, data = _create_qa_session(
            client, headers, RISK_QUESTION, "it-qa-block-1"
        )
        frames = _run_stream(client, headers, data["session_uid"])

        events = [e for e, _ in frames]
        # 帧序：首帧 started，第二帧 blocked，其后无 section/completed
        assert events[0] == "started"
        assert "blocked" in events
        blocked_idx = events.index("blocked")
        assert blocked_idx == 1, events
        assert "section_delta" not in events
        assert "section_done" not in events
        assert "completed" not in events
        # blocked 帧携带风险事件号、危机渠道与申诉标识（硬类别不可申诉）
        blocked = frames[blocked_idx][1]
        assert blocked["risk_event_no"]
        assert isinstance(blocked["channels"], list)
        assert blocked["appeal_allowed"] is False

    def test_mock_normal_frame_sequence(self, client, user_token):
        """mock 模式正常问题：started → section_delta* → section_done* → completed。"""
        headers, _ = user_token()
        _, data = _create_qa_session(
            client, headers, SAFE_QUESTION, "it-qa-ok-1"
        )
        frames = _run_stream(client, headers, data["session_uid"])

        events = [e for e, _ in frames]
        assert events[0] == "started"
        assert "section_delta" in events
        assert "section_done" in events
        assert events[-1] == "completed"
        # sequence 单调递增
        seqs = [d["sequence"] for _, d in frames if d is not None]
        assert seqs == sorted(seqs)
        # completed 帧携带额度信息
        completed = frames[-1][1]
        assert completed["status"] in ("done", "degraded")
        assert completed["quota"]["used"] == 1
        assert "disclaimer_id" in completed

    def test_idempotent_replay_after_completed(self, client, user_token):
        """同 client_request_id 已完成的会话再提交 → idempotent_replay=true。"""
        headers, _ = user_token()
        _, data = _create_qa_session(
            client, headers, SAFE_QUESTION, "it-qa-idem-1"
        )
        _run_stream(client, headers, data["session_uid"])

        # 同幂等键再次创建会话：回放首次结果
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "client_request_id": "it-qa-idem-1",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["idempotent_replay"] is True
        assert body["data"]["session_uid"] == data["session_uid"]

    def test_active_stream_conflict_409(self, client, user_token):
        """活跃流未结束时再开会话 → 409/1203（模拟活跃键占用）。"""
        headers, user_uid = user_token()
        # 直接操纵进程内 cache 模拟存在未结束的活跃流（键名 qa:active:{user_id}）
        from app.core.cache import cache

        user_id = sys.modules["conftest"].db_query_user_id(user_uid)
        cache.set(
            f"qa:active:{user_id}",
            json.dumps({"session_uid": "ghost", "cancel_token": "t"}),
            ttl_seconds=60,
        )
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "client_request_id": "it-qa-active-1",
            },
            headers=headers,
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == 1203


# ---------------------------------------------------------------------------
# 风险申诉：上限 2 次
# ---------------------------------------------------------------------------
class TestRiskAppeal:
    """误报申诉次数上限。"""

    def test_appeal_limit_third_rejected_1001(self, client, user_token):
        """同会话第 3 次申诉 → 1001（上限 2 次）。"""
        headers, _ = user_token()
        _, data = _create_qa_session(
            client, headers, RISK_QUESTION, "it-qa-appeal-1"
        )
        session_uid = data["session_uid"]
        # 执行流式问答触发风险拦截（落 RiskEvent 后才可申诉）
        frames = _run_stream(client, headers, session_uid)
        assert "blocked" in [e for e, _ in frames]
        notes = ["误判一：仅描述绘本情节", "误判二：描述动画剧情无实际行为"]
        for idx, note in enumerate(notes):
            resp = client.post(
                f"{API}/risk/appeals",
                json={"session_uid": session_uid, "appeal_note": note},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0, body
            assert body["data"]["appeal_no"]

        # 第 3 次：上限拒绝
        resp = client.post(
            f"{API}/risk/appeals",
            json={"session_uid": session_uid, "appeal_note": "第三次申诉"},
            headers=headers,
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 1001


# ---------------------------------------------------------------------------
# 气质测评：全链路 + 免费用户会员区块裁剪
# ---------------------------------------------------------------------------
class TestAssessmentFlow:
    """测评下发/作答/提交/报告门控全链路。"""

    def test_questions_16_items(self, client, user_token):
        """题库下发 16 题（4 维 × 4 题，含李克特 5 档选项）。"""
        headers, _ = user_token()
        resp = client.get(
            f"{API}/assessment/questions", params={"age_band": "1-3y"}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["questions"]) == 16
        qnos = sorted(q["q_no"] for q in data["questions"])
        assert qnos == list(range(1, 17))
        for q in data["questions"]:
            assert len(q["options"]) == 5

    def test_full_flow_active_type_and_free_gating(self, client, user_token):
        """16 题全 4 分 → type_code=active；免费用户 4 个会员区块无 content。"""
        headers, _ = user_token()
        # 开始测评
        resp = client.post(f"{API}/assessment/start", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        assessment_uid = resp.json()["data"]["assessment_uid"]

        # 全部 16 题作答 4 分
        for q_no in range(1, 17):
            resp = client.put(
                f"{API}/assessment/{assessment_uid}/answer",
                json={"q_no": q_no, "raw_score": 4},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["answered_count"] == q_no

        # 幂等提交
        resp = client.post(
            f"{API}/assessment/{assessment_uid}/submit",
            json={"client_request_id": "it-assess-1"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        assert body["data"]["type_code"] == "active"
        assert body["data"]["idempotent_replay"] is False
        report_uid = body["data"]["report_uid"]
        assert report_uid

        # 免费用户报告：13 区块，4 个会员区块无 content
        resp = client.get(
            f"{API}/history/report/{report_uid}", headers=headers
        )
        assert resp.status_code == 200, resp.text
        report = resp.json()["data"]
        assert report["is_member"] is False
        assert report["readonly"] is True
        assert len(report["blocks"]) == 13
        member_blocks = [b for b in report["blocks"] if b["access_tier"] == "block"]
        assert len(member_blocks) == 4
        for blk in member_blocks:
            assert "content" not in blk
            assert blk["summary"] == "开通会员查看完整方案"
        free_blocks = [b for b in report["blocks"] if b["access_tier"] == "free"]
        assert len(free_blocks) == 9
        for blk in free_blocks:
            assert "content" in blk

    def test_submit_idempotent_replay(self, client, user_token):
        """同 client_request_id 重复提交测评 → 回放首次结果。"""
        headers, _ = user_token()
        resp = client.post(f"{API}/assessment/start", json={}, headers=headers)
        assessment_uid = resp.json()["data"]["assessment_uid"]
        for q_no in range(1, 17):
            client.put(
                f"{API}/assessment/{assessment_uid}/answer",
                json={"q_no": q_no, "raw_score": 4},
                headers=headers,
            )
        payload = {"client_request_id": "it-assess-idem-1"}
        first = client.post(
            f"{API}/assessment/{assessment_uid}/submit", json=payload, headers=headers
        ).json()
        second = client.post(
            f"{API}/assessment/{assessment_uid}/submit", json=payload, headers=headers
        ).json()
        assert first["code"] == 0 and second["code"] == 0
        assert second["data"]["idempotent_replay"] is True
        assert second["data"]["report_uid"] == first["data"]["report_uid"]


# ---------------------------------------------------------------------------
# 商业化：下单 + mock-pay 幂等 + 会员生效
# ---------------------------------------------------------------------------
class TestBillingFlow:
    """下单、模拟支付回调幂等与会员状态。"""

    def test_order_mock_pay_and_member_active(self, client, user_token):
        """下单 → mock-pay → 订单 paid；重复回调幂等；订阅查询 member。"""
        headers, _ = user_token()
        # 下单
        resp = client.post(
            f"{API}/billing/orders",
            json={
                "product_code": "member_monthly",
                "platform": "web",
                "contract_confirm": True,
                "client_request_id": "it-order-1",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        assert body["data"]["idempotent_replay"] is False
        order_no = body["data"]["order_no"]
        assert order_no

        # 重复下单同幂等键：回放
        resp2 = client.post(
            f"{API}/billing/orders",
            json={
                "product_code": "member_monthly",
                "platform": "web",
                "contract_confirm": True,
                "client_request_id": "it-order-1",
            },
            headers=headers,
        )
        assert resp2.json()["data"]["idempotent_replay"] is True
        assert resp2.json()["data"]["order_no"] == order_no

        # mock-pay：验签 + 发放
        tx = "it-txn-001"
        sign = mock_pay_sign(tx)
        resp = client.post(
            f"{API}/billing/orders/{order_no}/mock-pay",
            json={"transaction_id": tx, "sign": sign},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        pay = resp.json()
        assert pay["code"] == 0, pay
        assert pay["data"]["status"] == "paid"
        assert pay["data"]["already_processed"] is False

        # 重复回调：幂等，不重复发放
        resp = client.post(
            f"{API}/billing/orders/{order_no}/mock-pay",
            json={"transaction_id": tx, "sign": sign},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["already_processed"] is True

        # 订阅查询：member 生效
        resp = client.get(f"{API}/billing/subscription", headers=headers)
        assert resp.status_code == 200, resp.text
        sub = resp.json()["data"]
        assert sub["member_status"] == "member"
        assert sub["subscription"] is not None
        assert sub["subscription"]["status"] == "active"

    def test_mock_pay_bad_sign_1504(self, client, user_token):
        """验签失败 → 1504，订单状态不变。"""
        headers, _ = user_token()
        order_no = client.post(
            f"{API}/billing/orders",
            json={
                "product_code": "member_monthly",
                "platform": "web",
                "contract_confirm": True,
                "client_request_id": "it-order-badsign",
            },
            headers=headers,
        ).json()["data"]["order_no"]
        resp = client.post(
            f"{API}/billing/orders/{order_no}/mock-pay",
            json={"transaction_id": "it-txn-bad", "sign": "0" * 64},
            headers=headers,
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 1504


# ---------------------------------------------------------------------------
# 后台权限矩阵三连
# ---------------------------------------------------------------------------
class TestAdminPermissionMatrix:
    """后台最小权限矩阵：1103 / 1603 / 1602。"""

    def test_support_cannot_write_switch_1103(self, client, admin_token):
        """客服写系统开关 → 1103 http 403（cfg:write 仅超管）。"""
        headers = admin_token("support")
        resp = client.put(
            f"{API}/admin/configs/switch.entry.child",
            json={"snapshot": {"enabled": False}, "reason": "误操作测试"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1103

    def test_expert_child_cannot_edit_pet_entry_1603(self, client, admin_token):
        """育儿专家改宠物条目 → 1603 跨领域越权。"""
        headers = admin_token("expert_child")
        resp = client.put(
            f"{API}/admin/kb/entries/kb_pet_cat_feed_01",
            json={"version": 1, "content": "越权修改正文"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1603

    def test_operator_unpublish_without_confirm_1602(self, client, admin_token):
        """运营缺 confirm_token 下架条目 → 1602，不产生副作用。"""
        headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/kb/entries/kb_child_sleep_01/unpublish",
            json={"reason": "内容过期需下架"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1602

    def test_admin_login_mfa_flow(self, client, admin_token):
        """超管两步登录成功，me 接口返回角色与菜单。"""
        headers = admin_token("admin")
        resp = client.get(f"{API}/admin/me", headers=headers)
        assert resp.status_code == 200, resp.text
        me = resp.json()["data"]
        assert me["role"] == "super_admin"
        assert isinstance(me["menus"], list)

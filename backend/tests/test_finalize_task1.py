# -*- coding: utf-8 -*-
"""规格 finalize-modules-to-100 Task 1 缺陷回归用例集（SIM 台账遗留缺陷清零）。

覆盖缺陷（mock 模式，不依赖真实 LLM）：

- SIM-18 宠物问答管线收敛：entry=pet 仅 pet_agent + safety_agent 参与
  （agents_involved ⊆ {pet, safety}，无「育儿建议」分节）；entry=family
  仍三 Agent；entry=child 保持 child + safety（意图实体 mock 下不追加 pet）；
- SIM-21 测评断点续填：start 幂等续填返回 resumed=true 且携带已答明细
  answers（q_no→raw_score/skipped），供前端还原选中态与定位首个未答题；
- SIM-20 报告长图水印数据源：build_image_meta 协议 V1 合规字段 + 长图接口
  仅免费区块（水印渲染在前端，数据源断言在此）；
- SIM-23 报告详情结构：报告 payload 的区块 content 为结构化对象
  （type_name 等键值，而非字符串 JSON）；qa 详情下发 is_member_content
  内容档位字段（与历史列表口径一致）；
- SIM-22 会员到期日回显：订阅接口下发 member_expire_at 与
  subscription.expire_at 实际到期日（前端取值路径修复的契约锚点）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import parse_sse  # noqa: E402

API = "/api/v1"

# 与既有回归用例同口径：正常问题（避开高危词与缓存命中——mock 下加唯一后缀）
SAFE_CHILD_Q = "两岁孩子晚上睡觉不踏实总翻来覆去怎么办"
SAFE_PET_Q = "猫频繁呕吐没精神是怎么回事"
SAFE_FAMILY_Q = "孩子和猫一起生活要注意什么"


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _create_qa_session(client, headers, question, client_request_id, entry):
    """创建问答会话并校验包络。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
        question: 问题原文。
        client_request_id: 幂等键（用例内唯一）。
        entry: 入口（child/pet/family）。

    Returns:
        包络 data 字典（含 session_uid）。

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
    return body["data"]


def _run_stream(client, headers, session_uid):
    """执行 SSE 流式问答并解析帧序列。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
        session_uid: 会话对外标识。

    Returns:
        [(event, data_dict or None), ...] 帧列表。

    Raises:
        AssertionError: 流响应非 200。
    """
    resp = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


def _finish_assessment(client, headers, raw_score=4):
    """完成一次完整测评（16 题作答 → 提交计分）。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
        raw_score: 统一作答分值（1-5）。

    Returns:
        (assessment_uid, report_uid) 二元组。

    Raises:
        AssertionError: 任一步响应异常。
    """
    resp = client.post(f"{API}/assessment/start", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    uid = data["assessment_uid"]
    for q_no in range(1, 17):
        resp = client.put(
            f"{API}/assessment/{uid}/answer",
            json={"q_no": q_no, "raw_score": raw_score},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    resp = client.post(
        f"{API}/assessment/{uid}/submit",
        json={"client_request_id": f"fin-task1-{uid[:8]}"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return uid, body["data"]["report_uid"]


# ---------------------------------------------------------------------------
# SIM-18：pet 入口仅 pet_agent + safety_agent，不再被 family 三 Agent 管线应答
# ---------------------------------------------------------------------------
class TestSim18PetPipeline:
    """入口分流 fan-out：pet→pet+safety；child→child+safety；family→三 Agent。"""

    def test_pet_entry_no_child_section(self, client, user_token):
        """entry=pet 消费至 completed：agents_involved ⊆ {pet, safety}，无育儿分节。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: agents_involved 混入 child 或存在育儿分节。
        """
        headers, _ = user_token()
        data = _create_qa_session(
            client, headers, SAFE_PET_Q, "fin18-pet-1", entry="pet"
        )
        frames = _run_stream(client, headers, data["session_uid"])
        events = [e for e, _ in frames]
        assert events[0] == "started", events
        assert "completed" in events, events
        completed = next(d for e, d in frames if e == "completed")
        involved = set(completed.get("agents_involved") or [])
        # 修复前（mock 意图 has_child_entity 恒 True）：agents_involved=['child','pet','safety']
        assert involved <= {"pet", "safety"}, involved
        assert involved, "pet 入口应至少有 pet/safety 参与"
        # 分节不含育儿分节；安全分节置顶语义不变
        section_keys = {d.get("section_key") for e, d in frames if e == "section_done" and d}
        assert "child" not in section_keys, section_keys
        assert "safety" in section_keys, section_keys

    def test_family_entry_keeps_three_agents(self, client, user_token):
        """entry=family 现状保持：三 Agent 全参与。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 三 Agent 未全参与。
        """
        headers, _ = user_token()
        data = _create_qa_session(
            client, headers, SAFE_FAMILY_Q, "fin18-family-1", entry="family"
        )
        frames = _run_stream(client, headers, data["session_uid"])
        completed = next(d for e, d in frames if e == "completed")
        involved = set(completed.get("agents_involved") or [])
        assert {"child", "pet", "safety"} <= involved, involved

    def test_child_entry_keeps_child_and_safety(self, client, user_token):
        """entry=child 现状保持：child + safety 参与（mock 意图无宠物实体不追加 pet）。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: child/safety 未参与。
        """
        headers, _ = user_token()
        data = _create_qa_session(
            client, headers, SAFE_CHILD_Q, "fin18-child-1", entry="child"
        )
        frames = _run_stream(client, headers, data["session_uid"])
        completed = next(d for e, d in frames if e == "completed")
        involved = set(completed.get("agents_involved") or [])
        assert {"child", "safety"} <= involved, involved
        # 安全分节仍置顶（pinned 语义不变）
        safety_done = next(
            (d for e, d in frames if e == "section_done" and d and d.get("section_key") == "safety"),
            None,
        )
        assert safety_done is not None
        assert safety_done.get("pinned") is True


# ---------------------------------------------------------------------------
# SIM-21：测评断点续填——draft 视图携带已答映射（前端还原选中态与定位）
# ---------------------------------------------------------------------------
class TestSim21DraftResume:
    """断点续填：start 幂等续填返回 resumed=true + answers 已答明细。"""

    def test_resume_returns_answers_mapping(self, client, user_token):
        """作答 2 题（含 1 跳题）后 start：resumed=true，answers 按 q_no 可还原。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 断点视图缺 answers 映射或计数不符。
        """
        headers, _ = user_token()
        resp = client.post(f"{API}/assessment/start", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        uid = resp.json()["data"]["assessment_uid"]

        # q1 作答 4 分、q2 跳题（raw_score=null）
        for q_no, score in ((1, 4), (2, None)):
            resp = client.put(
                f"{API}/assessment/{uid}/answer",
                json={"q_no": q_no, "raw_score": score},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text

        # 再次 start（引导页「继续作答」入口）：幂等续填并携带已答映射
        resp = client.post(f"{API}/assessment/start", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        draft = resp.json()["data"]
        assert draft["resumed"] is True, draft
        assert draft["assessment_uid"] == uid
        answers = {a["q_no"]: a for a in (draft.get("answers") or [])}
        assert answers[1]["raw_score"] == 4
        assert answers[2]["raw_score"] is None
        assert answers[2]["skipped"] is True
        assert draft["answered_count"] == 1
        assert draft["skipped_count"] == 1


# ---------------------------------------------------------------------------
# SIM-20：长图渲染数据源（水印在前端按会员态渲染，此处锁定协议字段）
# ---------------------------------------------------------------------------
class TestSim20ImageMeta:
    """build_image_meta 协议 V1 与长图接口免费区块口径。"""

    def test_build_image_meta_protocol(self):
        """纯函数：免责面积占比 ≥15%、出现次数 ≥2、协议版本 V1。

        Returns:
            None。

        Raises:
            AssertionError: 合规字段缺失或不达标。
        """
        from app.jobs.scheduler import build_image_meta

        meta = build_image_meta("fin20-report-uid")
        assert meta["protocol_version"] == "V1"
        assert meta["disclaimer_ratio"] >= 0.15
        assert meta["disclaimer_count"] >= 2
        assert meta["qr_placeholder"].endswith("/fin20-report-uid")

    def test_report_image_free_sections_only(self, client, user_token):
        """长图接口仅免费区块（会员内容不外泄），水印数据源不含会员态字段
        （前端按 user store 会员态渲染，符合任务口径）。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 长图混入会员区块或响应结构缺失。
        """
        headers, _ = user_token()
        _, report_uid = _finish_assessment(client, headers)
        resp = client.get(f"{API}/history/report/{report_uid}/image", headers=headers)
        assert resp.status_code == 200, resp.text
        payload = resp.json()["data"]
        keys = {s["key"] for s in payload["sections"]}
        member_keys = {"member_plan_detail", "member_communication", "member_scores", "member_history"}
        assert keys.isdisjoint(member_keys), keys
        assert payload["disclaimer_ratio"] >= 0.15
        assert payload["disclaimer_count"] >= 2


# ---------------------------------------------------------------------------
# SIM-23：报告详情区块结构化（content 为对象，杜绝前端原始 JSON 直显）+
#         qa 详情下发内容档位 is_member_content（与列表页口径一致）
# ---------------------------------------------------------------------------
class TestSim23ReportDetailStructure:
    """报告 payload 结构与 qa 详情内容档位字段。"""

    def test_report_blocks_content_structured(self, client, user_token):
        """报告详情：report_header.content 为结构化对象且含 type_name 键。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: content 为字符串（原始 JSON 形态）或缺 type_name。
        """
        headers, _ = user_token()
        _, report_uid = _finish_assessment(client, headers)
        resp = client.get(f"{API}/history/report/{report_uid}", headers=headers)
        assert resp.status_code == 200, resp.text
        payload = resp.json()["data"]
        header_blk = next(b for b in payload["blocks"] if b["key"] == "report_header")
        content = header_blk["content"]
        # 服务端保证结构化对象（前端按对象渲染，页面不出现 "{ " 开头原文）
        assert isinstance(content, dict), type(content)
        assert "type_name" in content
        assert isinstance(content["type_name"], str) and content["type_name"]

    def test_qa_detail_has_member_content_flag(self, client, user_token):
        """qa 详情下发 is_member_content（SIM-23 新增），与历史列表条目同口径。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 详情响应缺 is_member_content 布尔字段。
        """
        headers, _ = user_token()
        data = _create_qa_session(
            client, headers, SAFE_CHILD_Q, "fin23-qa-1", entry="child"
        )
        frames = _run_stream(client, headers, data["session_uid"])
        assert "completed" in [e for e, _ in frames]
        resp = client.get(f"{API}/history/qa/{data['session_uid']}", headers=headers)
        assert resp.status_code == 200, resp.text
        detail = resp.json()["data"]
        assert isinstance(detail.get("is_member_content"), bool)


# ---------------------------------------------------------------------------
# SIM-22：会员履约到期日回显——订阅接口下发实际到期日
# ---------------------------------------------------------------------------
class TestSim22SubscriptionExpireAt:
    """订阅响应携带 member_expire_at 与 subscription.expire_at。"""

    def test_subscription_returns_expire_at_after_pay(self, client, user_token):
        """下单 + mock-pay 后：member_expire_at 与 subscription.expire_at 非空。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 实际到期日字段缺失或为 None。
        """
        from conftest import mock_pay_sign

        headers, _ = user_token()
        resp = client.post(
            f"{API}/billing/orders",
            json={
                "product_code": "member_monthly",
                "platform": "web",
                "contract_confirm": True,
                "client_request_id": "fin22-order-1",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        order_no = resp.json()["data"]["order_no"]

        tx = "fin22-txn-001"
        resp = client.post(
            f"{API}/billing/orders/{order_no}/mock-pay",
            json={"transaction_id": tx, "sign": mock_pay_sign(tx)},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["code"] == 0, resp.text

        resp = client.get(f"{API}/billing/subscription", headers=headers)
        assert resp.status_code == 200, resp.text
        sub = resp.json()["data"]
        assert sub["member_status"] == "member"
        # SIM-22 锚点：前端「当前生效账户」截止日期回显的两个数据源均非空
        assert sub.get("member_expire_at"), sub
        assert sub["subscription"] is not None
        assert sub["subscription"].get("expire_at"), sub["subscription"]

    def test_free_user_subscription_structure(self, client, user_token):
        """无会员态：member_expire_at 为 None 但字段存在（前端占位文案现状保持）。

        Args:
            client: TestClient 夹具。
            user_token: 用户登录夹具。

        Returns:
            None。

        Raises:
            AssertionError: 响应缺 member_expire_at 键。
        """
        headers, _ = user_token()
        resp = client.get(f"{API}/billing/subscription", headers=headers)
        assert resp.status_code == 200, resp.text
        sub = resp.json()["data"]
        assert sub["member_status"] == "free"
        assert "member_expire_at" in sub
        assert sub["member_expire_at"] is None

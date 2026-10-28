# -*- coding: utf-8 -*-
"""浏览器回归三问题修复回归测试。

覆盖（对应本轮浏览器实测回归发现的 3 个缺陷）：
- 问题 1（mock 语义拦截）：浏览器实测句「孩子哭闹不停，捂住口鼻能不能
  让他安静下来」在 mock 模式完整会话流中应被二级语义拦截（blocked +
  risk_event_no）；表外普通问题放行（completed）；
- 问题 2（测评 422）：测评 start 接口兼容 profile_uid（UUID 字符串）与
  旧口径 profile_id 整型；uid 不存在按 1002/404；不传档案仍成功；完整
  start→作答→提交→报告链路档案关联不丢；
- 问题 3（Agent 日志 mock 字段）：mock 问答流后 agent_call_log 耗时/token
  落库非空，且后台日志列表/详情端点响应携带这些值；intent_route 行
  output_json 含意图字段（供后台「意图」展示）。

测试仅依赖 conftest 既有夹具（llm_mock autouse 强制 mock 模式），
真实 LLM 模式路径零改动不受影响。
"""
import json

import pytest

from app.llm.mock_semantic_corpus import match_mock_semantic
from app.models.base import gen_uuid

API = "/api/v1"

# 浏览器实测句（回归缺陷原句：含语料短语「捂住口鼻」的口语化变体）
BROWSER_QUESTION = "孩子哭闹不停，捂住口鼻能不能让他安静下来"
# 表外普通问题（不撞语料短语/一级词库/兜底正则，mock 下应正常走完）
OUTSIDE_QUESTION = "一岁宝宝夏天睡觉空调温度开多少比较合适"


# ---------------------------------------------------------------------------
# 问题 1：mock 语义拦截（完整会话流）
# ---------------------------------------------------------------------------
class TestBrowserQuestionSemanticBlock:
    """浏览器实测句的端到端语义拦截回归。"""

    def test_corpus_phrase_matches_browser_question(self):
        """语料触发短语对浏览器实测句命中（单元级前置确认）。"""
        hit = match_mock_semantic(BROWSER_QUESTION)
        assert hit is not None
        assert hit["category"] == "child_abuse"
        assert float(hit["score"]) > 0.8

    def test_browser_question_blocked_with_event_no(self, client, user_token):
        """完整会话流：实测句 blocked 帧携带 risk_event_no，无任何正文帧。"""
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": BROWSER_QUESTION,
                "client_request_id": f"br-risk-{gen_uuid()[:8]}",
            },
            headers=user_token_headers(client, "br-risk-user"),
        )
        assert resp.status_code == 200, resp.text
        session_uid = resp.json()["data"]["session_uid"]

        from tests.conftest import parse_sse

        stream = client.post(
            f"{API}/qa/sessions/{session_uid}/stream",
            headers=user_token_headers(client, "br-risk-user"),
        )
        assert stream.status_code == 200, stream.text
        frames = parse_sse(stream.text)
        events = [e for e, _ in frames]
        assert events[0] == "started"
        assert "blocked" in events
        # 阻断即返：无正文/完成帧
        assert "section_delta" not in events
        assert "completed" not in events
        blocked = frames[events.index("blocked")][1]
        assert blocked["risk_event_no"], blocked
        assert isinstance(blocked["channels"], list)

    def test_outside_question_completes(self, client, user_token):
        """表外普通问题：完整会话流正常 completed（放行口径回归）。"""
        headers = user_token_headers(client, "br-ok-user")
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": OUTSIDE_QUESTION,
                "client_request_id": f"br-ok-{gen_uuid()[:8]}",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        session_uid = resp.json()["data"]["session_uid"]

        from tests.conftest import parse_sse

        stream = client.post(
            f"{API}/qa/sessions/{session_uid}/stream", headers=headers
        )
        assert stream.status_code == 200, stream.text
        events = [e for e, _ in parse_sse(stream.text)]
        assert events[0] == "started"
        assert "section_done" in events
        assert events[-1] == "completed"
        assert "blocked" not in events


# ---------------------------------------------------------------------------
# 问题 2：测评 start 档案标识兼容（uid / 字符串 profile_id / 整型）
# ---------------------------------------------------------------------------
def user_token_headers(client, device_id: str, agree: bool = True) -> dict:
    """dev-login 登录并返回鉴权头（默认顺带签署基础同意）。

    Args:
        client: TestClient。
        device_id: 设备唯一标识。
        agree: 是否签署基础同意（问答入口 1301 门禁所需）。

    Returns:
        鉴权 headers dict。

    Raises:
        AssertionError: 登录/同意失败。
    """
    resp = client.post(f"{API}/auth/dev-login", json={"device_id": device_id})
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if agree:
        consent = client.post(
            f"{API}/consent/agree", json={"consent_type": "base"}, headers=headers
        )
        assert consent.status_code == 200, consent.text
        assert consent.json()["code"] == 0, consent.text
    return headers


def _create_child_profile(client, headers) -> dict:
    """完成儿童信息同意并创建儿童档案。

    Args:
        client: TestClient。
        headers: 鉴权头。

    Returns:
        档案 data 字典（含 profile_uid）。

    Raises:
        AssertionError: 同意/建档失败。
    """
    for ctype in ("base", "child_personal_info"):
        resp = client.post(
            f"{API}/consent/agree", json={"consent_type": ctype}, headers=headers
        )
        assert resp.status_code == 200, resp.text
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": "回归宝", "birth_date": "2025-04-08"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


class TestAssessmentStartProfileCompat:
    """测评 start 接口档案标识解析（uid 优先 / 整型兼容 / 越权 1002）。"""

    def _start(self, client, headers, payload) -> dict:
        """调用 start 接口并断言包络。

        Args:
            client: TestClient。
            headers: 鉴权头。
            payload: 请求体。

        Returns:
            响应 data 字典。

        Raises:
            AssertionError: 响应非 200 或 code 非 0。
        """
        resp = client.post(f"{API}/assessment/start", json=payload, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        return body["data"]

    def test_start_with_profile_uid(self, client, user_token):
        """profile_uid（UUID 字符串）启动成功且档案主键正确落库。"""
        from app.db import get_session_factory
        from app.models import Assessment, ChildProfile

        headers = user_token_headers(client, "br-uid-user")
        profile = _create_child_profile(client, headers)
        data = self._start(client, headers, {"profile_uid": profile["profile_uid"]})

        db = get_session_factory()()
        try:
            row = (
                db.query(Assessment)
                .filter(Assessment.assessment_uid == data["assessment_uid"])
                .first()
            )
            child = (
                db.query(ChildProfile)
                .filter(ChildProfile.profile_uid == profile["profile_uid"])
                .first()
            )
            assert row is not None and child is not None
            assert row.profile_id == child.id
        finally:
            db.close()

    def test_start_with_legacy_profile_id_uuid_string(self, client, user_token):
        """前端现状口径：profile_id 传 UUID 字符串可正常解析（422 修复）。"""
        headers = user_token_headers(client, "br-uuidstr-user")
        profile = _create_child_profile(client, headers)
        data = self._start(client, headers, {"profile_id": profile["profile_uid"]})
        assert data["profile_id"], data

    def test_start_with_legacy_int_profile_id(self, client, user_token):
        """向后兼容：profile_id 传整型主键仍可用。"""
        from app.db import get_session_factory
        from app.models import ChildProfile

        headers = user_token_headers(client, "br-int-user")
        profile = _create_child_profile(client, headers)
        db = get_session_factory()()
        try:
            child = (
                db.query(ChildProfile)
                .filter(ChildProfile.profile_uid == profile["profile_uid"])
                .first()
            )
            child_id = child.id
        finally:
            db.close()
        data = self._start(client, headers, {"profile_id": child_id})
        assert data["profile_id"] == child_id

    def test_start_with_unknown_uid_1002_404(self, client, user_token):
        """uid 不存在：HTTP 404 + code 1002（按既有资源不存在口径）。"""
        headers = user_token_headers(client, "br-baduid-user")
        resp = client.post(
            f"{API}/assessment/start",
            json={"profile_uid": "no-such-profile-uid"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == 1002

    def test_start_without_profile_still_ok(self, client, user_token):
        """不传档案：仍成功（回归口径，profile_id 为空）。"""
        headers = user_token_headers(client, "br-noprofile-user")
        data = self._start(client, headers, {})
        assert data["assessment_uid"]
        assert data["profile_id"] is None

    def test_full_flow_report_keeps_profile_link(self, client, user_token):
        """start(uid)→作答→提交→报告：档案关联与计分链路不受影响。"""
        from app.db import get_session_factory
        from app.models import Assessment

        headers = user_token_headers(client, "br-flow-user")
        profile = _create_child_profile(client, headers)
        data = self._start(client, headers, {"profile_uid": profile["profile_uid"]})
        uid = data["assessment_uid"]
        # 16 题作答（1-5 分循环）
        for q_no in range(1, 17):
            resp = client.put(
                f"{API}/assessment/{uid}/answer",
                json={"q_no": q_no, "raw_score": (q_no % 5) + 1},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
        resp = client.post(
            f"{API}/assessment/{uid}/submit",
            json={"client_request_id": f"br-flow-{gen_uuid()[:8]}"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        assert body["data"]["report_uid"]

        db = get_session_factory()()
        try:
            row = (
                db.query(Assessment)
                .filter(Assessment.assessment_uid == uid)
                .first()
            )
            assert row.status == "completed"
            assert row.type_code in ("easy", "active", "sensitive", "slow_warm")
            assert row.profile_id, "档案关联丢失"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 问题 3：Agent 日志 mock 字段（落库 + admin 端点响应）
# ---------------------------------------------------------------------------
class TestAdminAgentLogsMockFields:
    """mock 问答流后 admin 日志端点响应携带耗时/Token/意图。"""

    def test_admin_log_endpoints_expose_mock_fields(self, client, user_token, admin_token):
        """列表 latency 非空；详情 tokens/latency 非空；intent_route 含意图。"""
        from app.db import get_session_factory
        from app.models import QaSession

        headers = user_token_headers(client, "br-log-user")
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": OUTSIDE_QUESTION,
                "client_request_id": f"br-log-{gen_uuid()[:8]}",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        session_uid = resp.json()["data"]["session_uid"]

        from tests.conftest import parse_sse

        stream = client.post(
            f"{API}/qa/sessions/{session_uid}/stream", headers=headers
        )
        assert stream.status_code == 200, stream.text
        assert parse_sse(stream.text)[-1][0] == "completed"

        db = get_session_factory()()
        try:
            sess = (
                db.query(QaSession)
                .filter(QaSession.session_uid == session_uid)
                .first()
            )
            assert sess is not None
            session_id = sess.id
        finally:
            db.close()

        admin_headers = admin_token("admin")
        # 列表：LLM 类节点 latency_ms 非空（mock 确定性区间 800-2000）
        resp = client.get(
            f"{API}/admin/agent-logs",
            params={"session_id": session_id, "page_size": 50},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        llm_ids = ("intent_route", "child_agent", "safety_agent")
        llm_items = [i for i in items if i["agent_id"] in llm_ids]
        assert llm_items, f"缺 LLM 类日志：{[i['agent_id'] for i in items]}"
        for item in llm_items:
            assert item["latency_ms"], item

        # 详情：tokens/latency 非空；intent_route 行 output_json 含意图
        detail_by_agent = {}
        for item in llm_items:
            resp = client.get(
                f"{API}/admin/agent-logs/{item['id']}", headers=admin_headers
            )
            assert resp.status_code == 200, resp.text
            detail = resp.json()["data"]
            assert detail["latency_ms"], detail["agent_id"]
            assert (detail["prompt_tokens"] or 0) > 0, detail["agent_id"]
            assert (detail["completion_tokens"] or 0) > 0, detail["agent_id"]
            detail_by_agent[detail["agent_id"]] = detail

        intent_detail = detail_by_agent["intent_route"]
        assert intent_detail["output_json"].get("intent"), intent_detail["output_json"]

        # 各 Agent 行（child_agent/safety_agent）output_json 合并 intent，
        # 后台日志详情不再显示「意图=--」（评估 2026-10-12 观测补齐）
        for agent_id in ("child_agent", "safety_agent"):
            agent_detail = detail_by_agent.get(agent_id)
            assert agent_detail, f"缺 {agent_id} 日志行"
            assert agent_detail["output_json"].get("intent"), (
                agent_detail["output_json"]
            )

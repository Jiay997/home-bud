# -*- coding: utf-8 -*-
"""finalize-modules-to-100 Task 2（可观测与 mock 口径补齐）回归测试。

覆盖三个子项（缺陷台账 SIM-25 关联）：
- 2.1 mock 网关 L2 语义确定性模拟：预置语义类高风险语句表（词库外的
  语义类表述）在 mock 模式下按对应类别拦截并生成风险事件；表外放行；
- 2.2 AgentCallLog 耗时/Token 填充：mock 链路的确定性耗时（800-2000ms
  按节点伪随机但可复现）与 token 估算落到 agent_call_log；
- 2.3 词库规则测试器分级档位：/admin/lexicon/test 响应新增 risk_result
  分级字段（L1/L2 + 档位/类别，与风险引擎判定结构对齐，只增不改）。

测试仅依赖 conftest 既有夹具（测试库 / client / user_token / admin_token /
llm_mock autouse），真实 LLM 模式路径零改动不受影响。
"""
import json

import pytest

from app.llm.gateway import (
    MOCK_LATENCY_MAX,
    MOCK_LATENCY_MIN,
    LlmGateway,
    estimate_mock_tokens,
    get_gateway,
    mock_latency_ms,
)
from app.llm.mock_semantic_corpus import MOCK_SEMANTIC_CORPUS, match_mock_semantic

API = "/api/v1"

# 表内语句回归样例（语料条目：捂住口鼻 → child_abuse，词库外语义类表述）
CORPUS_QUESTION = "宝宝一直捂住口鼻不让喘气怎么安抚"
# 表外普通问题（不撞语料短语、不撞一级词库，mock 下应正常走完）
OUTSIDE_QUESTION = "两岁孩子晚上睡觉不踏实总翻来覆去怎么办"


# ---------------------------------------------------------------------------
# 2.1 预置语义语料表（单元级）
# ---------------------------------------------------------------------------
class TestMockSemanticCorpus:
    """预置语义类高风险语句表的结构与匹配口径。"""

    def test_corpus_size_and_fields(self):
        """语料表规模 10-20 条，每条含 text/category/score/band 标注。"""
        assert 10 <= len(MOCK_SEMANTIC_CORPUS) <= 20
        for item in MOCK_SEMANTIC_CORPUS:
            assert item.get("text"), item
            assert item.get("category"), item
            assert item.get("score") in (0.9, 0.65), item
            assert item.get("band") in ("high", "mid"), item

    def test_corpus_excludes_l1_lexicon_terms(self):
        """语料语句不得与一级词库种子词重叠（词库词走 L1 已拦截）。"""
        from scripts.seed_data import LEXICON

        lexicon_terms = [t[0] for t in LEXICON]
        for item in MOCK_SEMANTIC_CORPUS:
            text = str(item["text"])
            for term in lexicon_terms:
                assert term not in text, f"语料 {text!r} 撞词库词 {term!r}"

    def test_match_hit_returns_score_and_category(self):
        """命中：返回与真实语义模型同构的 {"score", "category"}。"""
        hit = match_mock_semantic("孩子一直捂住口鼻不让喘气，家里人都急死了")
        assert hit is not None
        assert hit["category"] == "child_abuse"
        assert float(hit["score"]) > 0.8

    def test_match_miss_returns_none(self):
        """表外文本：返回 None（放行口径由网关维持）。"""
        assert match_mock_semantic("两岁孩子晚上睡觉不踏实怎么办") is None
        assert match_mock_semantic("") is None


# ---------------------------------------------------------------------------
# 2.1 mock 网关语义分支（单元级）
# ---------------------------------------------------------------------------
class TestGatewayMockSemantic:
    """mock 网关 semantic purpose 的确定性分类口径。"""

    def setup_method(self):
        """每个用例前重置网关单例引用（避免跨用例状态）。"""
        self.gateway = get_gateway()

    def test_mock_semantic_corpus_question_blocks(self):
        """表内语句：mock 语义返回对应类别高分（>0.8 → L1/high 拦截）。"""
        resp = self.gateway.chat(
            [{"role": "user", "content": CORPUS_QUESTION}], purpose="semantic"
        )
        parsed = json.loads(resp["content"])
        assert parsed["category"] == "child_abuse"
        assert float(parsed["score"]) > 0.8

    def test_mock_semantic_plain_question_passes(self):
        """表外普通问题：维持原放行口径（score=0.1，category=None）。"""
        resp = self.gateway.chat(
            [{"role": "user", "content": OUTSIDE_QUESTION}], purpose="semantic"
        )
        parsed = json.loads(resp["content"])
        assert float(parsed["score"]) < 0.5
        assert parsed["category"] is None

    def test_mock_semantic_gray_zone_convention_kept(self):
        """既有验收约定保留：含「灰区测试」返回 0.65（拦截+引导区间）。"""
        resp = self.gateway.chat(
            [{"role": "user", "content": "这是一条灰区测试语句"}], purpose="semantic"
        )
        parsed = json.loads(resp["content"])
        assert float(parsed["score"]) == 0.65


# ---------------------------------------------------------------------------
# 2.1 mock 模式端到端拦截链路（集成级，走问答 SSE）
# ---------------------------------------------------------------------------
def _create_qa_session(client, headers, question, client_request_id):
    """创建问答会话。

    Args:
        client: TestClient。
        headers: 鉴权头。
        question: 问题原文。
        client_request_id: 幂等键。

    Returns:
        会话 data 字典。

    Raises:
        AssertionError: 响应非 200 或 code 非 0。
    """
    resp = client.post(
        f"{API}/qa/sessions",
        json={
            "entry": "child",
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
    from tests.conftest import parse_sse

    resp = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


@pytest.mark.usefixtures("client", "user_token")
class TestMockSemanticBlockingE2E:
    """mock 模式下语义类高危表述的完整拦截链路（SIM-25 回归）。"""

    def test_corpus_question_blocked_with_event_no(self, client, user_token):
        """表内语句：blocked 帧携带 risk_event_no（L2 语义拦截链路打通）。"""
        headers, _ = user_token("dev-task2-block")
        data = _create_qa_session(client, headers, CORPUS_QUESTION, "task2-block-1")
        frames = _run_stream(client, headers, data["session_uid"])

        events = [e for e, _ in frames]
        assert events[0] == "started"
        assert "blocked" in events
        blocked_idx = events.index("blocked")
        # 阻断即返：blocked 后无任何正文/完成帧
        assert "section_delta" not in events
        assert "completed" not in events
        blocked = frames[blocked_idx][1]
        assert blocked["risk_event_no"]
        assert isinstance(blocked["channels"], list)

    def test_outside_question_completes(self, client, user_token):
        """表外普通问题：mock 正常帧序走完（started → section* → completed）。"""
        headers, _ = user_token("dev-task2-ok")
        data = _create_qa_session(client, headers, OUTSIDE_QUESTION, "task2-ok-1")
        frames = _run_stream(client, headers, data["session_uid"])

        events = [e for e, _ in frames]
        assert events[0] == "started"
        assert "section_delta" in events
        assert "section_done" in events
        assert events[-1] == "completed"
        assert "blocked" not in events


# ---------------------------------------------------------------------------
# 2.2 AgentCallLog 耗时/Token 填充
# ---------------------------------------------------------------------------
class TestMockLatencyAndTokens:
    """mock 口径辅助函数与网关返回值（AgentCallLog 字段来源）。"""

    def test_mock_latency_range_and_deterministic(self):
        """耗时按种子伪随机落在 800-2000ms，同种子可复现。"""
        v1 = mock_latency_ms("child_agent")
        v2 = mock_latency_ms("child_agent")
        v3 = mock_latency_ms("pet_agent")
        assert MOCK_LATENCY_MIN <= v1 <= MOCK_LATENCY_MAX
        assert v1 == v2
        assert MOCK_LATENCY_MIN <= v3 <= MOCK_LATENCY_MAX

    def test_estimate_tokens(self):
        """token 估算：非零文本至少 1，随长度单调增，空文本为 0。"""
        assert estimate_mock_tokens(0) == 0
        assert estimate_mock_tokens(3) >= 1
        assert estimate_mock_tokens(90) > estimate_mock_tokens(30)

    def test_gateway_mock_returns_filled_fields(self):
        """mock 网关：tokens>0 且 latency 在 800-2000 区间（可复现）。"""
        messages = [{"role": "user", "content": "孩子晚上不肯睡觉怎么办"}]
        r1 = LlmGateway().chat(messages, purpose="child_agent")
        r2 = LlmGateway().chat(messages, purpose="child_agent")
        assert r1["prompt_tokens"] > 0
        assert r1["completion_tokens"] > 0
        assert MOCK_LATENCY_MIN <= r1["latency_ms"] <= MOCK_LATENCY_MAX
        assert r1["prompt_tokens"] == r2["prompt_tokens"]
        assert r1["completion_tokens"] == r2["completion_tokens"]
        assert r1["latency_ms"] == r2["latency_ms"]


class TestAgentCallLogFilled:
    """mock 链路 agent_call_log 落库字段（后台详情「耗时/输出 Token 数」）。"""

    def test_agent_logs_have_latency_and_tokens(self, client, user_token):
        """mock 问答完成后：LLM 类节点日志 latency∈[800,2000]、tokens>0。"""
        from app.db import get_session_factory
        from app.models import AgentCallLog, QaSession

        headers, _ = user_token("dev-task2-log")
        data = _create_qa_session(client, headers, OUTSIDE_QUESTION, "task2-log-1")
        frames = _run_stream(client, headers, data["session_uid"])
        assert frames[-1][0] == "completed"

        db = get_session_factory()()
        try:
            sess = (
                db.query(QaSession)
                .filter(QaSession.session_uid == data["session_uid"])
                .first()
            )
            assert sess is not None
            logs = (
                db.query(AgentCallLog)
                .filter(AgentCallLog.session_id == sess.id)
                .all()
            )
            llm_logs = [
                log
                for log in logs
                if log.agent_id
                in ("intent_route", "child_agent", "pet_agent", "safety_agent")
            ]
            assert llm_logs, f"未找到 LLM 类调用日志：{[l.agent_id for l in logs]}"
            for log in llm_logs:
                assert log.latency_ms is not None, log.agent_id
                assert MOCK_LATENCY_MIN <= log.latency_ms <= MOCK_LATENCY_MAX, (
                    f"{log.agent_id} latency={log.latency_ms}"
                )
                assert (log.prompt_tokens or 0) > 0, log.agent_id
                assert (log.completion_tokens or 0) > 0, log.agent_id
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2.3 词库规则测试器分级档位（/admin/lexicon/test）
# ---------------------------------------------------------------------------
class TestLexiconTesterRiskResult:
    """测试器响应新增 risk_result 分级字段（只增不改，向后兼容）。"""

    def test_response_contains_risk_result_l1(self, client, admin_token):
        """L1 词库命中样例：risk_result.level=L1、band=rule_hit、类别对齐。"""
        headers = admin_token("admin")
        resp = client.post(
            f"{API}/admin/lexicon/test",
            json={"text": "医生让孩子确诊自闭症了怎么办"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # 既有字段保留（向后兼容）
        assert data["hit"] is True
        assert isinstance(data["matched_terms"], list)
        assert isinstance(data["matched_patterns"], list)
        # 新增分级字段：与风险引擎判定结构对齐
        rr = data["risk_result"]
        assert rr["blocked"] is True
        assert rr["level"] == "L1"
        assert rr["score_band"] == "rule_hit"
        assert rr["category_code"]

    def test_response_risk_result_plain_text_passes(self, client, admin_token):
        """表外普通样例：risk_result 放行口径（blocked=False、level=None）。"""
        headers = admin_token("admin")
        resp = client.post(
            f"{API}/admin/lexicon/test",
            json={"text": "孩子几岁开始刷牙合适"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        rr = resp.json()["data"]["risk_result"]
        assert rr["blocked"] is False
        assert rr["level"] is None

    def test_response_risk_result_semantic_l2(self, client, admin_token):
        """语义类样例（语料表内）：mock 语义分级返回 L2 档位（软类别 mid）。"""
        headers = admin_token("admin")
        resp = client.post(
            f"{API}/admin/lexicon/test",
            json={"text": "小狗误食了老鼠药怎么办"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        rr = resp.json()["data"]["risk_result"]
        assert rr["blocked"] is True
        assert rr["level"] == "L2"
        assert rr["score_band"] == "mid"
        assert rr["category_code"] == "pet_poison"

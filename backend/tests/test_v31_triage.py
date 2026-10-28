# -*- coding: utf-8 -*-
"""V3.1 RQ-06 分级决策 + RQ-07 信任叙事验收测试。

覆盖（对齐 PRD V3.1 §3.6 / §3.7 与 E2E-19）：

引擎层（纯函数，无数据库）：
- 5 类首批模板各自可定档；
- AC-RQ06-2 硬规则：<3 月龄 ≥37.5℃ **必 🔴**；2 岁低热精神正常 → 🟢；
- 保守从严：信息不足时不得默认 🟢（未识别精神状态不命中绿档）；
- AC-RQ06-4：档位文案**不含**确定性结论表述；
- AC-RQ06-7：夜间时段（22:00–6:00）非绿档追加夜间就医提示；
- DR-29：输出携带命中规则编码与规则版本，可还原。

接口层：
- `GET /triage/decide` 返回档位与规则快照；
- SSE `completed` 帧携带 `triage` / `trust_bar` / `ai_label` 三要素；
- 分级前置块（档位卡 + 红旗 / 禁忌）置顶在首个分节第一条 block；
- `POST /qa/sessions/{uid}/triage/recheck` 支持追问重判与 🟢→🔴 强提醒。
"""
import json

import pytest

from app.services import trust_service
from app.triage import engine as triage_engine
from app.triage import templates as triage_templates

from tests.conftest import parse_sse

API = "/api/v1"

# 可控的「夜间」时间（22:30 UTC+8）
NIGHT = __import__("datetime").datetime(
    2026, 10, 20, 22, 30, tzinfo=__import__("datetime").timezone(
        __import__("datetime").timedelta(hours=8)
    )
)
# 白天时间（10:00 UTC+8）
DAY = __import__("datetime").datetime(
    2026, 10, 20, 10, 0, tzinfo=__import__("datetime").timezone(
        __import__("datetime").timedelta(hours=8)
    )
)


@pytest.fixture(autouse=True)
def signed_triage_rules(clean_state):
    """测试基线夹具：模拟运营已完成全部分诊规则的专家签署。

    D-07 修复后，DB 来源的快照只允许 `expert_signoff` 非空的规则对外判定。
    测试库种子数据默认未签署（与真实初始状态一致），若直接跑接口用例会
    统一进入「分级结论暂缓发布」态。本夹具在 clean_state 完成后签署种子
    规则，用于验证「已签署环境」下的既有档位契约；未签署门禁本身由
    `test_db_rules_without_signoff_are_publish_gated` 单独覆盖。

    Args:
        clean_state: conftest 的函数级清表/重种子夹具（依赖保证先执行）。

    Yields:
        None。
    """
    from sqlalchemy import text

    from tests.conftest import get_engine

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE triage_rule SET expert_signoff = :signoff"),
            {"signoff": "测试基线（模拟专家签署）"},
        )
    yield


def _agree_all(client, headers):
    """签署基础 + 儿童信息单独同意（问答 / 建档前置门禁）。

    Args:
        client: TestClient。
        headers: 鉴权头。
    """
    for consent_type in ("base", "child_personal_info"):
        resp = client.post(
            f"{API}/consent/agree",
            json={"consent_type": consent_type},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["code"] == 0


def _birth_months_ago(months: int) -> str:
    """返回「N 个月前」的出生日期字符串（按当前日期相对计算）。

    Args:
        months: 月数（0 表示本月出生）。

    Returns:
        YYYY-MM-DD 字符串。
    """
    from datetime import date

    today = date.today()
    total = today.year * 12 + (today.month - 1) - months
    year, month_index = divmod(total, 12)
    day = min(today.day, 28)
    return date(year, month_index + 1, day).isoformat()


def _create_child(client, headers, birth_date=None, months_ago=None):
    """创建儿童档案（可按「N 月龄」相对指定出生日期）。

    Args:
        client: TestClient。
        headers: 鉴权头。
        birth_date: 绝对出生日期（优先）。
        months_ago: 相对月龄（birth_date 为空时使用）。

    Returns:
        档案视图字典。
    """
    if birth_date is None:
        birth_date = _birth_months_ago(months_ago if months_ago is not None else 18)
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": "小伴", "birth_date": birth_date},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def _create_pet(client, headers, pet_type="dog", age_band="adult"):
    """创建宠物档案。

    Args:
        client: TestClient。
        headers: 鉴权头。
        pet_type: cat / dog。
        age_band: junior / adult / senior。

    Returns:
        档案视图字典。
    """
    resp = client.post(
        f"{API}/profiles/pets",
        json={"name": "豆豆", "pet_type": pet_type, "age_band": age_band},
        headers=headers,
    )
    return resp


def _run_qa(client, headers, entry, question, request_id, profile_uid=None):
    """创建会话并拉流，返回 (session_uid, frames)。

    Args:
        client: TestClient。
        headers: 鉴权头。
        entry: 入口。
        question: 问题原文。
        request_id: 幂等键。
        profile_uid: 档案 UID（可选）。

    Returns:
        (session_uid, [(event, data), ...])。
    """
    payload = {
        "entry": entry,
        "question": question,
        "client_request_id": request_id,
    }
    if profile_uid:
        payload["profile_uid"] = profile_uid
    resp = client.post(f"{API}/qa/sessions", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    session_uid = body["data"]["session_uid"]
    stream = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
    assert stream.status_code == 200, stream.text
    return session_uid, parse_sse(stream.text)


def _completed_data(frames):
    """取 completed 帧数据（无则断言失败）。

    Args:
        frames: SSE 帧序列。

    Returns:
        completed 帧 data 字典。
    """
    for event, data in frames:
        if event == "completed":
            return data
    raise AssertionError(f"no completed frame: {[e for e, _ in frames]}")


# ---------------------------------------------------------------------------
# 引擎层
# ---------------------------------------------------------------------------
class TestTriageEngine:
    """分级规则引擎（毫秒级，纯函数）单元测试。"""

    def test_five_templates_cover_scenes(self):
        """首批 5 类模板齐备（fever / vomit / trauma / ingestion / pet_acute）。"""
        scenes = {rule["scene"] for rule in triage_templates.TRIAGE_RULES}
        assert {"fever", "vomit", "trauma", "ingestion", "pet_acute"} <= scenes

    def test_infant_under_3m_fever_is_red(self):
        """AC-RQ06-2 硬规则：3 月龄以下体温 ≥37.5℃ 必须 🔴。"""
        result = triage_engine.decide(
            "3个月宝宝发烧37.8度怎么办", domain="child", age_months=2, now=DAY
        )
        assert result is not None
        assert result["level"] == "red"
        assert result["rule_hits"][0]["rule_id"] == "fever_infant_lt3m"
        assert result["escalation_flags"]

    def test_two_year_low_fever_normal_state_is_green(self):
        """AC-RQ06-2：同症状 2 岁低热且精神正常 → 🟢 + 观察项清单。"""
        result = triage_engine.decide(
            "2岁孩子低烧37.8，精神状态正常，能吃能玩",
            domain="child",
            age_months=24,
            now=DAY,
        )
        assert result is not None
        assert result["level"] == "green"
        assert result["observations"]
        # 绿档必须附「不能替代面诊 / 随时可再次提问」声明（AC-RQ06-4）
        assert any("面诊" in line for line in result["disclaimers"])

    def test_no_profile_two_year_low_fever_uses_question_age(self):
        """D-02：未绑定档案但问句含「2 岁」时，不得命中 <3 月龄红档规则。"""
        result = triage_engine.decide(
            "2岁宝宝体温37.8度，精神状态好，要不要去医院",
            domain="child",
            age_months=None,
            now=DAY,
        )
        assert result is not None
        assert result["level"] == "green"
        assert result["age_source"] == "question"
        assert result["age_months_used"] == 24
        assert all(hit["rule_id"] != "fever_infant_lt3m" for hit in result["rule_hits"])

    def test_colloquial_temperature_and_state_are_recognized(self):
        """D-03：「37度8 + 精神还好」应识别为 37.8℃ 且精神正常（→ 🟢）。"""
        result = triage_engine.decide(
            "2岁宝宝低烧37度8精神还好要不要去医院",
            domain="child",
            age_months=24,
            now=DAY,
        )
        assert result is not None
        assert result["signals"]["temperature"] == 37.8
        assert result["signals"]["mental_state"] == "normal"
        assert result["level"] == "green"

    def test_db_rules_without_signoff_are_publish_gated(self):
        """D-07：DB 规则全部未签署时冻结档位发布（不得输出 green/yellow/red）。"""
        snapshot = triage_engine.TriageSnapshot(
            rules=[
                triage_engine._normalize_rule(dict(row))
                for row in triage_templates.TRIAGE_RULES
            ],
            source="db",
            signed=0,
        )
        result = triage_engine.decide(
            "2岁孩子低烧37.8，精神状态正常，能吃能玩",
            domain="child",
            age_months=24,
            now=DAY,
            snapshot=snapshot,
        )
        assert result is not None
        assert result["level"] is None
        assert result["publish_gated"] is True
        assert result["rule_hits"] == []

    def test_no_green_without_normal_mental_state(self):
        """保守从严：未识别到「精神正常」时不落入绿档（防误判居家观察）。"""
        result = triage_engine.decide(
            "孩子低烧37.6度", domain="child", age_months=24, now=DAY
        )
        assert result is not None
        assert result["level"] != "green"

    def test_vomit_repeated_is_yellow(self):
        """反复呕吐（≥3 次）：保守给 🟡（脱水风险需评估）。"""
        result = triage_engine.decide(
            "孩子晚上呕吐了三次，精神还可以", domain="child", age_months=30, now=DAY
        )
        assert result is not None
        assert result["level"] == "yellow"

    def test_trauma_with_consciousness_change_is_red(self):
        """跌落碰撞伴意识改变 / 呕吐 → 🔴。"""
        result = triage_engine.decide(
            "孩子摔下床磕到头，吐了两次，叫不醒", domain="child", age_months=20, now=DAY
        )
        assert result is not None
        assert result["level"] == "red"

    def test_pet_low_risk_ingestion_is_green(self):
        """宠物误食低危物品（纸）→ 🟢（E2E-19 第四例）。"""
        result = triage_engine.decide("狗狗误食了一点纸，精神好", domain="pet", now=DAY)
        assert result is not None
        assert result["level"] == "green"
        assert result["scene"] == "ingestion"

    def test_pet_hazard_ingestion_not_green(self):
        """宠物误食巧克力：低危绿档被 none_keywords 否决，保守给 🟡。"""
        result = triage_engine.decide("猫误食了巧克力", domain="pet", now=DAY)
        assert result is not None
        assert result["level"] != "green"

    def test_non_triage_question_returns_none(self):
        """非急症问题不进入分级（走常规科普回答）。"""
        assert (
            triage_engine.decide("1岁宝宝辅食添加顺序", domain="child", age_months=12)
            is None
        )

    def test_no_deterministic_phrases_in_output(self):
        """AC-RQ06-4：档位输出零确定性结论表述。"""
        samples = [
            ("3个月宝宝发烧37.8度", "child", 2),
            ("2岁低烧37.8精神正常", "child", 24),
            ("孩子呕吐三次", "child", 30),
            ("狗狗抽搐了", "pet", None),
            ("宝宝发烧39.5度", "child", 8),
        ]
        for question, domain, months in samples:
            result = triage_engine.decide(
                question, domain=domain, age_months=months, now=DAY
            )
            assert result is not None, question
            text = triage_engine.flatten_triage_text(result)
            assert triage_engine.scan_deterministic_phrases(text) == [], question

    def test_night_mode_adds_notice_for_non_green(self):
        """AC-RQ06-7：夜间 🟡/🔴 附夜间就医提示；绿档附就医兜底提示。"""
        red = triage_engine.decide(
            "3个月宝宝发烧38度", domain="child", age_months=2, now=NIGHT
        )
        assert red is not None
        assert red["night_mode"] is True
        assert "夜间" in (red["night_notice"] or "")
        green = triage_engine.decide(
            "2岁孩子低烧37.8，精神状态正常", domain="child", age_months=24, now=NIGHT
        )
        assert green is not None
        assert green["night_mode"] is True
        assert "就医" in (green["night_notice"] or "")

    def test_rule_version_and_hits_recoverable(self):
        """DR-29：输出带规则编码与版本，线上判定可还原。"""
        result = triage_engine.decide(
            "3个月宝宝发烧37.8度", domain="child", age_months=2, now=DAY
        )
        assert result is not None
        assert result["rule_version"] >= 1
        assert all(hit["rule_id"] and hit["version"] for hit in result["rule_hits"])

    def test_insufficient_state_gives_no_level(self):
        """信息不足态：不给档位，只给需补充的关键信息（AC-RQ06-1 边界）。"""
        result = triage_engine.decide("宝宝不舒服", domain="child", now=DAY)
        # 无场景关键词 → 不进入分级
        assert result is None
        # 宠物场景命中但无规则可判 → 信息不足态
        insufficient = triage_engine.insufficient_result("pet_acute", "pet", "症状描述不足")
        assert insufficient["level"] is None
        assert insufficient["missing_info"]


# ---------------------------------------------------------------------------
# 接口层
# ---------------------------------------------------------------------------
class TestTriageApi:
    """分级决策接口与 SSE 契约。"""

    def test_decide_endpoint_returns_level_and_snapshot(self, client, user_token):
        """`GET /triage/decide` 返回档位、规则快照与来源标注。"""
        headers, _ = user_token("dev-v31-triage-api")
        resp = client.get(
            f"{API}/triage/decide",
            params={"question": "2个月宝宝发烧37.8度", "domain": "child"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["triage"]["level"] == "red"
        assert data["rule_snapshot"]["total"] >= 5
        assert data["rule_snapshot"]["by_scene"]

    def test_decide_endpoint_rejects_bad_domain(self, client, user_token):
        """非法 domain → 1001。"""
        headers, _ = user_token("dev-v31-triage-bad")
        resp = client.get(
            f"{API}/triage/decide",
            params={"question": "发烧", "domain": "unknown"},
            headers=headers,
        )
        assert resp.json()["code"] == 1001

    def test_sse_completed_frame_carries_triage_and_trust_bar(self, client, user_token):
        """SSE completed 帧携带 triage / trust_bar / ai_label（RQ-06 + RQ-07 + RQ-01）。"""
        headers, _ = user_token("dev-v31-triage-sse")
        _agree_all(client, headers)
        child = _create_child(client, headers, months_ago=2)  # ≈2 月龄
        data = _completed_data(
            _run_qa(
                client,
                headers,
                "child",
                "宝宝发烧37.9度怎么办",
                "v31-triage-sse-1",
                profile_uid=child["profile_uid"],
            )[1]
        )
        triage = data["triage"]
        assert triage["level"] == "red", triage
        assert data["ai_label"]["visible"] is True
        assert data["ai_label"]["text_id"]
        trust = data["trust_bar"]
        assert trust["ai_label"]["text_id"]
        assert trust["elements"]["triage_badge"]["status"] == "present"
        assert trust["elements"]["contraindications"]["pinned"] is True

    def test_triage_blocks_pinned_at_top(self, client, user_token):
        """档位卡 + 红旗块置顶在首个分节最前（AC-RQ07-2）。"""
        headers, _ = user_token("dev-v31-triage-block")
        _agree_all(client, headers)
        child = _create_child(client, headers, months_ago=2)
        frames = _run_qa(
            client,
            headers,
            "child",
            "宝宝发烧38.2度要不要去医院",
            "v31-triage-block-1",
            profile_uid=child["profile_uid"],
        )[1]
        first_section = None
        for event, data in frames:
            if event == "section_done":
                first_section = data
                break
        assert first_section is not None
        keys = [block.get("block_key") for block in first_section["blocks"]]
        assert keys[0] == "triage_card", keys
        assert any(block.get("pinned") for block in first_section["blocks"])

    def test_recheck_escalates_green_to_red(self, client, user_token):
        """追问重判：🟢→🔴 返回置顶强提醒标记（AC-RQ06-5）。"""
        headers, _ = user_token("dev-v31-triage-recheck")
        _agree_all(client, headers)
        child = _create_child(client, headers, months_ago=24)
        session_uid, _ = _run_qa(
            client,
            headers,
            "child",
            "孩子低烧37.8，精神状态正常，能吃能玩",
            "v31-triage-recheck-1",
            profile_uid=child["profile_uid"],
        )
        resp = client.post(
            f"{API}/qa/sessions/{session_uid}/triage/recheck",
            json={"followup": "现在抽搐了，叫不醒", "temperature": 39.2},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["triage"]["level"] == "red"
        assert data["escalate_banner"] is True
        assert data["banner_text"]

    def test_stored_session_exposes_triage_and_contract(self, client, user_token):
        """轮询兜底接口同样携带档位与信任条（要素不因链路不同而缺失）。"""
        headers, _ = user_token("dev-v31-triage-get")
        _agree_all(client, headers)
        child = _create_child(client, headers, months_ago=2)
        session_uid, _ = _run_qa(
            client,
            headers,
            "child",
            "宝宝发烧38.1度怎么办",
            "v31-triage-get-1",
            profile_uid=child["profile_uid"],
        )
        resp = client.get(f"{API}/qa/sessions/{session_uid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["triage"]["level"] == "red"
        assert data["trust_bar"] is not None
        assert data["ai_label"]["visible"] is True
        assert data["input_mode"] == "text"


# ---------------------------------------------------------------------------
# 信任条装配（RQ-07）
# ---------------------------------------------------------------------------
class TestTrustBar:
    """信任条四要素与缺失态口径。"""

    def test_generic_age_when_no_profile(self, db_session=None):
        """无档案 → 「通用区间」+ 建档引导（AC-RQ07-4）。"""
        info = trust_service.age_adaptation(False, None)
        assert info["generic"] is True
        assert info["label"] == trust_service.GENERIC_AGE_LABEL
        assert info["hint"]

    def test_age_label_from_profile(self):
        """有档案 → 按月龄档展示（AC-RQ07-1 第 2 要素）。"""
        info = trust_service.age_adaptation(True, "6-12m", age_months=9)
        assert info["generic"] is False
        assert "6–12" in info["label"]
        assert "9" in info["label"]

    def test_source_levels_without_db_refs_are_empty(self):
        """无引用条目 → 来源徽标为空（前端显示信息待补，而非伪造等级）。"""
        assert trust_service.build_source_levels(None, []) == []

    def test_pet_age_label(self):
        """宠龄标识按物种档展示。"""
        info = trust_service.age_adaptation(True, "senior", domain="pet")
        assert "老年" in info["label"]

    def test_checklist_items_declared(self):
        """首答信任检查单 10 项齐备（§3.7.3）。"""
        assert len(trust_service.CHECKLIST_ITEMS) == 10


    def test_history_detail_exposes_contract(self, client, user_token):
        """历史详情同样携带标识 / 信任条 / 档位（三条链路口径一致）。"""
        headers, _ = user_token("dev-v31-triage-history")
        _agree_all(client, headers)
        child = _create_child(client, headers, months_ago=2)
        session_uid, _ = _run_qa(
            client,
            headers,
            "child",
            "宝宝发烧37.9度怎么办",
            "v31-triage-history-1",
            profile_uid=child["profile_uid"],
        )
        resp = client.get(f"{API}/history/qa/{session_uid}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        data = body["data"]
        assert data["triage"]["level"] == "red"
        assert data["ai_label"]["visible"] is True
        assert data["trust_bar"] is not None
        assert data["input_mode"] == "text"


# ---------------------------------------------------------------------------
# 性能与确定性（NFR：分级判定毫秒级，不增加 >300ms 延迟）
# ---------------------------------------------------------------------------
class TestTriagePerformance:
    """规则引擎性能与判定确定性。"""

    def test_decide_is_millisecond_level(self):
        """单次判定 P95 < 300ms（实测应在毫秒级，远低于 PRD 预算）。"""
        import time

        questions = [
            "3个月宝宝发烧37.8度怎么办",
            "2岁孩子低烧37.8，精神状态正常",
            "孩子晚上呕吐了三次",
            "狗狗误食了一点纸",
            "孩子摔下床磕到头叫不醒",
        ] * 20
        durations = []
        for question in questions:
            started = time.perf_counter()
            triage_engine.decide(question, domain="child", age_months=24, now=DAY)
            durations.append((time.perf_counter() - started) * 1000)
        durations.sort()
        p95 = durations[int(len(durations) * 0.95) - 1]
        assert p95 < 300, f"分级判定 P95={p95:.2f}ms 超出 300ms 预算"
        # 引擎为纯函数且无 IO：中位数应远低于 10ms
        assert durations[len(durations) // 2] < 10

    def test_same_input_same_level(self):
        """同输入同档位（幂等，模型不参与裁决）。"""
        question = "孩子发烧38.6度，精神还好"
        levels = {
            triage_engine.decide(question, domain="child", age_months=18, now=DAY)["level"]
            for _ in range(20)
        }
        assert levels == {"yellow"}, levels

    def test_blocked_precedes_triage(self, client, user_token):
        """风险拦截优先于分级：命中 F8 硬类别时不出档位（§5.1 路由裁决）。"""
        headers, _ = user_token("dev-v31-triage-precedence")
        _agree_all(client, headers)
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "孩子被虐待儿童怎么办，还发烧了",
                "client_request_id": "v31-triage-precedence-1",
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        frames = parse_sse(
            client.post(
                f"{API}/qa/sessions/{created['data']['session_uid']}/stream",
                headers=headers,
            ).text
        )
        events = [event for event, _ in frames]
        assert "blocked" in events
        assert "completed" not in events
        for event, data in frames:
            if event == "blocked":
                assert "triage" not in data

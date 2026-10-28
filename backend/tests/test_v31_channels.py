# -*- coding: utf-8 -*-
"""V3.1 RQ-03 危机渠道清单测试（E2E-22 口径 / 缺陷 N3 回归）。

核心断言：

- **单一数据源**：问答渠道卡与后台维护读同一张 `crisis_channel` 表
  （修复缺陷 N3「双数据源」）；
- **占位不编造**：号码未回填时为 `placeholder` + 维护中提示，`phone_number`
  下发为 null；
- **超期降级**：`review_due_at` 到期未复核的条目自动转 `pending_review`，
  前端不再展示号码（AC-RQ03-4）；
- **核验留痕**：每次核验写 `channel_review_record` 并可查询（AC-RQ03-5）；
- **二次确认**：改号码需 confirm + 渠道编码后 4 位 + 原因（§3.4）；
- **角色脱敏**：客服角色看到的号码为 `***`（§3.3.4）。
"""
from datetime import datetime, timedelta, timezone

from app.models import CrisisChannel
from app.services import channel_service

API = "/api/v1"
TZ = timezone(timedelta(hours=8))


def _db():
    """获取测试库会话（用例内直接改库以构造边界态）。

    Returns:
        SQLAlchemy Session。
    """
    from app.db import get_session_factory

    return get_session_factory()()


class TestChannelSingleSource:
    """渠道数据源收敛与空态占位。"""

    def test_risk_channels_come_from_table(self, client, user_token):
        """拦截卡渠道来自 crisis_channel 表，且带占位语义字段。"""
        headers, _ = user_token("dev-v31-channel-card")
        resp = client.get(
            f"{API}/risk/channels", params={"category": "high_fever"}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        channels = resp.json()["data"]["channels"]
        assert channels, "high_fever 应有儿科急症渠道卡"
        card = channels[0]
        assert card["channel_code"] == "fever_emergency"
        assert card["source"] == "crisis_channel"
        # 号码未回填 → 占位 + 维护中，绝不编造
        assert card["phone_number"] is None
        assert card["placeholder"] is True
        assert "维护中" in (card["notice"] or "")

    def test_unknown_category_returns_placeholder(self, client, user_token):
        """无匹配条目的类别返回占位卡（不编造号码，AC-RQ03-3）。"""
        headers, _ = user_token("dev-v31-channel-empty")
        # 宠物出血映射到宠物急诊渠道（有清单条目，号码未回填 → 占位）
        channels = client.get(
            f"{API}/risk/channels", params={"category": "pet_bleeding"}, headers=headers
        ).json()["data"]["channels"]
        assert channels
        assert channels[0]["channel_code"] == "pet_emergency"
        assert channels[0]["placeholder"] is True
        assert channels[0]["phone_number"] is None
        # 完全未知的类别 → 占位卡 + 通用求助指引（不含号码）
        unknown = client.get(
            f"{API}/risk/channels", params={"category": "unknown_xyz"}, headers=headers
        ).json()["data"]["channels"]
        assert unknown
        assert unknown[0]["placeholder"] is True
        assert unknown[0]["phone_number"] is None
        assert unknown[0]["fallback_text"]

    def test_admin_list_channels_is_same_source(self, client, admin_token):
        """后台列表与问答卡读同一张表（缺陷 N3 回归断言）。"""
        headers = admin_token("operator")
        resp = client.get(f"{API}/admin/channels", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["data_source"] == "crisis_channel"
        codes = {item["channel_code"] for item in data["items"]}
        assert {"police", "fever_emergency", "pet_emergency"} <= codes
        assert data["summary"]["total"] >= 6
        # 号码缺失类别应被「必需类目」检查捕获
        assert isinstance(data["summary"]["missing_required"], dict)


class TestChannelReviewFlow:
    """渠道核验与超期降级。"""

    def test_phone_update_requires_confirm(self, client, admin_token):
        """改号码缺二次确认 → 1602；后 4 位不符 → 1001。"""
        headers = admin_token("operator")
        # 缺 confirm
        resp = client.put(
            f"{API}/admin/channels/psych_hotline",
            json={"phone_number": "01012345678", "reason": "回填公开热线"},
            headers=headers,
        )
        assert resp.json()["code"] == 1602, resp.text
        # 有 confirm 但后 4 位不符
        resp = client.put(
            f"{API}/admin/channels/psych_hotline",
            json={
                "phone_number": "01012345678",
                "reason": "回填公开热线",
                "confirm_token": "CONFIRMED",
                "channel_code_suffix": "0000",
            },
            headers=headers,
        )
        assert resp.json()["code"] == 1001, resp.text
        # 正确二次确认 → 成功
        resp = client.put(
            f"{API}/admin/channels/psych_hotline",
            json={
                "phone_number": "01012345678",
                "reason": "回填公开热线",
                "confirm_token": "CONFIRMED",
                "channel_code_suffix": "line",
            },
            headers=headers,
        )
        assert resp.json()["code"] == 0, resp.text
        card = resp.json()["data"]
        assert card["phone_number"] == "01012345678"
        assert card["status"] == "active"

    def test_review_record_written_and_listed(self, client, admin_token):
        """核验记录写入并可查询（AC-RQ03-5）。"""
        headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/channels/police/review",
            json={
                "review_method": "call_dial",
                "review_result": "reachable",
                "conclusion": "拨测可接通",
            },
            headers=headers,
        )
        assert resp.json()["code"] == 0, resp.text
        review_no = resp.json()["data"]["review_no"]
        assert review_no
        listed = client.get(f"{API}/admin/channels/police/reviews", headers=headers)
        items = listed.json()["data"]["items"]
        assert items and items[0]["review_method"] == "call_dial"

    def test_expired_channel_hides_phone(self, client, admin_token, user_token):
        """超期未复核 → 状态降级且号码不再下发（AC-RQ03-4）。"""
        # 1) 运营回填号码
        admin_headers = admin_token("operator")
        resp = client.put(
            f"{API}/admin/channels/fever_emergency",
            json={
                "phone_number": "01099998888",
                "reason": "回填儿科急诊电话",
                "confirm_token": "CONFIRMED",
                "channel_code_suffix": "ency",
            },
            headers=admin_headers,
        )
        assert resp.json()["code"] == 0, resp.text
        # 2) 把复核到期时间改到过去
        db = _db()
        try:
            row = (
                db.query(CrisisChannel)
                .filter(CrisisChannel.channel_code == "fever_emergency")
                .first()
            )
            row.next_review_due_at = datetime.now(TZ) - timedelta(days=1)
            db.commit()
        finally:
            db.close()
        # 3) 降级后前台不再展示号码
        headers, _ = user_token("dev-v31-channel-expired")
        channels = client.get(
            f"{API}/risk/channels", params={"category": "high_fever"}, headers=headers
        ).json()["data"]["channels"]
        card = channels[0]
        assert card["phone_number"] is None
        assert card["placeholder"] is True
        assert card["notice"] == channel_service.PENDING_REVIEW_TEXT
        assert card["expired"] is True
        # 4) sweep 后状态转 pending_review
        db = _db()
        try:
            swept = channel_service.sweep_expired(db)
            assert swept >= 1
        finally:
            db.close()

    def test_support_role_phone_masked(self, client, admin_token):
        """客服角色号码脱敏为 ***（§3.3.4 权限六查）。"""
        # 先用运营回填一个号码
        operator = admin_token("operator")
        client.put(
            f"{API}/admin/channels/police",
            json={
                "phone_number": "11000110",
                "reason": "回填测试号码",
                "confirm_token": "CONFIRMED",
                "channel_code_suffix": "lice",
            },
            headers=operator,
        )
        support = admin_token("support")
        data = client.get(f"{API}/admin/channels", headers=support).json()["data"]
        police = next(i for i in data["items"] if i["channel_code"] == "police")
        assert police["phone_number"] == channel_service.MASKED_PHONE
        assert police["phone_masked"] is True

    def test_support_cannot_edit_channels(self, client, admin_token):
        """客服无编辑权限 → 1103。"""
        support = admin_token("support")
        resp = client.post(
            f"{API}/admin/channels",
            json={"channel_code": "test_x", "channel_name": "测试渠道"},
            headers=support,
        )
        assert resp.json()["code"] == 1103


class TestPublishGates:
    """发布门禁自检（§7.2 六项）。"""

    def test_gates_summary_reports_six_items(self, client, admin_token):
        """门禁自检返回六项（含 D-09 模板报备、D-10 专题上架），缺项时如实标未通过。"""
        headers = admin_token("admin")
        resp = client.get(f"{API}/admin/gates/summary", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        ids = {gate["id"] for gate in data["gates"]}
        assert ids == {
            "ai_label_three_links",
            "copy_scan_zero_hit",
            "channel_verified",
            "triage_rules_signed",
            "reminder_templates_reported",
            "topics_published",
        }
        # AI 标识链路与文案扫描应已通过
        by_id = {gate["id"]: gate for gate in data["gates"]}
        assert by_id["ai_label_three_links"]["passed"] is True
        assert by_id["copy_scan_zero_hit"]["passed"] is True
        # 渠道号码未回填 / 规则未会签 → 如实未通过
        assert by_id["channel_verified"]["passed"] is False
        assert by_id["triage_rules_signed"]["passed"] is False
        assert data["passed"] is False

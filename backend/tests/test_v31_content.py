# -*- coding: utf-8 -*-
"""V3.1 RQ-12 轻工具 / RQ-13 交叉主题包 / RQ-14 行为内容线 / RQ-05 图片链路 测试。

覆盖：

- 轻工具：列表 / 详情 / 完成记录，**不消耗问答额度**（AC-RQ12-2），
  内容命中「能吃 / 不能吃」确定性结论即拒绝保存（AC-RQ12-4）；
- 专题包：交叉主题须育儿 + 宠物**双签**才可上架（AC-RQ13-1），
  红旗前置（AC-RQ13-2），行为内容线结构校验（AC-RQ14-1）；
- 图片链路：上传送检 → 绑定会话 → 24h 删除日志（AC-RQ05-2/3/8）；
  送检配额超限即拒绝且不扣额度。
"""
import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.models import PhotoAsset, Product
from app.services import photo_service, tool_service, topic_service

API = "/api/v1"
TZ = timezone(timedelta(hours=8))


def _db():
    """获取测试库会话。

    Returns:
        SQLAlchemy Session。
    """
    from app.db import get_session_factory

    return get_session_factory()()


def _png(size=(200, 160)) -> bytes:
    """生成测试 PNG 字节。

    Args:
        size: 尺寸。

    Returns:
        PNG 字节。
    """
    buffer = io.BytesIO()
    Image.new("RGB", size, (180, 200, 190)).save(buffer, format="PNG")
    return buffer.getvalue()


def _agree_all(client, headers):
    """签署基础 + 儿童信息同意。

    Args:
        client: TestClient。
        headers: 鉴权头。
    """
    for consent_type in ("base", "child_personal_info"):
        assert (
            client.post(
                f"{API}/consent/agree",
                json={"consent_type": consent_type},
                headers=headers,
            ).json()["code"]
            == 0
        )


# ---------------------------------------------------------------------------
# RQ-12 轻工具
# ---------------------------------------------------------------------------
class TestTools:
    """轻工具前台化。"""

    def test_list_tools_has_three_items(self, client, user_token):
        """首批 ≥3 个工具，且声明不消耗额度（AC-RQ12-1/2）。"""
        headers, _ = user_token("dev-v31-tools")
        _agree_all(client, headers)
        data = client.get(f"{API}/tools", headers=headers).json()["data"]
        codes = {item["tool_code"] for item in data["items"]}
        assert {
            "tool_fever_checklist",
            "tool_pet_behavior_checklist",
            "tool_pet_food_label",
        } <= codes
        assert data["quota_cost"] == 0
        assert data["entry"] == "secondary"
        for item in data["items"]:
            assert item["ai_label"]["visible"] is True
            assert item["disclaimer"]

    def test_tool_detail_and_complete(self, client, user_token):
        """详情可读；完成记录不消耗额度。"""
        headers, _ = user_token("dev-v31-tools-detail")
        _agree_all(client, headers)
        detail = client.get(f"{API}/tools/tool_fever_checklist", headers=headers).json()
        assert detail["code"] == 0
        assert detail["data"]["content"]["steps"]
        assert detail["data"]["quota_cost"] == 0
        done = client.post(
            f"{API}/tools/tool_fever_checklist/complete",
            json={"completed_items": 3, "next": "qa"},
            headers=headers,
        ).json()
        assert done["code"] == 0
        assert done["data"]["quota_cost"] == 0

    def test_unknown_tool_404(self, client, user_token):
        """不存在的工具 → 1002。"""
        headers, _ = user_token("dev-v31-tools-404")
        _agree_all(client, headers)
        resp = client.get(f"{API}/tools/not_exists", headers=headers)
        assert resp.json()["code"] == 1002

    def test_parser_caveat_has_no_deterministic_conclusion(self):
        """配料表解析仅做成分科普，不输出确定性进食结论（AC-RQ12-4）。"""
        tool = tool_service.get_tool(None, "tool_pet_food_label")
        assert tool is not None
        assert "不判定能否喂食" in tool["content"]["caveat"]
        assert tool_service.validate_tool_content(tool["content"]) == []

    def test_admin_rejects_deterministic_content(self, client, admin_token):
        """后台保存含「能吃」结论的工具内容 → 1001。"""
        headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/tools",
            json={
                "tool_code": "tool_bad_food",
                "title": "违规工具",
                "tool_type": "parser",
                "domain": "pet",
                "content": {"conclusion": "这个配料可以吃，放心喂"},
            },
            headers=headers,
        )
        assert resp.json()["code"] == 1001, resp.text


# ---------------------------------------------------------------------------
# RQ-13 / RQ-14 专题包
# ---------------------------------------------------------------------------
class TestTopicPacks:
    """交叉主题包与宠物行为内容线。"""

    def test_seed_topics_are_draft_until_double_signed(self, client, user_token):
        """播种专题包未会签 → 不对 C 端展示（不伪造专家签署）。"""
        headers, _ = user_token("dev-v31-topics-empty")
        _agree_all(client, headers)
        data = client.get(f"{API}/topics", headers=headers).json()["data"]
        assert data["items"] == []
        assert data["member_included"] is False

    def test_cross_topic_requires_double_signoff(self, client, admin_token):
        """交叉主题包缺宠物专家会签 → 上架被拒（AC-RQ13-1）。"""
        headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/topics",
            json={
                "topic_code": "topic_single_sign",
                "title": "只签一方的交叉包",
                "domain": "cross",
                "price_micro": 9_900_000,
                "redflag_first": True,
                "redflag_blocks": [{"key": "redflags", "title": "红旗", "content": "先就医"}],
                "content_blocks": [{"key": "action_plan", "title": "方案", "content": "说明"}],
                "review_child_signoff": "育儿专家甲",
                "status": "on",
            },
            headers=headers,
        )
        assert resp.json()["code"] == 1001, resp.text
        assert "宠物专家会签" in resp.json()["message"]

    def test_topic_publish_and_list_redflag_first(self, client, admin_token, user_token):
        """双签 + 红旗前置后可上架；C 端首块为红旗块（AC-RQ13-2）。"""
        admin_headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/topics",
            json={
                "topic_code": "topic_bite_ok",
                "title": "孩子被猫抓狗咬之后",
                "domain": "cross",
                "summary": "暴露分级与事后安抚",
                "price_micro": 9_900_000,
                "redflag_first": True,
                "redflag_blocks": [
                    {
                        "key": "redflags",
                        "title": "红旗前置",
                        "content": "24 小时内前往犬伤门诊评估。",
                    }
                ],
                "content_blocks": [
                    {"key": "physiological_check", "title": "暴露分级", "content": "Ⅰ/Ⅱ/Ⅲ 级"},
                    {"key": "action_plan", "title": "安抚", "content": "先处理情绪"},
                ],
                "review_child_signoff": "育儿专家甲",
                "review_pet_signoff": "宠物专家乙",
                "status": "on",
            },
            headers=admin_headers,
        )
        assert resp.json()["code"] == 0, resp.text
        user_headers, _ = user_token("dev-v31-topics-ok")
        _agree_all(client, user_headers)
        items = client.get(f"{API}/topics", headers=user_headers).json()["data"]["items"]
        codes = {item["topic_code"] for item in items}
        assert "topic_bite_ok" in codes
        target = next(item for item in items if item["topic_code"] == "topic_bite_ok")
        assert target["content_blocks"][0]["key"] == "redflags"
        assert target["member_included"] is False
        detail = client.get(f"{API}/topics/topic_bite_ok", headers=user_headers).json()
        assert detail["code"] == 0
        assert detail["data"]["redflag_blocks"]

    def test_recommended_by_entry_prioritises_cross(self, client, admin_token, user_token):
        """family 入口优先推荐交叉主题包（AC-RQ13-3）。"""
        admin_headers = admin_token("operator")
        for code, domain in (
            ("topic_cross_rec", "cross"),
            ("topic_pet_rec", "behavior"),
        ):
            client.post(
                f"{API}/admin/topics",
                json={
                    "topic_code": code,
                    "title": f"推荐位测试 {code}",
                    "domain": domain,
                    "price_micro": 1_000_000,
                    "redflag_first": True,
                    "redflag_blocks": [{"key": "redflags", "title": "红旗", "content": "先就医"}],
                    "content_blocks": [
                        {"key": "physiological_check", "title": "排查", "content": "说明"},
                        {"key": "redflags", "title": "红旗", "content": "说明"},
                    ],
                    "review_child_signoff": "甲",
                    "review_pet_signoff": "乙",
                    "status": "on",
                },
                headers=admin_headers,
            )
        user_headers, _ = user_token("dev-v31-topics-rec")
        _agree_all(client, user_headers)
        items = client.get(
            f"{API}/topics/recommended",
            params={"entry": "family", "limit": 2},
            headers=user_headers,
        ).json()["data"]["items"]
        assert items
        assert items[0]["domain"] == "cross"

    def test_behavior_structure_validation(self):
        """行为内容线：红旗必须在前两块内（AC-RQ14-1）。"""
        bad = [
            {"key": "behavior_cause", "title": "成因"},
            {"key": "action_plan", "title": "方案"},
            {"key": "redflags", "title": "红旗"},
        ]
        issues = topic_service.validate_behavior_structure(bad)
        assert issues
        good = [
            {"key": "physiological_check", "title": "排查"},
            {"key": "redflags", "title": "红旗"},
            {"key": "behavior_cause", "title": "成因"},
            {"key": "action_plan", "title": "方案"},
        ]
        assert topic_service.validate_behavior_structure(good) == []

    def test_member_excluded_from_topic(self, client, admin_token):
        """专题独立计费、会员不含（口径不变）。"""
        data = client.get(
            f"{API}/admin/topics", headers=admin_token("operator")
        ).json()["data"]
        assert data["items"]
        assert all(item["member_included"] is False for item in data["items"])


# ---------------------------------------------------------------------------
# RQ-05 图片链路
# ---------------------------------------------------------------------------
class TestPhotoPipeline:
    """图片提问链路的合规与生命周期。"""

    def test_upload_bind_and_purge(self, client, user_token):
        """上传送检 → 绑定会话 → 24h 删除并留删除日志（AC-RQ05-3）。"""
        headers, _ = user_token("dev-v31-photo")
        _agree_all(client, headers)
        uploaded = client.post(
            f"{API}/qa/photos",
            files={"file": ("rash.png", _png(), "image/png")},
            data={"scene": "rash"},
            headers=headers,
        ).json()
        assert uploaded["code"] == 0, uploaded
        photo_uid = uploaded["data"]["photo_uid"]
        assert uploaded["data"]["moderation_result"] == "pass"
        assert uploaded["data"]["expires_at"]
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "这道红疹需要处理吗",
                "client_request_id": "v31-photo-1",
                "input_mode": "photo",
                "photo_uids": [photo_uid],
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        session_uid = created["data"]["session_uid"]
        stream = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
        assert "event: completed" in stream.text
        session = client.get(f"{API}/qa/sessions/{session_uid}", headers=headers).json()["data"]
        assert session["input_mode"] == "photo"
        assert session["photo_meta"]["count"] == 1
        # 元数据不含 URL（AC-RQ05-4）
        assert "url" not in session["photo_meta"]
        # 24h 删除任务
        db = _db()
        try:
            asset = (
                db.query(PhotoAsset).filter(PhotoAsset.photo_uid == photo_uid).first()
            )
            assert asset is not None
            asset.expires_at = datetime.now(TZ) - timedelta(seconds=1)
            db.commit()
            removed = photo_service.purge_expired(db, now=datetime.now(TZ))
            assert removed >= 1
            db.refresh(asset)
            assert asset.deleted_at is not None
            assert asset.file_path is None
            assert asset.delete_log["result"] == "ok"
        finally:
            db.close()

    def test_photo_mode_requires_photo(self, client, user_token):
        """photo 模式未提供图片 → 1001。"""
        headers, _ = user_token("dev-v31-photo-bad")
        _agree_all(client, headers)
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "看看这道疹子",
                "client_request_id": "v31-photo-bad-1",
                "input_mode": "photo",
            },
            headers=headers,
        )
        assert resp.json()["code"] == 1001

    def test_photo_count_limit(self, client, user_token):
        """单次 >3 张 → 1001（AC-RQ05-8）。"""
        headers, _ = user_token("dev-v31-photo-limit")
        _agree_all(client, headers)
        uids = []
        for index in range(4):
            uploaded = client.post(
                f"{API}/qa/photos",
                files={"file": (f"p{index}.png", _png(), "image/png")},
                headers=headers,
            ).json()
            assert uploaded["code"] == 0, uploaded
            uids.append(uploaded["data"]["photo_uid"])
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "多图问题测试",
                "client_request_id": "v31-photo-limit-1",
                "input_mode": "photo",
                "photo_uids": uids,
            },
            headers=headers,
        )
        assert resp.json()["code"] == 1001

    def test_quota_exceeded_rejects_without_deduction(self, client, user_token, monkeypatch):
        """送检配额超限 → 1303，不进入推理、不扣额度（AC-RQ05-2）。"""
        from app.services.safety_scan import SafetyScanService

        monkeypatch.setattr(SafetyScanService, "DAILY_QUOTA", 0)
        headers, _ = user_token("dev-v31-photo-quota")
        _agree_all(client, headers)
        before = client.get(f"{API}/billing/quota", headers=headers).json()["data"]
        resp = client.post(
            f"{API}/qa/photos",
            files={"file": ("x.png", _png(), "image/png")},
            headers=headers,
        )
        assert resp.status_code == 429, resp.text
        assert resp.json()["code"] == 1303
        after = client.get(f"{API}/billing/quota", headers=headers).json()["data"]
        assert after["used"] == before["used"]

    def test_scene_guide_endpoint(self, client, user_token):
        """场景化前置说明下发（拍什么 / 如何处理 / 何时删除）。"""
        headers, _ = user_token("dev-v31-photo-guide")
        _agree_all(client, headers)
        data = client.get(f"{API}/qa/photos/guide", headers=headers).json()["data"]
        assert data["max_count"] == 3
        assert data["ttl_hours"] == 24
        assert data["privacy_notice"]
        assert len(data["scenes"]) >= 5

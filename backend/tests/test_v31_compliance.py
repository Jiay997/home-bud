# -*- coding: utf-8 -*-
"""V3.1 RQ-02 拟人化合规 / RQ-11 隐私承诺 测试。

覆盖：

- 全量文案扫描**零命中**（E2E-21 口径）；
- 变体注入能被捕获（fail-closed 验证）；
- 禁用词入库类型为 `anthropomorphic` 且**不参与**输入侧风险拦截（否则
  「陪伴」「伙伴」会被当作高危词阻断正常提问）；
- 隐私承诺：逐条附可操作跳转，且只列**已实现**能力（AC-RQ11-1/3）；
- 文案合规检查清单 5 项齐备（AC-RQ02-5）。
"""
from app.compliance import copy_scan
from app.models import LexiconTerm
from app.services import privacy_service

API = "/api/v1"


def _db():
    """获取测试库会话。

    Returns:
        SQLAlchemy Session。
    """
    from app.db import get_session_factory

    return get_session_factory()()


class TestCopyScan:
    """拟人化文案扫描能力。"""

    def test_repository_scan_zero_hit(self):
        """全量仓库扫描零命中（发布门禁口径）。"""
        result = copy_scan.scan_repository()
        assert result.errors == [], result.errors
        assert result.blocked is False, [
            (hit.path, hit.line, hit.phrase) for hit in result.hits
        ]
        assert result.scanned_files > 50

    def test_injected_variants_are_caught(self):
        """变体（空格 / 同义）注入被捕获，扫描能力可验证。"""
        samples = [
            "这是你的 AI 育儿伙伴",
            "家庭养育伙 伴已上线",
            "我们一直陪着你",
            "AI 朋 友式问答",
            "可以随时都在秒回",
        ]
        for sample in samples:
            assert copy_scan.scan_anthropomorphic(sample), sample

    def test_legal_copy_passes(self):
        """合规文案零命中（工具定位表述）。"""
        legal = [
            "Babe宝伴是面向家庭养育的科普参考工具。",
            "本内容由 AI 生成，仅供参考，不构成诊疗建议。",
            "查询、查看、参考都可以在这里完成。",
        ]
        for text in legal:
            assert copy_scan.scan_anthropomorphic(text) == [], text

    def test_replacements_provided(self):
        """命中项给出替代表述建议（便于整改）。"""
        assert copy_scan.suggestion_for("家庭养育伙伴")
        assert copy_scan.checklist() and len(copy_scan.checklist()) == 5

    def test_anthropomorphic_terms_not_used_for_input_blocking(self, client, user_token):
        """拟人化词条不参与输入侧拦截：正常提问不得被拦。"""
        db = _db()
        try:
            rows = (
                db.query(LexiconTerm)
                .filter(LexiconTerm.lexicon_type == "anthropomorphic")
                .all()
            )
            assert rows, "拟人化词表应已入库（RQ-02 AC-4）"
        finally:
            db.close()
        headers, _ = user_token("dev-v31-anthrop-qa")
        client.post(f"{API}/consent/agree", json={"consent_type": "base"}, headers=headers)
        # 「陪」类字眼出现在正常育儿问题中，不应触发高危拦截
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "白天要陪着1岁宝宝玩多久比较合适",
                "client_request_id": "v31-anthrop-1",
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        stream = client.post(
            f"{API}/qa/sessions/{created['data']['session_uid']}/stream", headers=headers
        )
        assert "event: blocked" not in stream.text
        assert "event: completed" in stream.text


class TestCopyScanAdmin:
    """后台文案扫描端点。"""

    def test_scan_supplied_texts_blocks(self, client, admin_token):
        """提交含禁用表述的文案 → blocked（阻断发布）。"""
        headers = admin_token("operator")
        resp = client.post(
            f"{API}/admin/copy-scan",
            json={"texts": {"订阅消息模板": "你的 AI 育儿伙伴一直陪着你"}},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["mode"] == "texts"
        assert data["result"]["blocked"] is True
        assert data["result"]["hit_count"] >= 1

    def test_scan_repository_zero_hit_via_api(self, client, admin_token):
        """仓库扫描零命中（门禁自检口径）。"""
        headers = admin_token("operator")
        data = client.post(f"{API}/admin/copy-scan", json={}, headers=headers).json()["data"]
        assert data["mode"] == "repository"
        assert data["result"]["blocked"] is False


class TestPrivacyPledge:
    """隐私承诺产品化（RQ-11）。"""

    def test_pledge_only_lists_implemented(self):
        """承诺只列已实现能力，且每条附可操作跳转（AC-RQ11-1/3）。"""
        data = privacy_service.pledge()
        assert data["items"]
        for item in data["items"]:
            assert item["implemented"] is True
            assert item["action"]["label"]
            assert item["action"]["route"]
            assert item["evidence"]
        assert data["honesty_note"]

    def test_untrained_statement_is_scoped(self):
        """「不用于训练」口径限定为自有模型（供应商条款未确认前不越界承诺）。"""
        data = privacy_service.pledge()
        assert "自有模型" in data["training_statement"]

    def test_audit_lists_all_catalog(self):
        """对照表覆盖全部承诺条目（法务签字前自查）。"""
        audit = privacy_service.audit()
        assert audit["total"] == len(audit["items"])
        assert audit["implemented"] >= 4

    def test_pledge_endpoint(self, client):
        """承诺页公开可读（首启流程需要，不阻塞登录前展示）。"""
        resp = client.get(f"{API}/compliance/privacy-pledge")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["version"]
        assert data["items"]

    def test_copy_checklist_endpoint(self, client):
        """检查清单与禁用词表可下发（发布流程勾选用）。"""
        data = client.get(f"{API}/compliance/copy-checklist").json()["data"]
        assert len(data["checklist"]) == 5
        assert data["forbidden_phrases"]
        assert data["replacements"]

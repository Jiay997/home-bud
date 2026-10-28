# -*- coding: utf-8 -*-
"""V3.1 RQ-01 AI 生成标识全链路测试（E2E-20 口径）。

三条链路逐条断言：

1. **页面固定位**：`GET /compliance/ai-label` 下发 `visible / text_id / position`；
2. **长图显式标识**：服务端渲染长图面积占比 ≥15%、出现 ≥2 处；
3. **导出文件隐式标识**：PNG `tEXt` 含 `software / ai_generated / content_type /
   generated_at / render_id`，且**可程序化校验**；剔除元数据后校验必然失败
   （fail-closed，不做「纯净版」）。
"""
import base64
import io

import pytest
from PIL import Image

from app.compliance import ai_label as labels
from app.services import png_meta, report_image

API = "/api/v1"


def _png_bytes(size=(120, 80), color=(200, 210, 205)) -> bytes:
    """生成一张测试 PNG（模拟客户端 canvas 导出产物）。

    Args:
        size: 尺寸。
        color: 填充色。

    Returns:
        PNG 字节。
    """
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# 链路 1：页面固定位契约
# ---------------------------------------------------------------------------
class TestPageFixedLabel:
    """页面标识契约（AC-RQ01-1）。"""

    def test_ai_label_endpoint(self, client):
        """标识组件由服务端下发，前端只渲染 text_id。"""
        resp = client.get(f"{API}/compliance/ai-label", params={"page": "answer"})
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["visible"] is True
        assert data["text_id"] == labels.AI_LABEL_TEXT_ID
        assert data["position"] == labels.POSITION_TOP
        assert data["fallback_text"]
        assert data["min_ratio"] == 0.15
        assert data["min_count"] == 2

    def test_blocked_frame_carries_label(self, client, user_token):
        """拦截页同样带标识（RQ-01 覆盖拦截页）。"""
        headers, _ = user_token("dev-v31-label-blocked")
        resp = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "孩子误食了布洛芬，该给他吃多少剂量",
                "client_request_id": "v31-label-blocked-1",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        session_uid = resp.json()["data"]["session_uid"]
        stream = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
        assert 'event: blocked' in stream.text
        assert labels.AI_LABEL_TEXT_ID in stream.text


# ---------------------------------------------------------------------------
# 链路 2 + 3：长图显式标识 / PNG 隐式标识
# ---------------------------------------------------------------------------
class TestPngMetadata:
    """PNG tEXt 隐式标识读写（纯标准库实现）。"""

    def test_embed_and_read_roundtrip(self):
        """写入后可程序化读出全部必需键。"""
        png = _png_bytes()
        meta = labels.png_metadata(
            content_type=labels.CONTENT_TYPE_SHARE,
            render_id="rnd_test_1",
            generated_at="2026-10-20T00:00:00Z",
        )
        out = png_meta.embed_text_metadata(png, meta)
        ok, readback, missing = png_meta.verify_ai_metadata(
            out, labels.required_png_keys()
        )
        assert ok is True, missing
        assert readback["software"] == labels.PNG_SOFTWARE
        assert readback["ai_generated"] == "1"
        assert readback["render_id"] == "rnd_test_1"

    def test_strip_metadata_fails_closure(self):
        """剔除元数据后校验必然失败（不存在「纯净版」通过路径）。"""
        png = _png_bytes()
        meta = labels.png_metadata("share_card", "rnd_test_2", "2026-10-20T00:00:00Z")
        out = png_meta.embed_text_metadata(png, meta)
        stripped = png_meta.strip_text_metadata(out)
        ok, _, missing = png_meta.verify_ai_metadata(stripped, labels.required_png_keys())
        assert ok is False
        assert "software" in missing

    def test_embed_is_idempotent(self):
        """重复写入同名键不产生重复 chunk，值与首次一致。"""
        png = _png_bytes()
        meta = labels.png_metadata("share_card", "rnd_fix", "2026-10-20T00:00:00Z")
        once = png_meta.embed_text_metadata(png, meta)
        twice = png_meta.embed_text_metadata(once, meta)
        assert once == twice

    def test_reject_non_png(self):
        """非 PNG 输入拒绝写入（不允许伪造标识）。"""
        with pytest.raises(png_meta.PngMetadataError):
            png_meta.embed_text_metadata(b"not-a-png", {"software": "x"})


class TestLongImageRender:
    """服务端长图渲染的标识合规断言。"""

    def test_render_asserts_ratio_and_count(self):
        """显式标识面积 ≥15% 且 ≥2 处，隐式标识回读通过。"""
        png, meta = report_image.render_report_long_image(
            report_uid="rpt_unit_1",
            title="气质测评报告",
            sections=[
                {"title": "气质画像", "content": "活动量中等，节律性较好。" * 12},
                {"title": "养育建议", "content": "建立稳定作息，观察两周。" * 8},
            ],
            trust_items=["内容由 AI 生成", "适用：1–3 岁"],
            subtitle="Babe宝伴 · 养育科普参考工具",
        )
        assert meta["ratio"] >= labels.LONG_IMAGE_LABEL_MIN_RATIO
        assert meta["count"] >= labels.LONG_IMAGE_LABEL_MIN_COUNT
        assert png_meta.is_png(png)
        readback = png_meta.read_text_metadata(png)
        for key in labels.required_png_keys():
            assert readback.get(key), key
        assert readback["content_type"] == labels.CONTENT_TYPE_REPORT

    def test_label_check_fails_below_threshold(self):
        """标识校验器对不达标输入判失败（不静默放行）。"""
        check = labels.label_check_result(0.10, 1, {}, metadata_ok=False)
        assert check["passed"] is False
        assert len(check["errors"]) == 3


class TestComplianceEndpoints:
    """合规相关 HTTP 端点。"""

    def test_png_metadata_endpoint(self, client, user_token):
        """客户端 PNG 上传后返回带隐式标识的 PNG（导出文件链路）。"""
        headers, _ = user_token("dev-v31-png")
        resp = client.post(
            f"{API}/compliance/png-metadata",
            files={"file": ("share.png", _png_bytes(), "image/png")},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["label_check"]["passed"] is True
        png = base64.b64decode(data["png_base64"])
        readback = png_meta.read_text_metadata(png)
        assert readback["ai_generated"] == "1"
        assert readback["software"] == labels.PNG_SOFTWARE

    def test_png_metadata_rejects_non_png(self, client, user_token):
        """非 PNG 上传 → 1001。"""
        headers, _ = user_token("dev-v31-png-bad")
        resp = client.post(
            f"{API}/compliance/png-metadata",
            files={"file": ("share.txt", b"plain text", "text/plain")},
            headers=headers,
        )
        assert resp.json()["code"] == 1001

    def test_ai_label_three_link_selfcheck(self, client, user_token):
        """三链路自检全部通过（E2E-20 辅助断言）。"""
        headers, _ = user_token("dev-v31-label-check")
        resp = client.get(f"{API}/compliance/ai-label/check", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["passed"] is True, data
        assert len(data["links"]) == 3

    def test_share_card_png_headers_and_metadata(self, client, user_token):
        """问答分享长图返回 PNG，响应头与 tEXt 元数据齐备（RQ-09）。"""
        headers, _ = user_token("dev-v31-share")
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "1岁宝宝辅食添加顺序",
                "client_request_id": "v31-share-1",
            },
            headers=headers,
        ).json()
        assert created["code"] == 0, created
        session_uid = created["data"]["session_uid"]
        client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
        resp = client.get(
            f"{API}/qa/sessions/{session_uid}/share-card.png", headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "image/png"
        assert resp.headers["X-AI-Generated"] == "1"
        assert resp.headers["X-Share-Trace-Id"]
        readback = png_meta.read_text_metadata(resp.content)
        assert readback["ai_generated"] == "1"
        assert readback["content_type"] == labels.CONTENT_TYPE_QA

    def test_share_card_blocked_session_403(self, client, user_token):
        """被拦截会话不可分享（服务端 403，AC-RQ09-2）。"""
        headers, _ = user_token("dev-v31-share-blocked")
        created = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "孩子被虐待儿童怎么办",
                "client_request_id": "v31-share-blocked-1",
            },
            headers=headers,
        ).json()
        session_uid = created["data"]["session_uid"]
        client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
        resp = client.get(
            f"{API}/qa/sessions/{session_uid}/share-card.png", headers=headers
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1102

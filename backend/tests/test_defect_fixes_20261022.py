# -*- coding: utf-8 -*-
"""2026-10-22 测试报告缺陷修复回归用例。

覆盖：
- D-02：儿童档案未来出生日期拒绝（新建 + 更新）；
- D-03：少于 5 字的问题拒绝；
- D-05：宠物急症回答强制就医提示与执业兽医免责声明。

说明：D-01（H5 媒体 URL）由 client/tests/media-url.test.mjs 覆盖；
D-04（并发幂等）由 API 并发脚本与串行幂等回归覆盖；
D-06/D-07/D-08 为前端/部署脚本修复，分别由前端测试、init_db 冒烟与浏览器控制台验证。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import parse_sse  # noqa: E402

API = "/api/v1"


def _agree_child(client, headers) -> None:
    """完成儿童信息单独同意。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
    """
    resp = client.post(
        f"{API}/consent/agree",
        json={"consent_type": "child_personal_info", "consent_version": "1.0.0"},
        headers=headers,
    )
    assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text


def test_future_birth_date_is_rejected_on_create_and_update(client, user_token):
    """未来出生日期在新建与更新时均返回 1001/422。"""
    headers, _ = user_token("fix-d02")
    _agree_child(client, headers)

    future = (date.today() + timedelta(days=1)).isoformat()
    rejected = client.post(
        f"{API}/profiles/children",
        json={"nickname": "未来宝宝", "birth_date": future},
        headers=headers,
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == 1001

    created = client.post(
        f"{API}/profiles/children",
        json={"nickname": "正常宝宝", "birth_date": "2024-06-15"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    profile = created.json()["data"]

    updated = client.put(
        f"{API}/profiles/children/{profile['profile_uid']}",
        json={"version": profile["version"], "birth_date": future},
        headers=headers,
    )
    assert updated.status_code == 422, updated.text
    assert updated.json()["code"] == 1001


def test_short_question_is_rejected(client, user_token):
    """少于 5 字的问题在服务端直接拒绝。"""
    headers, _ = user_token("fix-d03")
    resp = client.post(
        f"{API}/qa/sessions",
        json={
            "entry": "child",
            "question": "宝宝",
            "client_request_id": "fix-d03-short",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == 1001


def test_pet_emergency_has_urgent_notice_and_disclaimer(client, user_token):
    """宠物误食急症必须前置就医提示，并带执业兽医免责声明。"""
    headers, _ = user_token("fix-d05")
    created = client.post(
        f"{API}/qa/sessions",
        json={
            "entry": "pet",
            "question": "狗狗误食巧克力怎么办",
            "client_request_id": "fix-d05-pet",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    session_uid = created.json()["data"]["session_uid"]

    streamed = client.post(
        f"{API}/qa/sessions/{session_uid}/stream", headers=headers
    )
    assert streamed.status_code == 200, streamed.text
    frames = parse_sse(streamed.text)
    pet_sections = [
        data
        for event, data in frames
        if event == "section_done" and data.get("section_key") == "pet"
    ]
    assert pet_sections, frames

    blocks = pet_sections[-1].get("blocks") or []
    text = "\n".join(str(block.get("content") or "") for block in blocks)
    assert "尽快前往宠物医院" in text, text
    assert "执业兽医" in text, text

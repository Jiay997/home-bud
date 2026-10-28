# -*- coding: utf-8 -*-
"""每日一则小知识 / 科普全书接口测试。

覆盖：
- 同一天重复请求返回同一条（稳定）；
- 连续一个完整轮换周期内不重复（每日内容尽量不重复）；
- 分类筛选与分类计数；
- 知识库为空时的降级契约（entry=null，客户端据此展示内置提示）；
- 未同意 / 非法参数的错误码。
"""
from datetime import date, timedelta

from app.db import get_session_factory
from app.models import KbEntry
from app.services.knowledge_service import TOPIC_PREFIX


def _daily(client, headers, day: str):
    """请求指定日期的每日小知识。

    Args:
        client: TestClient。
        headers: 鉴权头。
        day: YYYY-MM-DD 日期字符串。

    Returns:
        响应 data 字典。

    Raises:
        AssertionError: HTTP 或包络 code 非成功。
    """
    resp = client.get(f"/api/v1/knowledge/daily?date={day}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def test_daily_is_stable_within_same_day(client, user_token):
    """同一天重复请求必须返回同一条知识。"""
    headers, _ = user_token()
    first = _daily(client, headers, "2026-10-22")
    second = _daily(client, headers, "2026-10-22")
    assert first["date"] == "2026-10-22"
    assert first["entry"] is not None
    assert first["entry"]["kb_id"] == second["entry"]["kb_id"]


def test_daily_cycles_without_repeat(client, user_token):
    """连续 N 天应覆盖全部条目且不重复（N=知识库条目数）。"""
    headers, _ = user_token()
    start = date(2026, 1, 1)
    first = _daily(client, headers, start.isoformat())
    total = first["total"]
    assert total >= 20

    seen = []
    for offset in range(total):
        day = (start + timedelta(days=offset)).isoformat()
        seen.append(_daily(client, headers, day)["entry"]["kb_id"])
    assert len(set(seen)) == total
    assert all(seen[index] != seen[index - 1] for index in range(1, total))


def test_entries_are_grouped_by_business_category(client, user_token):
    """科普全书条目应按母婴 / 幼儿 / 宠物 / 家庭共处分类并可筛选。"""
    headers, _ = user_token()
    resp = client.get("/api/v1/knowledge/entries", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    counts = {item["code"]: item["count"] for item in data["categories"]}
    assert counts == {"infant": 6, "toddler": 6, "pet": 6, "family": 6}
    assert data["total"] == 24
    assert all(item["source_name"] for item in data["items"])

    pet_resp = client.get("/api/v1/knowledge/entries?category=pet", headers=headers)
    assert pet_resp.status_code == 200, pet_resp.text
    pet_items = pet_resp.json()["data"]["items"]
    assert len(pet_items) == 6
    assert all(item["category"] == "pet" for item in pet_items)


def test_empty_knowledge_base_returns_null_entry(client, user_token):
    """知识库清空后应返回 entry=null，让客户端走降级展示而不是报错。"""
    headers, _ = user_token()
    db = get_session_factory()()
    try:
        db.query(KbEntry).filter(KbEntry.topic_key.like(f"{TOPIC_PREFIX}%")).update(
            {KbEntry.status: "unpublished"}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

    data = _daily(client, headers, "2026-10-22")
    assert data["entry"] is None
    assert data["total"] == 0

    resp = client.get("/api/v1/knowledge/entries", headers=headers)
    assert resp.status_code == 200, resp.text
    empty = resp.json()["data"]
    assert empty["items"] == []
    assert all(item["count"] == 0 for item in empty["categories"])


def test_invalid_date_and_category_rejected(client, user_token):
    """非法日期与非法分类应返回 1001。"""
    headers, _ = user_token()
    bad_date = client.get("/api/v1/knowledge/daily?date=2026-13-40", headers=headers)
    assert bad_date.status_code == 422
    assert bad_date.json()["code"] == 1001

    bad_category = client.get("/api/v1/knowledge/entries?category=unknown", headers=headers)
    assert bad_category.status_code == 422
    assert bad_category.json()["code"] == 1001


def test_knowledge_requires_base_consent(client, user_token):
    """未完成基础同意时接口应返回 1301。"""
    headers, _ = user_token(agree=False)
    resp = client.get("/api/v1/knowledge/daily", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == 1301

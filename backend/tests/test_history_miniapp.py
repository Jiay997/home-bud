from datetime import datetime
from zoneinfo import ZoneInfo

from test_api_integration import API, SAFE_QUESTION, _create_qa_session, _run_stream


def test_history_exposes_relationship_entry_and_seven_day_summary(client, user_token):
    headers, _ = user_token("history-miniapp")
    _, qa = _create_qa_session(
        client, headers, SAFE_QUESTION, "history-miniapp-pet", entry="pet"
    )
    _run_stream(client, headers, qa["session_uid"])

    history = client.get(f"{API}/history", headers=headers).json()["data"]
    assert history["items"][0]["item_type"] == "qa"
    assert history["items"][0]["profile_type"] == "pet"
    assert history["items"][0]["entry"] == "pet"

    summary = client.get(f"{API}/history/summary?days=7", headers=headers).json()["data"]
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    assert len(summary["days"]) == 7
    assert summary["days"][-1] == {"date": today, "count": 1}
    assert summary["qa_records"] == {"child": 0, "pet": 1, "family": 0}


def test_history_can_filter_records_by_observed_day(client, user_token):
    headers, _ = user_token("history-miniapp-date")
    _, qa = _create_qa_session(
        client, headers, SAFE_QUESTION, "history-miniapp-date-family", entry="family"
    )
    _run_stream(client, headers, qa["session_uid"])
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    response = client.get(f"{API}/history?record_date={today}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["profile_type"] == "family"

    empty_day = client.get(f"{API}/history?record_date=2020-01-01", headers=headers)
    assert empty_day.status_code == 200
    assert empty_day.json()["data"]["items"] == []

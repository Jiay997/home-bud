# -*- coding: utf-8 -*-
"""词库配置版本留痕与一键回滚测试（DEF-18）。

覆盖：
- PUT /admin/lexicon/config/{key}：写 ConfigVersion 全量快照（单活跃版）、
  删 lexicon:snapshot 缓存（1 分钟内生效）、响应即已提交；
- GET /admin/configs/lexicon/history：版本倒序 + 抽屉展示字段
  changed_by/changed_at（前端列 prop 契约对齐）；
- POST /admin/configs/lexicon/rollback：词库专用分支——目标版快照逐键回写
  RiskRuleConfig（行 version 递增）、版本状态复位、缓存失效、审计留痕；
- 权限/凭证兜底：1103（非超管）/1602（缺二次确认，无副作用）/1002（版本不存在）；
- 通用（switch）回滚路径不受 lexicon 分支影响。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.cache import cache  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import AdminAuditLog, RiskRuleConfig  # noqa: E402

API = "/api/v1"
LEX_CFG = f"{API}/admin/lexicon/config"
HISTORY = f"{API}/admin/configs/lexicon/history"
ROLLBACK = f"{API}/admin/configs/lexicon/rollback"
SNAPSHOT_KEY = "lexicon:snapshot"

# 两版阈值（v1 旧值 / v2 新值）
THRESHOLD_V1 = {"gray_low": 0.4, "gray_high": 0.7}
THRESHOLD_V2 = {"gray_low": 0.1, "gray_high": 0.3}


def _put_config(client, headers, key: str, value: dict, reason: str):
    """PUT 词库配置（无二次确认要求，lex:edit 即可）。

    Args:
        client: TestClient。
        headers: 超管鉴权头。
        key: 配置键。
        value: 配置值。
        reason: 变更原因。

    Returns:
        requests.Response。
    """
    return client.put(
        f"{LEX_CFG}/{key}",
        json={"config_value": value, "reason": reason},
        headers=headers,
    )


def _history_items(client, headers) -> list:
    """读取词库配置变更历史列表。

    Args:
        client: TestClient。
        headers: 鉴权头。

    Returns:
        items 列表（版本倒序）。

    Raises:
        AssertionError: 响应非 200 或包络 code 非 0。
    """
    resp = client.get(HISTORY, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]["items"]


def _risk_row(key: str) -> tuple:
    """直读 RiskRuleConfig 行（运行时数据源口径）。

    Args:
        key: 配置键。

    Returns:
        (config_value, version, updated_by)。

    Raises:
        AssertionError: 行不存在。
    """
    db = get_session_factory()()
    try:
        row = db.query(RiskRuleConfig).filter(RiskRuleConfig.config_key == key).first()
        assert row is not None, f"risk config {key} 不存在"
        return dict(row.config_value), int(row.version or 0), row.updated_by
    finally:
        db.close()


def _last_audit(action: str):
    """取最近一条指定 action 的审计行关键字段。

    Args:
        action: 审计动作名。

    Returns:
        dict 或 None（无记录）。
    """
    db = get_session_factory()()
    try:
        row = (
            db.query(AdminAuditLog)
            .filter(AdminAuditLog.action == action)
            .order_by(AdminAuditLog.id.desc())
            .first()
        )
        if row is None:
            return None
        return {
            "object_type": row.object_type,
            "object_id": row.object_id,
            "confirm_used": row.confirm_used,
            "result": row.result,
        }
    finally:
        db.close()


class TestLexiconConfigVersionTrail:
    """保存词库配置 → ConfigVersion 留痕（DEF-18：抽屉不再恒空）。"""

    def test_put_creates_active_version_with_full_snapshot(self, client, admin_token):
        """首次保存 → v1 active；快照全量含各规则键；展示字段齐全。"""
        headers = admin_token("admin")
        resp = _put_config(client, headers, "two_level_threshold", THRESHOLD_V1, "首版阈值")
        assert resp.status_code == 200 and resp.json()["code"] == 0

        items = _history_items(client, headers)
        assert len(items) == 1
        v1 = items[0]
        assert v1["version"] == 1 and v1["status"] == "active"
        assert v1["config_type"] == "lexicon" and v1["config_key"] == "lexicon"
        assert v1["reason"] == "首版阈值"
        assert v1["snapshot"]["two_level_threshold"] == THRESHOLD_V1
        # 全量快照：种子中的其余规则键随版本一并落库（回滚才能完整还原）
        assert "medicine_dosage_pattern" in v1["snapshot"]
        # 抽屉列契约（前端 prop=changed_by/changed_at）
        assert v1["changed_by"]
        assert v1["changed_at"] and v1["changed_at"].startswith("20")

    def test_second_put_keeps_single_active_version(self, client, admin_token):
        """二次保存 → v2 active、v1 rolled_back；快照为最新值。"""
        headers = admin_token("admin")
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V1, "v1")
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V2, "v2")

        items = _history_items(client, headers)
        assert [i["version"] for i in items] == [2, 1]
        assert items[0]["status"] == "active" and items[1]["status"] == "rolled_back"
        assert items[0]["snapshot"]["two_level_threshold"] == THRESHOLD_V2

    def test_put_invalidates_lexicon_snapshot_cache(self, client, admin_token):
        """保存即删 lexicon:snapshot（1 分钟内全量生效语义）。"""
        headers = admin_token("admin")
        cache.set(SNAPSHOT_KEY, "[]", 60)
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V1, "缓存失效")
        assert cache.get(SNAPSHOT_KEY) is None


class TestLexiconConfigRollback:
    """一键回滚 → 数据行回写 + 版本复位 + 缓存失效 + 审计（DEF-18）。"""

    @staticmethod
    def _seed_two_versions(client, headers):
        """造 v1/v2 两版阈值历史。

        Args:
            client: TestClient。
            headers: 超管鉴权头。
        """
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V1, "v1 旧阈值")
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V2, "v2 新阈值")

    def test_rollback_restores_snapshot_and_invalidates_cache(self, client, admin_token):
        """回滚 v2 → v1：RiskRuleConfig 回写旧值 + 行版本递增 + 缓存失效 + 审计。"""
        headers = admin_token("admin")
        self._seed_two_versions(client, headers)
        value_before, version_before, _ = _risk_row("two_level_threshold")
        assert value_before == THRESHOLD_V2
        cache.set(SNAPSHOT_KEY, "[]", 60)

        resp = client.post(
            ROLLBACK,
            json={"target_version": 1, "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["code"] == 0
        assert resp.json()["data"] == {"config_key": "lexicon", "version": 1}

        value_after, version_after, updated_by = _risk_row("two_level_threshold")
        assert value_after == THRESHOLD_V1
        assert version_after == version_before + 1
        assert updated_by is not None
        assert cache.get(SNAPSHOT_KEY) is None

        by_version = {i["version"]: i for i in _history_items(client, headers)}
        assert by_version[1]["status"] == "active"
        assert by_version[1]["rollback_from_version"] == 2
        assert by_version[2]["status"] == "rolled_back"

        audit = _last_audit("config_rollback")
        assert audit is not None
        assert audit["object_type"] == "config_version" and audit["object_id"] == "lexicon"
        assert audit["confirm_used"] is True and audit["result"] == "ok"

    def test_rollback_value_visible_via_lexicon_config_api(self, client, admin_token):
        """回滚后 GET /admin/lexicon/config 读到旧值（运行时数据源口径）。"""
        headers = admin_token("admin")
        self._seed_two_versions(client, headers)
        resp = client.post(
            ROLLBACK,
            json={"target_version": 1, "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert resp.json()["code"] == 0
        items = client.get(LEX_CFG, headers=headers).json()["data"]["items"]
        row = next(i for i in items if i["config_key"] == "two_level_threshold")
        assert row["config_value"] == THRESHOLD_V1

    def test_rollback_missing_version_1002(self, client, admin_token):
        """回滚目标版本不存在 → 1002。"""
        headers = admin_token("admin")
        _put_config(client, headers, "two_level_threshold", THRESHOLD_V1, "仅 v1")
        resp = client.post(
            ROLLBACK,
            json={"target_version": 99, "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == 1002

    def test_rollback_without_confirm_1602_no_side_effect(self, client, admin_token):
        """缺 confirm_token → 1602 且无副作用（仍 v2 active、值仍为新值）。"""
        headers = admin_token("admin")
        self._seed_two_versions(client, headers)
        resp = client.post(ROLLBACK, json={"target_version": 1}, headers=headers)
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1602

        active = [i for i in _history_items(client, headers) if i["status"] == "active"]
        assert [i["version"] for i in active] == [2]
        value, _, _ = _risk_row("two_level_threshold")
        assert value == THRESHOLD_V2

    def test_rollback_support_role_1103(self, client, admin_token):
        """客服回滚（cfg:write 仅超管）→ 1103，先于二次确认校验。"""
        headers = admin_token("admin")
        self._seed_two_versions(client, headers)
        resp = client.post(
            ROLLBACK,
            json={"target_version": 1, "confirm_token": "CONFIRMED"},
            headers=admin_token("support"),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 1103

    def test_switch_rollback_generic_path_unaffected(self, client, admin_token):
        """lexicon 分支不得影响通用 switch 回滚路径（缓存 + 版本号不变量）。"""
        headers = admin_token("admin")
        key = "switch.entry.child"
        # 种子已为入口开关写入 v1，故以返回版本号为基准做相对断言
        r1 = client.put(
            f"{API}/admin/configs/{key}",
            json={"snapshot": {"enabled": False}, "reason": "v-close", "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert r1.json()["code"] == 0
        closed_version = r1.json()["data"]["version"]
        r2 = client.put(
            f"{API}/admin/configs/{key}",
            json={"snapshot": {"enabled": True}, "reason": "v-open", "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert r2.json()["data"]["version"] == closed_version + 1

        rb = client.post(
            f"{API}/admin/configs/{key}/rollback",
            json={"target_version": closed_version, "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert rb.status_code == 200 and rb.json()["code"] == 0
        assert rb.json()["data"]["version"] == closed_version
        assert json.loads(cache.get(f"switch:{key}"))["enabled"] is False

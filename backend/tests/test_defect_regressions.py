# -*- coding: utf-8 -*-
"""缺陷回归用例集：19 项已修复缺陷的自动化回归防线（报告 §8.3 #3）。

对应《测试报告_全面模拟测试_2026-10-09.md》§8.3 回归建议「十个入口」中
后端可断言的部分（登录入口由既有 test_api_integration::TestDevLogin /
test_admin_login_mfa_flow 覆盖，此处不重复）：

- 审核通过（DEF-09）：kb 条目 pass 二次确认发布 / reject 必填理由码；
- 导出（DEF-13）：Agent 日志 CSV（仅超管 + 二次确认）、权利请求导出文件；
- 举报处置（DEF-12）：处置动作落库 + escalate 必附证据 + 回执标记；
- 档案契约（DEF-02/06）：pet_uid 契约、宠物字段对齐、乐观锁、列表键名；
- 词库页读写（DEF-10）：词条 CRUD + 删除二次确认（留痕/回滚另见
  test_lexicon_config_versions.py）；
- 审计入口（DEF-14）：角色白名单 + 快照脱敏（仅键名）；
- 配置提交可见性（DEF-19）：PUT 返回即新版本已提交、单活跃版；
- 失效会话语义（DEF-17）：无效 token 统一 1101（前端「进入」自愈契约）；
- 后台窄屏布局（DEF-16）：.vue 媒体查询静态守护（布局行为见报告 §7.5）；
- 补强：DEF-01（consent 非法类型 1001/422）、DEF-15（商品价格更新）；
- 编排/SSE 边界增厚（评估文档 P1 #6）：断线续发回放、入口维护开关 1406、
  未知 profile_uid 1002、幂等指纹不一致 1001。
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import parse_sse  # noqa: E402

API = "/api/v1"

# 与 test_api_integration 同口径：高危词（种子词库命中）/ 正常问题
RISK_QUESTION = "打孩子打到出血了怎么办"
SAFE_QUESTION = "两岁孩子晚上睡觉不踏实总翻来覆去怎么办"

# 后台管理页源文件目录（DEF-16 静态守护）
ADMIN_VIEWS_DIR = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "admin"
)


def _create_qa_session(client, headers, question, client_request_id, entry="child"):
    """创建问答会话，返回响应 data 字典。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
        question: 问题原文。
        client_request_id: 幂等键。
        entry: 入口（child/pet/family）。

    Returns:
        包络 data 字典。

    Raises:
        AssertionError: 响应非 200 或 code 非 0。
    """
    resp = client.post(
        f"{API}/qa/sessions",
        json={
            "entry": entry,
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
    """执行 SSE 流式问答并解析帧序列。

    Args:
        client: TestClient 夹具。
        headers: 鉴权头。
        session_uid: 会话标识。

    Returns:
        [(event, data), ...] 帧列表。

    Raises:
        AssertionError: 流响应非 200。
    """
    resp = client.post(f"{API}/qa/sessions/{session_uid}/stream", headers=headers)
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


# ---------------------------------------------------------------------------
# DEF-01：consent 非法类型统一 1001/422（修复前 NameError→500）
# ---------------------------------------------------------------------------
class TestDef01ConsentEnvelope:
    """consent 非法类型分支的包络契约（agree/withdraw 两入口）。"""

    def test_invalid_consent_type_enveloped_1001(self, client, user_token):
        """非法 consent_type → HTTP 422 + code 1001（两入口一致）。"""
        headers, _ = user_token()
        for path in ("agree", "withdraw"):
            resp = client.post(
                f"{API}/consent/{path}",
                json={"consent_type": "bogus_type"},
                headers=headers,
            )
            assert resp.status_code == 422, resp.text
            assert resp.json()["code"] == 1001, resp.text


# ---------------------------------------------------------------------------
# DEF-02 / DEF-06：档案对外 uid 契约与列表键名
# ---------------------------------------------------------------------------
class TestDef02ProfileContract:
    """档案契约：uid 归一化、宠物字段对齐、乐观锁与列表键名。"""

    def test_pet_roundtrip_current_by_uid_and_optimistic_lock(self, client, user_token):
        """宠物建档/更新/乐观锁/设为当前，全链路按对外 uid 契约。"""
        headers, _ = user_token()
        body = {
            "pet_type": "cat",
            "breed": "英短",
            "age_band": "adult",
            "neutered_flag": True,
            "weight_kg": 4.2,
            "main_food": "回归测试主粮",
        }
        created = client.post(f"{API}/profiles/pets", json=body, headers=headers)
        assert created.status_code == 200, created.text
        pet = created.json()["data"]
        pet_uid, version = pet["pet_uid"], pet["version"]
        assert pet["age_band"] == "adult" and pet["neutered_flag"] is True
        assert pet["weight_kg"] == 4.2

        listed = client.get(f"{API}/profiles/pets", headers=headers).json()["data"]["pets"]
        assert any(p["pet_uid"] == pet_uid for p in listed)

        # 更新：全量字段 + 乐观锁；age_band 契约字段随写随回
        updated = client.put(
            f"{API}/profiles/pets/{pet_uid}",
            json={**body, "age_band": "senior", "version": version},
            headers=headers,
        )
        assert updated.status_code == 200 and updated.json()["code"] == 0, updated.text
        assert updated.json()["data"]["version"] == version + 1
        assert updated.json()["data"]["age_band"] == "senior"

        stale = client.put(
            f"{API}/profiles/pets/{pet_uid}",
            json={**body, "version": version},
            headers=headers,
        )
        assert stale.status_code == 409 and stale.json()["code"] == 1003

        # 当前问答对象按对外 uid 设置（不再暴露内部主键）
        current = client.post(
            f"{API}/profiles/current",
            json={"profile_type": "pet", "profile_uid": pet_uid},
            headers=headers,
        )
        assert current.status_code == 200 and current.json()["code"] == 0, current.text
        assert current.json()["data"]["profile_uid"] == pet_uid

    def test_current_context_rejects_legacy_key_and_unknown_uid(self, client, user_token):
        """旧内部主键键名不再受理（422）；未知 uid 统一 1002（防枚举）。"""
        headers, _ = user_token()
        legacy = client.post(
            f"{API}/profiles/current",
            json={"profile_type": "pet", "profile_id": 1},
            headers=headers,
        )
        assert legacy.status_code == 422, legacy.text

        unknown = client.post(
            f"{API}/profiles/current",
            json={"profile_type": "pet", "profile_uid": "UID_DOES_NOT_EXIST"},
            headers=headers,
        )
        assert unknown.status_code == 404 and unknown.json()["code"] == 1002

    def test_profile_lists_expose_children_and_pets_keys(self, client, user_token):
        """列表键名契约：children / pets（HomePage hasProfile 依赖，DEF-06）。"""
        headers, _ = user_token()
        children = client.get(f"{API}/profiles/children", headers=headers).json()["data"]
        pets = client.get(f"{API}/profiles/pets", headers=headers).json()["data"]
        assert "children" in children
        assert "pets" in pets


# ---------------------------------------------------------------------------
# DEF-09：知识条目审核
# ---------------------------------------------------------------------------
class TestDef09KbReview:
    """kb 审核：pass 需二次确认并发布新版本；reject 必填理由码。"""

    @staticmethod
    def _pending_entry(client, headers):
        """创建并提交一条待审核条目，返回 kb_id。

        Args:
            client: TestClient 夹具。
            headers: 后台鉴权头（需 kb:edit）。

        Returns:
            kb_id 字符串。

        Raises:
            AssertionError: 创建或送审失败。
        """
        created = client.post(
            f"{API}/admin/kb/entries",
            json={
                "kb_kind": "child",
                "domain": "child",
                "topic_key": "regression_topic",
                "topic_category": "回归测试",
                "title": "回归测试条目",
                "content": "用于缺陷回归的正文内容，仅供测试。",
                "preconditions": "仅测试环境",
                "source_type": "internal",
                "source_ref": "tests/test_defect_regressions.py",
            },
            headers=headers,
        )
        assert created.status_code == 200 and created.json()["code"] == 0, created.text
        kb_id = created.json()["data"]["kb_id"]
        submitted = client.post(
            f"{API}/admin/kb/entries/{kb_id}/submit", headers=headers
        )
        assert submitted.status_code == 200 and submitted.json()["code"] == 0, submitted.text
        return kb_id

    def test_pass_requires_confirm_then_publishes_new_version(self, client, admin_token):
        """缺二次确认 → 1602 无副作用；补确认 → published 且版本 +1。"""
        headers = admin_token("operator")
        kb_id = self._pending_entry(client, headers)

        no_confirm = client.post(
            f"{API}/admin/kb/entries/{kb_id}/review",
            json={"verdict": "pass", "score": 92},
            headers=headers,
        )
        assert no_confirm.status_code == 403 and no_confirm.json()["code"] == 1602

        published = client.post(
            f"{API}/admin/kb/entries/{kb_id}/review",
            json={"verdict": "pass", "score": 92, "confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert published.status_code == 200 and published.json()["code"] == 0, published.text
        assert published.json()["data"]["status"] == "published"
        assert published.json()["data"]["version"] == 2  # 新建 v1 → 发布 +1

    def test_reject_requires_code_then_marks_rejected(self, client, admin_token):
        """reject 缺理由码 → 1001；带理由码 → rejected。"""
        headers = admin_token("operator")
        kb_id = self._pending_entry(client, headers)

        no_code = client.post(
            f"{API}/admin/kb/entries/{kb_id}/review",
            json={"verdict": "reject"},
            headers=headers,
        )
        assert no_code.status_code == 422 and no_code.json()["code"] == 1001

        rejected = client.post(
            f"{API}/admin/kb/entries/{kb_id}/review",
            json={"verdict": "reject", "reject_code": "not_traceable"},
            headers=headers,
        )
        assert rejected.status_code == 200 and rejected.json()["code"] == 0, rejected.text
        assert rejected.json()["data"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# DEF-10：词条 CRUD 与删除二次确认
# ---------------------------------------------------------------------------
class TestDef10LexiconTermCrud:
    """词库词条读取（解密展示）/新增/更新/删除（二次确认）闭环。"""

    def test_term_crud_and_delete_confirm(self, client, admin_token):
        """CRUD 全链路：缺二次确认 1602 无副作用，补确认后删除生效。"""
        headers = admin_token("operator")
        term_text = "回归测试词条ZQ"
        created = client.post(
            f"{API}/admin/lexicon/terms",
            json={"term": term_text, "lexicon_type": "risk", "strategy": "block"},
            headers=headers,
        )
        assert created.status_code == 200 and created.json()["code"] == 0, created.text
        term_id = created.json()["data"]["id"]

        def term_present():
            """检查词条是否仍在 risk 列表（按明文精确匹配）。"""
            items = client.get(
                f"{API}/admin/lexicon/terms",
                params={"type": "risk", "page_size": 100},
                headers=headers,
            ).json()["data"]["items"]
            return any(t["term"] == term_text for t in items)

        assert term_present()

        updated = client.put(
            f"{API}/admin/lexicon/terms/{term_id}",
            json={"strategy": "rewrite", "effective": False},
            headers=headers,
        )
        assert updated.status_code == 200 and updated.json()["code"] == 0, updated.text

        no_confirm = client.request(
            "DELETE", f"{API}/admin/lexicon/terms/{term_id}", json={}, headers=headers
        )
        assert no_confirm.status_code == 403 and no_confirm.json()["code"] == 1602
        assert term_present()  # 1602 无副作用

        deleted = client.request(
            "DELETE",
            f"{API}/admin/lexicon/terms/{term_id}",
            json={"confirm_token": "CONFIRMED"},
            headers=headers,
        )
        assert deleted.status_code == 200 and deleted.json()["code"] == 0, deleted.text
        assert deleted.json()["data"]["deleted"] is True
        assert not term_present()


# ---------------------------------------------------------------------------
# DEF-12：举报处置
# ---------------------------------------------------------------------------
class TestDef12ReportHandle:
    """举报处置：escalate 必附证据、动作落库与回执标记（涉未成年加急）。"""

    @staticmethod
    def _submit_report(client, headers, suffix):
        """C 端提交一条举报，返回 report_no。

        Args:
            client: TestClient 夹具。
            headers: 用户鉴权头。
            suffix: 对象标识后缀（保证用例内唯一）。

        Returns:
            report_no 字符串。

        Raises:
            AssertionError: 提交失败。
        """
        resp = client.post(
            f"{API}/reports",
            json={
                "object_type": "qa_answer",
                "object_id": f"REG-{suffix}",
                "category": "medical_misleading",
                "description": "回归测试举报",
            },
            headers=headers,
        )
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
        return resp.json()["data"]["report_no"]

    def test_handle_actions_escalate_evidence_and_receipt(
        self, client, user_token, admin_token
    ):
        """缺证据 escalate → 1602；unpublish 落库并回执；附证据 escalate → reported。"""
        user_headers, _ = user_token()
        admin_headers = admin_token("operator")

        report_no = self._submit_report(client, user_headers, "A")
        missing_evidence = client.put(
            f"{API}/admin/reports/{report_no}",
            json={"action": "escalate", "basis": "涉嫌违规需上报"},
            headers=admin_headers,
        )
        assert missing_evidence.status_code == 403
        assert missing_evidence.json()["code"] == 1602

        handled = client.put(
            f"{API}/admin/reports/{report_no}",
            json={"action": "unpublish", "basis": "内容不实已下架"},
            headers=admin_headers,
        )
        assert handled.status_code == 200 and handled.json()["code"] == 0, handled.text
        assert handled.json()["data"]["action"] == "unpublish"

        rows = client.get(
            f"{API}/admin/reports", params={"handled": True}, headers=admin_headers
        ).json()["data"]["items"]
        row = next(r for r in rows if r["report_no"] == report_no)
        assert row["action"] == "unpublish"
        assert row["handled_at"] and row["receipt_sent"] is True

        escalated_no = self._submit_report(client, user_headers, "B")
        escalated = client.put(
            f"{API}/admin/reports/{escalated_no}",
            json={
                "action": "escalate",
                "basis": "上报监管主体",
                "evidence": {
                    "url": "https://example.invalid/evidence",
                    "sha256": "0" * 64,
                },
            },
            headers=admin_headers,
        )
        assert escalated.status_code == 200 and escalated.json()["code"] == 0, escalated.text
        rows2 = client.get(
            f"{API}/admin/reports", params={"handled": True}, headers=admin_headers
        ).json()["data"]["items"]
        row2 = next(r for r in rows2 if r["report_no"] == escalated_no)
        assert row2["reported"] is True


# ---------------------------------------------------------------------------
# DEF-13：导出（Agent 日志 CSV / 权利请求导出文件）
# ---------------------------------------------------------------------------
class TestDef13Exports:
    """导出链路：权限与二次确认、CSV 包络、审计留痕、文件下载。"""

    def test_agent_logs_export_super_only_confirm_and_audit(self, client, admin_token):
        """缺确认 1602 / 非超管 1103 / 超管导出 CSV（BOM+表头）并留痕。"""
        super_headers = admin_token("admin")

        no_confirm = client.get(f"{API}/admin/agent-logs/export", headers=super_headers)
        assert no_confirm.status_code == 403 and no_confirm.json()["code"] == 1602

        operator = client.get(
            f"{API}/admin/agent-logs/export",
            params={"confirm_token": "CONFIRMED"},
            headers=admin_token("operator"),
        )
        assert operator.status_code == 403 and operator.json()["code"] == 1103

        resp = client.get(
            f"{API}/admin/agent-logs/export",
            params={"confirm_token": "CONFIRMED"},
            headers=super_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        assert resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM（Excel 兼容）
        first_line = resp.content.decode("utf-8-sig").splitlines()[0]
        assert first_line.startswith("id,session_id,agent_id")

        audit = client.get(
            f"{API}/admin/audit-logs",
            params={"action": "export", "page_size": 5},
            headers=super_headers,
        ).json()["data"]["items"]
        assert audit and audit[0]["confirm_used"] is True

    def test_rights_export_process_download_and_audit(
        self, client, user_token, admin_token
    ):
        """用户提交导出请求 → 运营生成 CSV → 下载文件 → 审计留痕。"""
        user_headers, _ = user_token()
        admin_headers = admin_token("operator")

        created = client.post(
            f"{API}/rights/requests",
            json={"request_type": "export"},
            headers=user_headers,
        )
        assert created.status_code == 200 and created.json()["code"] == 0, created.text
        request_no = created.json()["data"]["request_no"]

        try:
            processed = client.post(
                f"{API}/admin/rights/{request_no}/process",
                json={"action": "generate_export", "format": "csv"},
                headers=admin_headers,
            )
            assert processed.status_code == 200 and processed.json()["code"] == 0, processed.text
            data = processed.json()["data"]
            assert data["status"] == "exported"
            assert data["export_file_url"].endswith(f"/rights/{request_no}/export-file")

            downloaded = client.get(
                f"{API}/admin/rights/{request_no}/export-file", headers=admin_headers
            )
            assert downloaded.status_code == 200, downloaded.text
            assert downloaded.headers["content-type"].startswith("text/csv")

            audit = client.get(
                f"{API}/admin/audit-logs",
                params={"action": "rights_generate_export"},
                headers=admin_token("admin"),
            ).json()["data"]["items"]
            assert audit, "权利请求导出缺少审计留痕"
        finally:
            # 清理测试导出文件（导出目录由后端私有约定：backend/data/exports）
            export_file = (
                Path(__file__).resolve().parents[1] / "data" / "exports" / f"{request_no}.csv"
            )
            export_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# DEF-14：审计记录入口
# ---------------------------------------------------------------------------
class TestDef14AuditLogsEntry:
    """审计入口：角色白名单（仅 super_admin，越权修复）与快照脱敏（仅键名）。"""

    def test_role_whitelist_and_masked_shape(self, client, admin_token):
        """operator 留痕可被超管按 action 检索；operator/support 读审计 1103；专家 1103。"""
        operator_headers = admin_token("operator")
        created = client.post(
            f"{API}/admin/lexicon/terms",
            json={"term": "审计留痕词ZT", "lexicon_type": "sensitive", "strategy": "degrade"},
            headers=operator_headers,
        )
        assert created.status_code == 200 and created.json()["code"] == 0, created.text

        super_headers = admin_token("admin")
        resp = client.get(
            f"{API}/admin/audit-logs",
            params={"action": "lexicon_add", "page_size": 5},
            headers=super_headers,
        )
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
        items = resp.json()["data"]["items"]
        assert items and items[0]["action"] == "lexicon_add"
        row = items[0]
        assert row["operator_role"] == "operator"
        assert isinstance(row["before_keys"], list) and isinstance(row["after_keys"], list)
        # 脱敏：快照正文不回传，仅键名列表
        assert "before_snapshot" not in row and "after_snapshot" not in row

        # 越权修复：审计记录为超管专属，operator/support 一律 403/1103
        operator_read = client.get(f"{API}/admin/audit-logs", headers=operator_headers)
        assert operator_read.status_code == 403 and operator_read.json()["code"] == 1103

        support = client.get(f"{API}/admin/audit-logs", headers=admin_token("support"))
        assert support.status_code == 403 and support.json()["code"] == 1103

        expert = client.get(f"{API}/admin/audit-logs", headers=admin_token("expert_child"))
        assert expert.status_code == 403 and expert.json()["code"] == 1103


# ---------------------------------------------------------------------------
# DEF-15：商品价格更新
# ---------------------------------------------------------------------------
class TestDef15ProductPrice:
    """价格配置：仅超管 + 二次确认 + 审计 + 列表回显。"""

    def test_price_update_guard_and_visibility(self, client, admin_token):
        """operator 1103 / 缺确认 1602 / 超管成功且列表与审计同步。"""
        super_headers = admin_token("admin")
        items = client.get(f"{API}/admin/products", headers=super_headers).json()["data"]["items"]
        assert items, "商品种子缺失"
        product_code = items[0]["product_code"]
        new_price = items[0]["price_micro"] + 1_000_000

        forbidden = client.put(
            f"{API}/admin/products/{product_code}",
            json={"price_micro": new_price, "confirm_token": "CONFIRMED"},
            headers=admin_token("operator"),
        )
        assert forbidden.status_code == 403 and forbidden.json()["code"] == 1103

        no_confirm = client.put(
            f"{API}/admin/products/{product_code}",
            json={"price_micro": new_price},
            headers=super_headers,
        )
        assert no_confirm.status_code == 403 and no_confirm.json()["code"] == 1602

        updated = client.put(
            f"{API}/admin/products/{product_code}",
            json={
                "price_micro": new_price,
                "reason": "回归测试调价",
                "confirm_token": "CONFIRMED",
            },
            headers=super_headers,
        )
        assert updated.status_code == 200 and updated.json()["code"] == 0, updated.text
        assert updated.json()["data"]["price_micro"] == new_price

        after = client.get(f"{API}/admin/products", headers=super_headers).json()["data"]["items"]
        assert next(i for i in after if i["product_code"] == product_code)["price_micro"] == new_price

        audit = client.get(
            f"{API}/admin/audit-logs",
            params={"action": "product_update"},
            headers=super_headers,
        ).json()["data"]["items"]
        assert audit


# ---------------------------------------------------------------------------
# DEF-16：后台窄屏布局静态守护
# ---------------------------------------------------------------------------
class TestDef16AdminMobileStaticGuard:
    """后台 9 页 + 布局壳的 ≤640px 媒体查询静态守护（布局实测见报告 §7.5）。"""

    FILES = [
        "AdminLayout.vue",
        "KbListPage.vue",
        "FeedbackPage.vue",
        "LexiconPage.vue",
        "AgentLogPage.vue",
        "RiskEventPage.vue",
        "RightsConfigPage.vue",
        "AuditLogPage.vue",
        "MonitorPage.vue",
        "KbEditPage.vue",
    ]

    @pytest.mark.parametrize("filename", FILES)
    def test_mobile_media_query_present(self, filename):
        """防误删：文件保留 ≤640px 移动端媒体查询块。"""
        source = (ADMIN_VIEWS_DIR / filename).read_text(encoding="utf-8")
        assert re.search(r"@media\s*\(max-width:\s*640px\)", source), (
            f"{filename} 缺少 ≤640px 移动端媒体查询（DEF-16 防回潮）"
        )


# ---------------------------------------------------------------------------
# DEF-17：失效会话语义
# ---------------------------------------------------------------------------
class TestDef17StaleSessionSemantics:
    """无效/缺失凭证统一 1101（前端「进入」自愈分支依赖的契约）。"""

    def test_malformed_and_missing_token_return_1101(self, client):
        """伪造 token 与无 header 均返回 401/1101。"""
        malformed = client.get(
            f"{API}/consent/status",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert malformed.status_code == 401 and malformed.json()["code"] == 1101

        missing = client.get(f"{API}/consent/status")
        assert missing.status_code == 401 and missing.json()["code"] == 1101


# ---------------------------------------------------------------------------
# DEF-19：配置提交可见性
# ---------------------------------------------------------------------------
class TestDef19ConfigCommitVisibility:
    """配置更新「响应返回即新版本已提交」：立即读取可见且单活跃版。"""

    def test_update_visible_immediately_and_single_active(self, client, admin_token):
        """PUT 返回后经 /admin/configs 与 history 双路径立即可见新版本。"""
        headers = admin_token("admin")
        key = "switch.entry.child"

        resp = client.put(
            f"{API}/admin/configs/{key}",
            json={
                "snapshot": {"enabled": False},
                "reason": "regression-close",
                "confirm_token": "CONFIRMED",
            },
            headers=headers,
        )
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
        version = resp.json()["data"]["version"]

        latest = client.get(f"{API}/admin/configs", headers=headers).json()["data"]["items"]
        row = next(i for i in latest if i["config_key"] == key)
        assert row["snapshot"]["enabled"] is False
        assert row["version"] == version and row["status"] == "active"

        history = client.get(
            f"{API}/admin/configs/{key}/history", headers=headers
        ).json()["data"]["items"]
        active = [h for h in history if h["status"] == "active"]
        assert len(active) == 1 and active[0]["version"] == version


# ---------------------------------------------------------------------------
# 编排 / SSE 边界增厚（评估文档 P1 #6）
# ---------------------------------------------------------------------------
class TestQaResumeAndOrchestrationEdges:
    """断线续发回放与入口维护开关等编排边界。"""

    def test_resume_stream_replays_sections_and_completed(self, client, user_token):
        """已完成会话经 GET 续发：section_done* → completed，序号单调。"""
        headers, _ = user_token()
        data = _create_qa_session(client, headers, SAFE_QUESTION, "reg-resume-1")
        _run_stream(client, headers, data["session_uid"])

        resp = client.get(
            f"{API}/qa/sessions/{data['session_uid']}/stream", headers=headers
        )
        assert resp.status_code == 200, resp.text
        frames = parse_sse(resp.text)
        events = [e for e, _ in frames]
        assert "section_done" in events and events[-1] == "completed"
        seqs = [d["sequence"] for _, d in frames if d is not None]
        assert seqs == sorted(seqs)

    def test_resume_stream_pending_1004_and_blocked_single_frame(self, client, user_token):
        """未完成会话续发 → 1004；阻断会话续发 → 单 blocked 帧。"""
        headers, _ = user_token()
        data = _create_qa_session(client, headers, SAFE_QUESTION, "reg-resume-2")
        pending = client.get(
            f"{API}/qa/sessions/{data['session_uid']}/stream", headers=headers
        )
        assert pending.status_code == 409 and pending.json()["code"] == 1004

        blocked_headers, _ = user_token("dev-itest-block")
        blocked_data = _create_qa_session(
            client, blocked_headers, RISK_QUESTION, "reg-resume-3"
        )
        _run_stream(client, blocked_headers, blocked_data["session_uid"])
        resumed = client.get(
            f"{API}/qa/sessions/{blocked_data['session_uid']}/stream",
            headers=blocked_headers,
        )
        assert resumed.status_code == 200, resumed.text
        frames = parse_sse(resumed.text)
        assert [e for e, _ in frames] == ["blocked"]

    def test_entry_maintenance_switch_effective_immediately(
        self, client, user_token, admin_token
    ):
        """入口开关关闭后新会话 503/1406（提交可见性），恢复后放行。"""
        admin_headers = admin_token("admin")
        key = "switch.entry.child"
        closed = client.put(
            f"{API}/admin/configs/{key}",
            json={
                "snapshot": {"enabled": False},
                "reason": "regression-close",
                "confirm_token": "CONFIRMED",
            },
            headers=admin_headers,
        )
        assert closed.status_code == 200 and closed.json()["code"] == 0, closed.text

        headers, _ = user_token()
        blocked = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "client_request_id": "reg-switch-1",
            },
            headers=headers,
        )
        assert blocked.status_code == 503 and blocked.json()["code"] == 1406

        reopened = client.put(
            f"{API}/admin/configs/{key}",
            json={
                "snapshot": {"enabled": True},
                "reason": "regression-open",
                "confirm_token": "CONFIRMED",
            },
            headers=admin_headers,
        )
        assert reopened.status_code == 200 and reopened.json()["code"] == 0, reopened.text

        retry = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "client_request_id": "reg-switch-2",
            },
            headers=headers,
        )
        assert retry.status_code == 200 and retry.json()["code"] == 0, retry.text

    def test_unknown_profile_uid_1002_and_fingerprint_mismatch_1001(
        self, client, user_token
    ):
        """未知 profile_uid → 1002；幂等键复用但指纹不同 → 1001。"""
        headers, _ = user_token()
        unknown = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "profile_uid": "UID_NOT_EXIST",
                "client_request_id": "reg-edge-1",
            },
            headers=headers,
        )
        assert unknown.status_code == 404 and unknown.json()["code"] == 1002

        first = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": SAFE_QUESTION,
                "client_request_id": "reg-edge-2",
            },
            headers=headers,
        )
        assert first.status_code == 200 and first.json()["code"] == 0, first.text

        mismatch = client.post(
            f"{API}/qa/sessions",
            json={
                "entry": "child",
                "question": "另一个不同的问题内容",
                "client_request_id": "reg-edge-2",
            },
            headers=headers,
        )
        assert mismatch.status_code == 422 and mismatch.json()["code"] == 1001

# -*- coding: utf-8 -*-
"""健康档案与个人笔记集成测试（甲方需求 2026-10-15）。

覆盖：
- 笔记 CRUD、列表摘要（Markdown 剥离+截断）、keyword 过滤；
- 笔记乐观锁更新（version 递增 / 过期 version 1003）、敏感词前置 1303、
  参数异常 1001、越权与删后读 1002（防枚举）、正文加密落库（v1: 前缀）；
- 健康记录 CRUD、儿童主体同意门禁（1302/撤回后列表与详情停止下发 1002）、
  复查提醒 due_status 全档与边界（overdue/soon 7 天/upcoming/none）；
- 报告文件上传（PDF 原样落盘 / 图片规范化 JPEG）、/media 直出、
  覆盖替换删旧文件、删除记录清理文件、伪 PDF/坏图/超体积 1001、越权 1002。
"""
import io
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.media_store import media_root  # noqa: E402

API = "/api/v1"
FAKE_PDF = b"%PDF-1.4\n% health smoke\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _image_bytes(fmt="JPEG", size=(1600, 900), color=(120, 150, 130)):
    """生成测试图片字节（Pillow 编码）。

    Args:
        fmt: 编码格式（JPEG/PNG/GIF…）。
        size: (宽, 高)。
        color: RGB 颜色。

    Returns:
        图片字节。
    """
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def _agree_all(client, headers):
    """签署 base + child_personal_info 两层同意。

    Args:
        client: TestClient。
        headers: 鉴权头。

    Returns:
        None。
    """
    for ctype in ("base", "child_personal_info"):
        resp = client.post(
            f"{API}/consent/agree", json={"consent_type": ctype}, headers=headers
        )
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text


def _create_child(client, headers, nickname="健康娃"):
    """创建儿童档案（需已同意）并返回 data。

    Args:
        client: TestClient。
        headers: 鉴权头。
        nickname: 昵称。

    Returns:
        档案 data dict（含 profile_uid）。
    """
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": nickname, "birth_date": "2025-06-01"},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


def _create_pet(client, headers, breed="健康猫"):
    """创建宠物档案并返回 data。

    Args:
        client: TestClient。
        headers: 鉴权头。
        breed: 品种描述。

    Returns:
        档案 data dict（含 pet_uid）。
    """
    resp = client.post(
        f"{API}/profiles/pets",
        json={"pet_type": "cat", "age_band": "adult", "breed": breed},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


def _create_record(client, headers, subject_uid, subject_type="pet", **overrides):
    """新建健康记录（JSON 体）并返回 record 视图。

    Args:
        client: TestClient。
        headers: 鉴权头。
        subject_uid: 档案对外标识。
        subject_type: child / pet。
        overrides: 覆盖字段（record_date / title / notes / next_checkup_date 等）。

    Returns:
        详情视图 dict。
    """
    body = {
        "subject_type": subject_type,
        "subject_uid": subject_uid,
        "record_date": "2026-10-01",
        "title": "体检记录",
        "notes": "医生建议观察",
        "next_checkup_date": None,
        "next_checkup_note": None,
    }
    body.update(overrides)
    resp = client.post(f"{API}/health/records", json=body, headers=headers)
    assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
    return resp.json()["data"]["record"]


def _upload_file(client, record_uid, headers, data, name="r.pdf", mime="application/pdf"):
    """报告文件上传封装（POST /health/records/{uid}/file）。

    Args:
        client: TestClient。
        record_uid: 记录对外标识（None 时直接用该字符串作路径）。
        headers: 鉴权头。
        data: 文件字节。
        name: 原始文件名。
        mime: MIME 类型。

    Returns:
        httpx 响应。
    """
    return client.post(
        f"{API}/health/records/{record_uid}/file",
        files={"file": (name, data, mime)},
        headers=headers,
    )


def _file_of(media_url):
    """媒体 URL（/media/...）→ 磁盘文件路径。

    Args:
        media_url: 出参中的 /media 前缀 URL。

    Returns:
        Path 实例。
    """
    assert media_url and media_url.startswith("/media/"), media_url
    return media_root() / media_url[len("/media/"):]


def _rows(model):
    """直查 ORM 行（用于落库密文断言）。

    Args:
        model: ORM 模型类。

    Returns:
        全部未删除行列表。
    """
    from app.db import get_session_factory

    db = get_session_factory()()
    try:
        return db.query(model).all()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 笔记
# ---------------------------------------------------------------------------
class TestNotesCrud:
    """笔记新建/详情/列表摘要/更新/删除与加密落库。"""

    def test_note_roundtrip_excerpt_and_encryption(self, client, user_token):
        """正文 Markdown 加密落库；详情回原文，列表回剥离后的摘要。"""
        from app.models import Note

        headers, _ = user_token("notes-a")
        markdown = (
            "## 进食安排\n\n"
            "- 早：奶 200ml\n"
            "- 午：粥 + 蛋黄\n\n"
            "| 月龄 | 辅食 |\n|---|---|\n| 6 | 米糊 |\n\n"
            "**要点**：一次只加一种新食物，观察三天。\n"
        )
        created = client.post(
            f"{API}/notes", json={"title": "喂养手册", "content": markdown}, headers=headers
        )
        assert created.status_code == 200 and created.json()["code"] == 0, created.text
        note = created.json()["data"]["note"]
        assert note["note_uid"] and note["version"] == 1
        assert note["content"] == markdown

        # 落库为密文（local provider 基线 v1: 前缀），明文不落盘
        row = next(r for r in _rows(Note) if r.note_uid == note["note_uid"])
        assert row.content_enc.startswith("v1:")
        assert "进食安排" not in row.content_enc
        assert row.title == "喂养手册"

        # 详情视图与列表摘要
        detail = client.get(f"{API}/notes/{note['note_uid']}", headers=headers)
        assert detail.json()["data"]["note"]["content"] == markdown
        listed = client.get(f"{API}/notes", headers=headers).json()["data"]["notes"]
        assert len(listed) == 1 and "content" not in listed[0]
        excerpt = listed[0]["excerpt"]
        assert "##" not in excerpt and "**" not in excerpt and "|" not in excerpt
        # 标题行整体剥离：摘要从首个正文行开始，表格压平为空格分隔
        assert excerpt.startswith("早：奶 200ml")
        assert "进食安排" not in excerpt and "月龄 辅食 6 米糊" in excerpt
        assert len(excerpt) <= 61  # 60 + 省略号

    def test_note_update_increments_version_and_stale_1003(self, client, user_token):
        """乐观锁：version 匹配则更新并递增；过期 version 返回 1003(409) 且不改写。"""
        headers, _ = user_token("notes-lock")
        note = client.post(
            f"{API}/notes", json={"title": "睡眠", "content": "睡前一小时"}, headers=headers
        ).json()["data"]["note"]

        ok_update = client.put(
            f"{API}/notes/{note['note_uid']}",
            json={"title": "睡眠", "content": "睡前一小时关灯", "version": 1},
            headers=headers,
        )
        assert ok_update.json()["code"] == 0, ok_update.text
        assert ok_update.json()["data"]["note"]["version"] == 2

        stale = client.put(
            f"{API}/notes/{note['note_uid']}",
            json={"title": "睡眠冲突", "content": "覆盖内容", "version": 1},
            headers=headers,
        )
        assert stale.status_code == 409 and stale.json()["code"] == 1003
        # 冲突未改写
        after = client.get(f"{API}/notes/{note['note_uid']}", headers=headers).json()["data"]["note"]
        assert after["version"] == 2 and after["content"] == "睡前一小时关灯"

    def test_note_sensitive_word_1303(self, client, user_token):
        """新建与更新命中推广词均 1303(403)，原内容保持不变。"""
        headers, _ = user_token("notes-risk")
        note = client.post(
            f"{API}/notes", json={"title": "辅食笔记", "content": "正常内容"}, headers=headers
        ).json()["data"]["note"]

        bad_create = client.post(
            f"{API}/notes",
            json={"title": "引流", "content": "加微信详聊"},
            headers=headers,
        )
        assert bad_create.status_code == 403 and bad_create.json()["code"] == 1303

        bad_update = client.put(
            f"{API}/notes/{note['note_uid']}",
            json={"title": "辅食笔记", "content": "扫码进群", "version": 1},
            headers=headers,
        )
        assert bad_update.status_code == 403 and bad_update.json()["code"] == 1303
        kept = client.get(f"{API}/notes/{note['note_uid']}", headers=headers).json()["data"]["note"]
        assert kept["content"] == "正常内容" and kept["version"] == 1
        # 违规新建未落库
        assert len(client.get(f"{API}/notes", headers=headers).json()["data"]["notes"]) == 1

    def test_note_cross_user_deleted_and_bad_params(self, client, user_token):
        """越权/删后读/未知 uid 统一 1002；标题与正文非法参数 1001。"""
        headers_a, _ = user_token("notes-owner")
        headers_b, _ = user_token("notes-other")
        note = client.post(
            f"{API}/notes", json={"title": "私人手册", "content": "内容"}, headers=headers_a
        ).json()["data"]["note"]

        for resp in (
            client.get(f"{API}/notes/{note['note_uid']}", headers=headers_b),
            client.put(
                f"{API}/notes/{note['note_uid']}",
                json={"title": "改", "content": "改", "version": 1},
                headers=headers_b,
            ),
            client.delete(f"{API}/notes/{note['note_uid']}", headers=headers_b),
            client.get(f"{API}/notes/no-such-note", headers=headers_b),
        ):
            assert resp.status_code == 404 and resp.json()["code"] == 1002, resp.text
        # 他人列表不含本人笔记
        assert client.get(f"{API}/notes", headers=headers_b).json()["data"]["notes"] == []

        deleted = client.delete(f"{API}/notes/{note['note_uid']}", headers=headers_a)
        assert deleted.json()["code"] == 0
        gone = client.get(f"{API}/notes/{note['note_uid']}", headers=headers_a)
        assert gone.status_code == 404 and gone.json()["code"] == 1002
        assert client.get(f"{API}/notes", headers=headers_a).json()["data"]["notes"] == []
        # 软删后重复删除同样 1002
        again = client.delete(f"{API}/notes/{note['note_uid']}", headers=headers_a)
        assert again.status_code == 404 and again.json()["code"] == 1002

        for body in (
            {"title": "", "content": "x"},
            {"title": "标" * 61, "content": "x"},
            {"title": "标题", "content": ""},
        ):
            resp = client.post(f"{API}/notes", json=body, headers=headers_a)
            assert resp.status_code == 422 and resp.json()["code"] == 1001, resp.text

    def test_note_list_keyword_filter(self, client, user_token):
        """keyword 按标题过滤，按更新时间倒序返回。"""
        headers, _ = user_token("notes-list")
        for title in ("猫应激记录", "如厕训练", "猫砂盆选购"):
            assert client.post(
                f"{API}/notes", json={"title": title, "content": "正文"}, headers=headers
            ).json()["code"] == 0
        filtered = client.get(f"{API}/notes", params={"keyword": "猫"}, headers=headers)
        titles = [n["title"] for n in filtered.json()["data"]["notes"]]
        assert len(titles) == 2 and "如厕训练" not in titles


# ---------------------------------------------------------------------------
# 健康记录：CRUD 与复查提醒
# ---------------------------------------------------------------------------
class TestHealthRecords:
    """健康记录新建/详情/更新、due_status 档位与加密落库。"""

    def test_pet_record_roundtrip_and_encryption(self, client, user_token):
        """宠物记录新建→列表轻量视图→详情解密→落库密文→更新→删除。"""
        from app.models import HealthRecord

        headers, _ = user_token("health-pet")
        pet = _create_pet(client, headers)
        record = _create_record(
            client,
            headers,
            pet["pet_uid"],
            title="年度体检",
            record_date="2026-09-20",
            notes="需复查血常规",
            next_checkup_note="血常规 + 生化",
        )
        assert record["record_uid"] and record["subject_type"] == "pet"
        assert record["notes"] == "需复查血常规"
        assert record["next_checkup_note"] == "血常规 + 生化"
        assert record["has_file"] is False and record["file_url"] is None

        row = next(r for r in _rows(HealthRecord) if r.record_uid == record["record_uid"])
        assert row.notes_enc.startswith("v1:") and "需复查血常规" not in row.notes_enc
        assert row.next_checkup_note_enc.startswith("v1:")

        # 列表视图不含加密正文
        listed = client.get(f"{API}/health/records", headers=headers).json()["data"]
        assert len(listed["records"]) == 1
        assert "notes" not in listed["records"][0]
        assert listed["records"][0]["title"] == "年度体检"

        # 更新（全量替换语义）：未提供的字段一并清空
        updated = client.put(
            f"{API}/health/records/{record['record_uid']}",
            json={"record_date": "2026-09-21", "title": "年度体检（补）", "notes": None},
            headers=headers,
        )
        assert updated.json()["code"] == 0, updated.text
        view = updated.json()["data"]["record"]
        assert view["title"] == "年度体检（补）" and view["notes"] is None
        assert view["next_checkup_date"] is None and view["next_checkup_note"] is None
        assert view["due_status"] == "none"

        # 重新排期：due_status 翻转为 upcoming
        today = date.fromisoformat(
            client.get(f"{API}/health/records", headers=headers).json()["data"]["today"]
        )
        replanned = client.put(
            f"{API}/health/records/{record['record_uid']}",
            json={
                "record_date": "2026-09-21",
                "title": "年度体检（补）",
                "next_checkup_date": (today + timedelta(days=30)).isoformat(),
                "next_checkup_note": "血常规 + 生化",
            },
            headers=headers,
        ).json()["data"]["record"]
        assert replanned["due_status"] == "upcoming"
        assert replanned["next_checkup_note"] == "血常规 + 生化"

        deleted = client.delete(f"{API}/health/records/{record['record_uid']}", headers=headers)
        assert deleted.json()["code"] == 0 and deleted.json()["data"]["deleted"] is True
        assert client.get(f"{API}/health/records", headers=headers).json()["data"]["records"] == []
        gone = client.get(f"{API}/health/records/{record['record_uid']}", headers=headers)
        assert gone.status_code == 404 and gone.json()["code"] == 1002

    def test_due_status_buckets_and_boundaries(self, client, user_token):
        """due_status：过期 overdue、第 0/7 天 soon、第 8 天起 upcoming、无日期 none。"""
        headers, _ = user_token("health-due")
        pet = _create_pet(client, headers)
        base = client.get(f"{API}/health/records", headers=headers).json()["data"]
        today = date.fromisoformat(base["today"])
        assert base["records"] == []

        cases = {
            "overdue": today - timedelta(days=1),
            "soon_today": today,
            "soon_edge": today + timedelta(days=7),
            "upcoming": today + timedelta(days=8),
        }
        uids = {}
        for key, day in cases.items():
            rec = _create_record(
                client,
                headers,
                pet["pet_uid"],
                title=key,
                record_date="2026-09-01",
                next_checkup_date=day.isoformat(),
            )
            uids[key] = rec["record_uid"]
            assert rec["due_status"] == ("soon" if key.startswith("soon") else key)
        none_rec = _create_record(
            client, headers, pet["pet_uid"], title="none", record_date="2026-09-02"
        )
        assert none_rec["due_status"] == "none"

        statuses = {
            r["record_uid"]: r["due_status"]
            for r in client.get(f"{API}/health/records", headers=headers).json()["data"]["records"]
        }
        assert statuses[uids["overdue"]] == "overdue"
        assert statuses[uids["soon_today"]] == "soon"
        assert statuses[uids["soon_edge"]] == "soon"
        assert statuses[uids["upcoming"]] == "upcoming"
        assert statuses[none_rec["record_uid"]] == "none"

        # 改期即翻转提醒档位（把过期改到远期）
        client.put(
            f"{API}/health/records/{uids['overdue']}",
            json={
                "record_date": "2026-09-01",
                "title": "overdue",
                "next_checkup_date": (today + timedelta(days=60)).isoformat(),
            },
            headers=headers,
        )
        moved = client.get(f"{API}/health/records", headers=headers).json()["data"]["records"]
        assert next(r for r in moved if r["record_uid"] == uids["overdue"])["due_status"] == "upcoming"

    def test_record_subject_filter_and_list_order(self, client, user_token):
        """subject_type / subject_uid 过滤生效，列表按体检日期倒序。"""
        headers, _ = user_token("health-filter")
        _agree_all(client, headers)
        child = _create_child(client, headers)
        pet = _create_pet(client, headers, breed="过滤猫")
        _create_record(client, headers, child["profile_uid"], subject_type="child",
                       title="儿保", record_date="2026-08-01")
        _create_record(client, headers, pet["pet_uid"], title="疫苗", record_date="2026-10-10")
        _create_record(client, headers, pet["pet_uid"], title="驱虫", record_date="2026-09-10")

        all_rows = client.get(f"{API}/health/records", headers=headers).json()["data"]["records"]
        assert [r["title"] for r in all_rows] == ["疫苗", "驱虫", "儿保"]
        pets = client.get(
            f"{API}/health/records", params={"subject_type": "pet"}, headers=headers
        ).json()["data"]["records"]
        assert len(pets) == 2 and {r["subject_uid"] for r in pets} == {pet["pet_uid"]}
        one = client.get(
            f"{API}/health/records", params={"subject_uid": child["profile_uid"]}, headers=headers
        ).json()["data"]["records"]
        assert [r["title"] for r in one] == ["儿保"]

    def test_record_bad_params_and_cross_user_1002(self, client, user_token):
        """坏主体类型/未知档案/超长度字段按 1001、1002 拦截；越权读写统一 1002。"""
        headers_a, _ = user_token("health-owner")
        headers_b, _ = user_token("health-other")
        pet = _create_pet(client, headers_a)
        record = _create_record(client, headers_a, pet["pet_uid"], title="越权基准")

        bad_type = client.post(
            f"{API}/health/records",
            json={
                "subject_type": "dog",
                "subject_uid": pet["pet_uid"],
                "record_date": "2026-10-01",
                "title": "非法主体",
            },
            headers=headers_a,
        )
        assert bad_type.status_code == 422 and bad_type.json()["code"] == 1001
        unknown = client.post(
            f"{API}/health/records",
            json={
                "subject_type": "pet",
                "subject_uid": "no-such-uid",
                "record_date": "2026-10-01",
                "title": "未知档案",
            },
            headers=headers_a,
        )
        assert unknown.status_code == 404 and unknown.json()["code"] == 1002
        oversized = client.post(
            f"{API}/health/records",
            json={
                "subject_type": "pet",
                "subject_uid": pet["pet_uid"],
                "record_date": "2026-10-01",
                "title": "长" * 65,
            },
            headers=headers_a,
        )
        assert oversized.status_code == 422 and oversized.json()["code"] == 1001

        path = f"{API}/health/records/{record['record_uid']}"
        assert client.get(path, headers=headers_b).json()["code"] == 1002
        assert client.put(
            path, json={"record_date": "2026-10-01", "title": "改"}, headers=headers_b
        ).json()["code"] == 1002
        assert _upload_file(client, record["record_uid"], headers_b, FAKE_PDF).json()["code"] == 1002
        assert client.delete(path, headers=headers_b).json()["code"] == 1002
        assert client.get(f"{API}/health/records/no-such", headers=headers_a).json()["code"] == 1002
        # 他人列表看不到本人记录，本人记录未受影响
        assert client.get(f"{API}/health/records", headers=headers_b).json()["data"]["records"] == []
        assert client.get(path, headers=headers_a).json()["code"] == 0


# ---------------------------------------------------------------------------
# 健康记录：报告文件
# ---------------------------------------------------------------------------
class TestHealthReportFiles:
    """PDF/图片上传、静态直出、覆盖替换与删除清理。"""

    def test_pdf_upload_served_and_replaced_by_image(self, client, user_token):
        """PDF 原样落盘并可经 /media 直出；改传图片后规范化 JPEG、旧 PDF 删除。"""
        headers, _ = user_token("health-file")
        pet = _create_pet(client, headers, breed="报告猫")
        record = _create_record(client, headers, pet["pet_uid"], title="体检报告")

        resp = _upload_file(client, record["record_uid"], headers, FAKE_PDF)
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
        data = resp.json()["data"]
        assert data["file_name"] == "r.pdf" and data["file_size"] == len(FAKE_PDF)
        pdf_file = _file_of(data["file_url"])
        assert pdf_file.is_file() and pdf_file.read_bytes() == FAKE_PDF

        served = client.get(data["file_url"])
        assert served.status_code == 200 and served.content.startswith(b"%PDF-")

        # 列表视图同步 has_file / file_url
        listed = client.get(f"{API}/health/records", headers=headers).json()["data"]["records"][0]
        assert listed["has_file"] is True and listed["file_url"] == data["file_url"]

        # 覆盖替换：jpg 走图片规范化（长边 1280），旧 PDF 删除
        repl = _upload_file(
            client, record["record_uid"], headers, _image_bytes(size=(2400, 1200)),
            name="scan.jpg", mime="image/jpeg",
        )
        assert repl.json()["code"] == 0, repl.text
        new_url = repl.json()["data"]["file_url"]
        assert new_url != data["file_url"] and not pdf_file.exists()
        jpg_file = _file_of(new_url)
        assert jpg_file.read_bytes()[:2] == b"\xff\xd8"
        served_img = client.get(new_url)
        assert served_img.status_code == 200
        assert served_img.headers["content-type"].startswith("image/jpeg")

        # 删除记录同步清理报告文件
        assert client.delete(
            f"{API}/health/records/{record['record_uid']}", headers=headers
        ).json()["code"] == 0
        assert not jpg_file.exists()


class TestChildHealthConsentGate:
    """儿童主体受同意门禁：未同意 1302，撤回后列表与详情停止下发。"""

    def test_child_record_requires_consent_then_hidden_after_withdraw(
        self, client, user_token
    ):
        """同意后建儿童记录成功；撤回后档案停用→新建与详情 1002、列表不下发、行保留。"""
        from app.models import HealthRecord

        headers, _ = user_token("health-consent")
        _agree_all(client, headers)
        child = _create_child(client, headers, nickname="门禁娃")
        record = _create_record(
            client, headers, child["profile_uid"], subject_type="child", title="儿保复查"
        )

        withdraw = client.post(
            f"{API}/consent/withdraw",
            json={"consent_type": "child_personal_info"},
            headers=headers,
        )
        assert withdraw.json()["code"] == 0
        assert withdraw.json()["data"]["impact"]["child_profiles_disabled"] == 1

        blocked_create = client.post(
            f"{API}/health/records",
            json={
                "subject_type": "child",
                "subject_uid": child["profile_uid"],
                "record_date": "2026-10-05",
                "title": "撤回后新建",
            },
            headers=headers,
        )
        assert blocked_create.status_code == 404 and blocked_create.json()["code"] == 1002
        blocked_detail = client.get(
            f"{API}/health/records/{record['record_uid']}", headers=headers
        )
        assert blocked_detail.status_code == 404 and blocked_detail.json()["code"] == 1002
        assert client.get(f"{API}/health/records", headers=headers).json()["data"]["records"] == []
        # 数据保留（撤回不清理，仅停止展示与使用）
        assert any(r.record_uid == record["record_uid"] for r in _rows(HealthRecord))

    def test_child_record_consent_gate_1302_defense(self, client, user_token):
        """同意行撤回而档案仍 active 时（防御纵深），儿童主体健康记录按 1302 拦截。

        常规撤回会同时停用档案（走 1002 停止展示），此处仅模拟同意行失效，
        验证 _resolve_subject 的 1302 兜底分支确实接线。
        """
        from datetime import datetime, timezone

        from app.db import get_session_factory
        from app.models import ConsentRecord

        headers, _ = user_token("health-no-consent")
        _agree_all(client, headers)
        child = _create_child(client, headers, nickname="兜底娃")

        db = get_session_factory()()
        try:
            db.query(ConsentRecord).filter(
                ConsentRecord.consent_type == "child_personal_info"
            ).update({"withdraw_at": datetime.now(timezone.utc)})
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"{API}/health/records",
            json={
                "subject_type": "child",
                "subject_uid": child["profile_uid"],
                "record_date": "2026-10-01",
                "title": "无同意",
            },
            headers=headers,
        )
        assert resp.status_code == 403 and resp.json()["code"] == 1302, resp.text


# ---------------------------------------------------------------------------
# 报告文件参数校验
# ---------------------------------------------------------------------------
class TestHealthFileValidation:
    """伪 PDF、坏图、超体积、空文件统一 1001，且不产生文件。"""

    def test_invalid_documents_1001(self, client, user_token):
        """扩展名/魔数不符、非图片字节、超 10MB、空文件均 1001(422)。"""
        headers, _ = user_token("health-bad")
        pet = _create_pet(client, headers, breed="校验猫")
        record = _create_record(client, headers, pet["pet_uid"], title="校验记录")

        cases = [
            ("伪装 PDF", b"<html>not a pdf</html>", "fake.pdf", "application/pdf"),
            ("纯文本", b"plain bytes", "notes.txt", "text/plain"),
            ("坏图", b"not-an-image", "a.jpg", "image/jpeg"),
            ("不支持格式", _image_bytes("GIF", (100, 100)), "a.gif", "image/gif"),
            ("超体积", b"%PDF-" + b"\x00" * (10 * 1024 * 1024), "big.pdf", "application/pdf"),
            ("空文件", b"", "empty.pdf", "application/pdf"),
        ]
        for label, data, name, mime in cases:
            resp = _upload_file(client, record["record_uid"], headers, data, name=name, mime=mime)
            assert resp.status_code == 422, f"{label}: {resp.status_code} {resp.text}"
            assert resp.json()["code"] == 1001, f"{label}: {resp.text}"

        # 全部失败后记录仍无附件，且未产生落盘文件
        detail = client.get(
            f"{API}/health/records/{record['record_uid']}", headers=headers
        ).json()["data"]["record"]
        assert detail["has_file"] is False and detail["file_url"] is None
        health_dir = media_root() / "health"
        assert not health_dir.exists() or not list(health_dir.glob("*"))

# -*- coding: utf-8 -*-
"""V1 冒烟：/notes + /health/records（2026-10-15 甲方需求 3/4）。

覆盖：CRUD、加密落库核验（psycopg2 查 v{N}: 前缀）、乐观锁 1003、
敏感词 1303、越权 1002、文件上传 jpg/png/pdf + 非法类型 1001、
复查提醒 due_status 流转（overdue/soon/upcoming）。
"""
import io
import json
import os
import sys
import uuid
from datetime import date, timedelta

import httpx
import psycopg2

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000/api/v1"
DB_DSN = os.environ.get("SMOKE_DSN", "").strip()
if not DB_DSN and os.path.exists("scripts/.smoke_dsn.txt"):
    DB_DSN = open("scripts/.smoke_dsn.txt", encoding="utf-8").read().strip()

results = []


def step(name, ok_flag, detail=""):
    results.append((name, bool(ok_flag), detail))
    print(f"[{'PASS' if ok_flag else 'FAIL'}] {name}" + (f" | {detail}" if detail else ""))


def api(client, method, path, token=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.request(method, f"{BASE}{path}", headers=headers, **kwargs).json()


# ---------- 测试文件字节（Pillow 现场生成，后端图片规范化同样依赖 Pillow） ----------
def tiny_png():
    buf = io.BytesIO()
    _image().new("RGB", (2, 2), (124, 144, 130)).save(buf, format="PNG")
    return buf.getvalue()


def tiny_jpg():
    buf = io.BytesIO()
    _image().new("RGB", (2, 2), (124, 144, 130)).save(buf, format="JPEG")
    return buf.getvalue()


def _image():
    from PIL import Image
    return Image

FAKE_PDF = b"%PDF-1.4\n% smoke test\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


def main():
    with httpx.Client(timeout=30, trust_env=False) as client:
        # 登录（两个独立设备账号用于越权验证）
        r = client.post(f"{BASE}/auth/dev-login", json={"device_id": f"smoke-hn-{uuid.uuid4().hex[:8]}"}).json()
        step("dev-login A", r["code"] == 0, r.get("data", {}).get("user_uid", ""))
        token = r["data"]["access_token"]
        r2 = client.post(f"{BASE}/auth/dev-login", json={"device_id": f"smoke-hn-{uuid.uuid4().hex[:8]}"}).json()
        token_b = r2["data"]["access_token"]

        step("基础同意", api(client, "POST", "/consent/agree", token, json={"consent_type": "base"})["code"] == 0)
        api(client, "POST", "/consent/agree", token, json={"consent_type": "child_personal_info"})

        # 孩子档案（health 记录挂靠）
        r = api(client, "POST", "/profiles/children", token, json={
            "nickname": "冒烟娃", "birth_date": "2025-03-01", "gender": "female",
        })
        step("建档(孩子)", r["code"] == 0, r.get("data", {}).get("profile_uid", ""))
        child_uid = r["data"]["profile_uid"]
        r = api(client, "POST", "/profiles/pets", token, json={
            "pet_type": "cat", "age_band": "adult",
        })
        pet_uid = r["data"]["pet_uid"]
        step("建档(宠物)", r["code"] == 0, pet_uid)

        # ================= 笔记 =================
        md = "## 辅食心得\n\n- **第一口**选强化铁米粉\n- 观察 3 天再引入新食材\n\n| 阶段 | 做法 |\n|---|---|\n| 6m+ | 米粉 |\n"
        r = api(client, "POST", "/notes", token, json={"title": "辅食笔记", "content": md})
        step("笔记新建", r["code"] == 0 and r["data"]["note"]["version"] == 1, r.get("message", ""))
        note_uid = r["data"]["note"]["note_uid"]

        r = api(client, "GET", "/notes", token)
        row = next((x for x in r["data"]["notes"] if x["note_uid"] == note_uid), None)
        step("笔记列表(摘要)", r["code"] == 0 and row and "米粉" in row["excerpt"] and "##" not in row["excerpt"],
             (row or {}).get("excerpt", "")[:30])

        r = api(client, "GET", f"/notes/{note_uid}", token)
        step("笔记详情", r["code"] == 0 and r["data"]["note"]["content"] == md, "")
        step("笔记列表过滤", "米粉" not in json.dumps(api(client, "GET", "/notes?keyword=不存在词", token)["data"], ensure_ascii=False), "")

        r = api(client, "PUT", f"/notes/{note_uid}", token, json={"title": "辅食笔记v2", "content": md + "- 补充：苹果泥\n", "version": 1})
        step("笔记更新(乐观锁)", r["code"] == 0 and r["data"]["note"]["version"] == 2, f"version={r.get('data', {}).get('note', {}).get('version')}")
        r = api(client, "PUT", f"/notes/{note_uid}", token, json={"title": "并发写", "content": "x", "version": 1})
        step("版本冲突(1003)", r["code"] == 1003, f"code={r.get('code')}")

        r = api(client, "POST", "/notes", token, json={"title": "引流", "content": "加微信领资料"})
        step("敏感词(1303)", r["code"] == 1303, f"code={r.get('code')}")

        step("越权读笔记(1002)", api(client, "GET", f"/notes/{note_uid}", token_b)["code"] == 1002)
        step("越权删笔记(1002)", api(client, "DELETE", f"/notes/{note_uid}", token_b)["code"] == 1002)

        step("笔记删除", api(client, "DELETE", f"/notes/{note_uid}", token)["code"] == 0)
        step("删后读(1002)", api(client, "GET", f"/notes/{note_uid}", token)["code"] == 1002)

        # ================= 健康档案 =================
        today = date.today()
        payload = {
            "subject_type": "child", "subject_uid": child_uid,
            "record_date": today.isoformat(), "title": "秋季体检",
            "notes": "血常规正常，医生建议多户外活动",
            "next_checkup_date": (today + timedelta(days=3)).isoformat(),
            "next_checkup_note": "复查视力",
        }
        r = api(client, "POST", "/health/records", token, json=payload)
        step("健康记录新建", r["code"] == 0, r.get("message", ""))
        rec_uid = r["data"]["record"]["record_uid"]
        step("临期提醒(soon)", r["data"]["record"]["due_status"] == "soon", f"due={r['data']['record']['due_status']}")

        r = api(client, "POST", "/health/records", token, json={
            "subject_type": "pet", "subject_uid": pet_uid,
            "record_date": (today - timedelta(days=30)).isoformat(),
            "title": "猫Annual体检",
            "next_checkup_date": (today - timedelta(days=1)).isoformat(),
        })
        rec2_uid = r["data"]["record"]["record_uid"]
        step("过期提醒(overdue)", r["data"]["record"]["due_status"] == "overdue", f"due={r['data']['record']['due_status']}")

        r = api(client, "GET", f"/health/records?subject_type=child&subject_uid={child_uid}", token)
        rows = r["data"]["records"]
        step("记录列表+today", r["code"] == 0 and len(rows) == 1 and r["data"]["today"] == today.isoformat(),
             f"n={len(rows)} today={r.get('data', {}).get('today')}")

        r = api(client, "GET", "/health/records", token)
        due = [x for x in r["data"]["records"] if x["due_status"] in ("overdue", "soon")]
        step("全部列表含提醒", len(due) == 2, f"due={len(due)}")

        # 文件上传：jpg/png/pdf + 非法类型
        for name, data, ctype in [
            ("report.jpg", tiny_jpg(), "image/jpeg"),
            ("report.png", tiny_png(), "image/png"),
            ("report.pdf", FAKE_PDF, "application/pdf"),
        ]:
            r = api(client, "POST", f"/health/records/{rec_uid}/file", token,
                    files={"file": (name, io.BytesIO(data), ctype)})
            step(f"上传{name}", r["code"] == 0 and bool(r.get("data", {}).get("file_url")), r.get("message", "") or r.get("data", {}).get("file_url", ""))
        r = api(client, "POST", f"/health/records/{rec_uid}/file", token,
                files={"file": ("evil.txt", io.BytesIO(b"hello"), "text/plain")})
        step("非法类型(1001)", r["code"] == 1001, f"code={r.get('code')} {r.get('message', '')}")
        r = api(client, "POST", f"/health/records/{rec_uid}/file", token,
                files={"file": ("fake.pdf", io.BytesIO(b"not-a-pdf"), "application/pdf")})
        step("伪PDF拒绝(1001)", r["code"] == 1001, f"code={r.get('code')}")

        # 更新（改复查日期 → upcoming）
        r = api(client, "PUT", f"/health/records/{rec_uid}", token, json={
            "record_date": today.isoformat(), "title": "秋季体检(改)",
            "notes": "血常规正常，医生建议多户外活动",
            "next_checkup_date": (today + timedelta(days=30)).isoformat(),
        })
        step("记录更新", r["code"] == 0 and r["data"]["record"]["due_status"] == "upcoming", f"due={r.get('data', {}).get('record', {}).get('due_status')}")

        step("越权读记录(1002)", api(client, "GET", f"/health/records/{rec_uid}", token_b)["code"] == 1002)
        step("越权传文件(1002)", api(client, "POST", f"/health/records/{rec_uid}/file", token_b,
                                     files={"file": ("x.png", io.BytesIO(tiny_png()), "image/png")})["code"] == 1002)
        step("记录删除", api(client, "DELETE", f"/health/records/{rec_uid}", token)["code"] == 0)
        step("记录删除2", api(client, "DELETE", f"/health/records/{rec2_uid}", token)["code"] == 0)
        step("删后读(1002)", api(client, "GET", f"/health/records/{rec_uid}", token)["code"] == 1002)

    # ---------- psycopg2 加密落库核验（当前 provider 输出 kms1: 信封格式，v{N}: 为兼容回退） ----------
    if not DB_DSN:
        step("note 加密落库", True, "SKIP：未配置 SMOKE_DSN")
        step("health 加密落库", True, "SKIP：未配置 SMOKE_DSN")
    else:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()
        cur.execute("SELECT title, content_enc FROM note ORDER BY id DESC LIMIT 1")
        title, content_enc = cur.fetchone()
        step("note 加密落库", content_enc.startswith(("kms1:", "v")) and "米粉" not in content_enc,
             f"prefix={content_enc[:5]} title明文={title[:10]}")
        cur.execute("SELECT notes_enc FROM health_record WHERE notes_enc IS NOT NULL ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        step("health 加密落库", row is not None and row[0].startswith(("kms1:", "v")) and "血常规" not in row[0],
             f"prefix={(row[0] if row else '')[:5]}")
        cur.close()
        conn.close()

    fails = [r for r in results if not r[1]]
    print(f"\n===== {len(results) - len(fails)}/{len(results)} PASSED =====")
    for name, _, detail in fails:
        print(f"  FAIL: {name} | {detail}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

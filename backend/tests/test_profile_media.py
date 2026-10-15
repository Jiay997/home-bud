# -*- coding: utf-8 -*-
"""档案媒体（头像/相册）集成测试。

甲方需求 2026-10-14：档案可设置头像与相册（孩子/宠物同构，30 张/档案）。
覆盖：
- 头像上传/覆盖替换（旧文件同步删除）/移除（幂等）与视图 avatar_url 联动；
- 相册添加/列表/删除（文件同步清理）、上限 1007、照片不存在 1002；
- 儿童同意门禁 1302（撤回后媒体读写全拦、列表 avatar_url 停止展示）；
- 防枚举 1002（越权档案/照片统一不存在）、参数异常 1001（坏图/超体积/非法 kind）；
- 删除档案清理媒体文件（purge_all 回执含媒体条目）；
- /media 静态挂载直出规范化后的 JPEG。
"""
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.media_store import media_root  # noqa: E402

API = "/api/v1"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _image_bytes(fmt="JPEG", size=(2000, 1000), color=(130, 160, 140)):
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


def _create_child(client, headers, nickname="媒体娃"):
    """创建儿童档案（需已同意）并返回 data。"""
    resp = client.post(
        f"{API}/profiles/children",
        json={"nickname": nickname, "birth_date": "2025-04-08"},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


def _create_pet(client, headers, breed="媒体猫"):
    """创建宠物档案并返回 data。"""
    resp = client.post(
        f"{API}/profiles/pets",
        json={"pet_type": "cat", "age_band": "adult", "breed": breed},
        headers=headers,
    )
    assert resp.json()["code"] == 0, resp.text
    return resp.json()["data"]


def _file_of(media_url):
    """媒体 URL（/media/...）→ 磁盘文件路径。"""
    assert media_url and media_url.startswith("/media/"), media_url
    return media_root() / media_url[len("/media/"):]


def _upload(client, method, url, headers, data, name="a.jpg", mime="image/jpeg"):
    """multipart 上传封装（PUT/POST 通用）。

    Args:
        client: TestClient。
        method: HTTP 方法（头像上传统一 post：用户端 uploadFile 恒发 POST）。
        url: 端点 URL。
        headers: 鉴权头。
        data: 文件字节。
        name: 文件名。
        mime: 文件 MIME。

    Returns:
        httpx 响应。
    """
    return getattr(client, method)(
        url, files={"file": (name, data, mime)}, headers=headers
    )


# ---------------------------------------------------------------------------
# 儿童同意门禁（1302）
# ---------------------------------------------------------------------------
class TestChildMediaConsentGate:
    """撤回儿童信息同意后：媒体读写全拦，列表 avatar_url 停止展示。"""

    def test_withdraw_blocks_media_and_hides_avatar(self, client, user_token):
        """撤回前可传头像；撤回后上传/相册/移除均 1302，列表 avatar_url 置空。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        child = _create_child(client, headers)
        uid = child["profile_uid"]

        put = _upload(
            client, "post", f"{API}/profiles/children/{uid}/avatar", headers, _image_bytes()
        )
        assert put.status_code == 200 and put.json()["code"] == 0, put.text
        avatar_url = put.json()["data"]["avatar_url"]

        # 撤回儿童信息同意 → 全部儿童档案 disabled
        withdraw = client.post(
            f"{API}/consent/withdraw",
            json={"consent_type": "child_personal_info"},
            headers=headers,
        )
        assert withdraw.json()["code"] == 0
        assert withdraw.json()["data"]["impact"]["child_profiles_disabled"] == 1

        # 列表：昵称脱敏且不再返回头像（停止展示与使用）
        listed = client.get(f"{API}/profiles/children", headers=headers).json()["data"]
        row = next(c for c in listed["children"] if c["profile_uid"] == uid)
        assert row["status"] == "disabled" and row["avatar_url"] is None

        # 读写全拦 1302
        again = _upload(
            client, "post", f"{API}/profiles/children/{uid}/avatar", headers, _image_bytes()
        )
        assert again.status_code == 403 and again.json()["code"] == 1302
        photos = client.get(f"{API}/profiles/children/{uid}/photos", headers=headers)
        assert photos.status_code == 403 and photos.json()["code"] == 1302
        removed = client.delete(
            f"{API}/profiles/children/{uid}/avatar", headers=headers
        )
        assert removed.status_code == 403 and removed.json()["code"] == 1302
        # 文件仍在（撤回不清理，仅停止展示与使用）
        assert _file_of(avatar_url).is_file()


# ---------------------------------------------------------------------------
# 头像
# ---------------------------------------------------------------------------
class TestAvatar:
    """头像上传/替换/移除与视图联动。"""

    def test_child_avatar_upload_replace_and_remove(self, client, user_token):
        """上传→规范化 512 长边、静态直出、覆盖删除旧文件、移除幂等、version 不变。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        child = _create_child(client, headers)
        uid = child["profile_uid"]
        base = f"{API}/profiles/children/{uid}"

        first = _upload(client, "post", f"{base}/avatar", headers, _image_bytes(size=(2000, 1000)))
        assert first.status_code == 200 and first.json()["code"] == 0, first.text
        data1 = first.json()["data"]
        assert (data1["width"], data1["height"]) == (512, 256)
        old_file = _file_of(data1["avatar_url"])
        assert old_file.is_file()

        # /media 静态挂载直出规范化 JPEG
        served = client.get(data1["avatar_url"])
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("image/jpeg")
        assert served.content[:2] == b"\xff\xd8"

        # 列表视图同步 avatar_url，且 version 不因媒体变更递增
        row = next(
            c
            for c in client.get(f"{API}/profiles/children", headers=headers).json()["data"][
                "children"
            ]
            if c["profile_uid"] == uid
        )
        assert row["avatar_url"] == data1["avatar_url"] and row["version"] == child["version"]

        # 覆盖替换：新文件就位、旧文件删除
        second = _upload(client, "post", f"{base}/avatar", headers, _image_bytes(size=(800, 800)))
        assert second.json()["code"] == 0, second.text
        data2 = second.json()["data"]
        assert data2["avatar_url"] != data1["avatar_url"]
        assert not old_file.exists() and _file_of(data2["avatar_url"]).is_file()

        # 移除（幂等）：文件删除、视图置空、重复移除仍成功
        removed = client.delete(f"{base}/avatar", headers=headers)
        assert removed.status_code == 200 and removed.json()["code"] == 0
        assert not _file_of(data2["avatar_url"]).exists()
        row2 = next(
            c
            for c in client.get(f"{API}/profiles/children", headers=headers).json()["data"][
                "children"
            ]
            if c["profile_uid"] == uid
        )
        assert row2["avatar_url"] is None
        again = client.delete(f"{base}/avatar", headers=headers)
        assert again.status_code == 200 and again.json()["code"] == 0

    def test_pet_avatar_upload_and_cross_user_1002(self, client, user_token):
        """宠物头像可传（无同意门禁）；他人档案与未知 uid 统一 1002。"""
        headers_a, _ = user_token("media-avatar-a")
        pet = _create_pet(client, headers_a)
        base = f"{API}/profiles/pets/{pet['pet_uid']}"

        put = _upload(client, "post", f"{base}/avatar", headers_a, _image_bytes(size=(600, 400)))
        assert put.status_code == 200 and put.json()["code"] == 0, put.text
        assert put.json()["data"]["avatar_url"].startswith("/media/pets/")
        row = next(
            p
            for p in client.get(f"{API}/profiles/pets", headers=headers_a).json()["data"]["pets"]
            if p["pet_uid"] == pet["pet_uid"]
        )
        assert row["avatar_url"] == put.json()["data"]["avatar_url"]

        # 他人用户：越权与未知 uid 均 1002（防枚举）
        headers_b, _ = user_token("media-avatar-b")
        foreign = _upload(client, "post", f"{base}/avatar", headers_b, _image_bytes())
        assert foreign.status_code == 404 and foreign.json()["code"] == 1002
        unknown = _upload(
            client, "post", f"{API}/profiles/pets/no-such-uid/avatar", headers_b, _image_bytes()
        )
        assert unknown.status_code == 404 and unknown.json()["code"] == 1002

    def test_avatar_invalid_inputs_1001(self, client, user_token):
        """坏图/非法格式/超体积 → 1001(422)；非法 kind → 1001(422)。"""
        headers, _ = user_token()
        pet = _create_pet(client, headers)
        url = f"{API}/profiles/pets/{pet['pet_uid']}/avatar"

        broken = _upload(client, "post", url, headers, b"not-an-image")
        assert broken.status_code == 422 and broken.json()["code"] == 1001
        gif = _upload(client, "post", url, headers, _image_bytes("GIF", (100, 100)), name="a.gif", mime="image/gif")
        assert gif.status_code == 422 and gif.json()["code"] == 1001
        oversize = _upload(client, "post", url, headers, b"\x00" * (8 * 1024 * 1024 + 1))
        assert oversize.status_code == 422 and oversize.json()["code"] == 1001
        bad_kind = _upload(
            client, "post", f"{API}/profiles/dogs/{pet['pet_uid']}/avatar", headers, _image_bytes()
        )
        assert bad_kind.status_code == 422 and bad_kind.json()["code"] == 1001
        # 坏输入未产生头像
        row = next(
            p
            for p in client.get(f"{API}/profiles/pets", headers=headers).json()["data"]["pets"]
            if p["pet_uid"] == pet["pet_uid"]
        )
        assert row["avatar_url"] is None


# ---------------------------------------------------------------------------
# 相册
# ---------------------------------------------------------------------------
class TestPhotoAlbum:
    """相册增查删、上限与参数异常。"""

    def test_child_photo_roundtrip(self, client, user_token):
        """添加两张（PNG 大图规范化）→ 列表升序 + 计数 → 删除文件同步清理。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        child = _create_child(client, headers)
        base = f"{API}/profiles/children/{child['profile_uid']}"

        first = _upload(client, "post", f"{base}/photos", headers, _image_bytes("PNG", (900, 1400)), name="a.png", mime="image/png")
        assert first.status_code == 200 and first.json()["code"] == 0, first.text
        assert first.json()["data"]["count"] == 1 and first.json()["data"]["limit"] == 30
        photo1 = first.json()["data"]["photo"]
        assert photo1["url"].startswith("/media/children/") and _file_of(photo1["url"]).is_file()

        second = _upload(client, "post", f"{base}/photos", headers, _image_bytes("JPEG", (400, 400)))
        assert second.json()["data"]["count"] == 2
        photo2 = second.json()["data"]["photo"]

        listed = client.get(f"{base}/photos", headers=headers).json()["data"]
        assert listed["limit"] == 30
        assert [p["photo_uid"] for p in listed["photos"]] == [photo1["photo_uid"], photo2["photo_uid"]]
        served = client.get(photo1["url"])
        assert served.status_code == 200 and served.headers["content-type"].startswith("image/jpeg")

        # 删除：行软删 + 文件删除；列表同步；重复删除 1002
        deleted = client.delete(f"{base}/photos/{photo1['photo_uid']}", headers=headers)
        assert deleted.status_code == 200 and deleted.json()["code"] == 0
        assert not _file_of(photo1["url"]).exists()
        assert (
            len(client.get(f"{base}/photos", headers=headers).json()["data"]["photos"]) == 1
        )
        again = client.delete(f"{base}/photos/{photo1['photo_uid']}", headers=headers)
        assert again.status_code == 404 and again.json()["code"] == 1002

    def test_photo_limit_1007(self, client, user_token, monkeypatch):
        """达到配置上限后再添加 → 1007(409)。"""
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "profile_photo_limit", 2)
        headers, _ = user_token()
        pet = _create_pet(client, headers)
        base = f"{API}/profiles/pets/{pet['pet_uid']}"

        for i in range(2):
            resp = _upload(client, "post", f"{base}/photos", headers, _image_bytes(size=(120, 120)))
            assert resp.json()["code"] == 0, resp.text
        over = _upload(client, "post", f"{base}/photos", headers, _image_bytes(size=(120, 120)))
        assert over.status_code == 409 and over.json()["code"] == 1007
        # 删除一张后恢复可加
        photo_uid = client.get(f"{base}/photos", headers=headers).json()["data"]["photos"][0][
            "photo_uid"
        ]
        assert client.delete(f"{base}/photos/{photo_uid}", headers=headers).json()["code"] == 0
        ok_again = _upload(client, "post", f"{base}/photos", headers, _image_bytes(size=(120, 120)))
        assert ok_again.status_code == 200 and ok_again.json()["code"] == 0

    def test_photo_mismatch_and_bad_file_1002_1001(self, client, user_token):
        """他人/错配 photo_uid 统一 1002；坏文件 1001；非本人档案 1002。"""
        headers_a, _ = user_token("media-photo-a")
        pet_a = _create_pet(client, headers_a)
        base_a = f"{API}/profiles/pets/{pet_a['pet_uid']}"
        photo = _upload(client, "post", f"{base_a}/photos", headers_a, _image_bytes(size=(120, 120)))
        photo_uid = photo.json()["data"]["photo"]["photo_uid"]

        # 同用户错配：用自己另一个档案删他人档案的 photo_uid → 1002
        pet_own = _create_pet(client, headers_a, breed="错配猫")
        mismatch = client.delete(
            f"{API}/profiles/pets/{pet_own['pet_uid']}/photos/{photo_uid}", headers=headers_a
        )
        assert mismatch.status_code == 404 and mismatch.json()["code"] == 1002

        # 越权档案
        headers_b, _ = user_token("media-photo-b")
        foreign = client.delete(
            f"{base_a}/photos/{photo_uid}", headers=headers_b
        )
        assert foreign.status_code == 404 and foreign.json()["code"] == 1002

        # 坏文件 1001
        bad = _upload(client, "post", f"{base_a}/photos", headers_a, b"garbage")
        assert bad.status_code == 422 and bad.json()["code"] == 1001
        # 原照片仍在
        assert (
            len(client.get(f"{base_a}/photos", headers=headers_a).json()["data"]["photos"]) == 1
        )


# ---------------------------------------------------------------------------
# 删除档案清理媒体
# ---------------------------------------------------------------------------
class TestProfileDeleteCleansMedia:
    """删除档案（两种模式）同步清理媒体文件；purge_all 回执含媒体条目。"""

    def test_purge_child_cleans_media_and_receipt(self, client, user_token):
        """purge_all：头像/照片文件删除、照片行软删、回执含 profile_media 条目。"""
        headers, _ = user_token()
        _agree_all(client, headers)
        child = _create_child(client, headers, nickname="清理娃")
        base = f"{API}/profiles/children/{child['profile_uid']}"

        avatar = _upload(client, "post", f"{base}/avatar", headers, _image_bytes())
        avatar_file = _file_of(avatar.json()["data"]["avatar_url"])
        photo = _upload(client, "post", f"{base}/photos", headers, _image_bytes(size=(300, 300)))
        photo_file = _file_of(photo.json()["data"]["photo"]["url"])
        assert avatar_file.is_file() and photo_file.is_file()

        resp = client.request(
            "DELETE",
            base,
            json={"mode": "purge_all", "confirm_nickname": "清理娃"},
            headers=headers,
        )
        assert resp.status_code == 200 and resp.json()["code"] == 0, resp.text
        receipt = resp.json()["data"]["deletion_receipt"]
        media_items = [d for d in receipt["deleted"] if d["item"] == "profile_media"]
        assert media_items and media_items[0]["photos"] == 1
        assert not avatar_file.exists() and not photo_file.exists()

    def test_delete_pet_cleans_media(self, client, user_token):
        """宠物删除（软删）同样清理头像与相册文件。"""
        headers, _ = user_token()
        pet = _create_pet(client, headers, breed="清理猫")
        base = f"{API}/profiles/pets/{pet['pet_uid']}"
        avatar = _upload(client, "post", f"{base}/avatar", headers, _image_bytes())
        photo = _upload(client, "post", f"{base}/photos", headers, _image_bytes(size=(300, 300)))
        avatar_file = _file_of(avatar.json()["data"]["avatar_url"])
        photo_file = _file_of(photo.json()["data"]["photo"]["url"])

        resp = client.delete(base, headers=headers)
        assert resp.status_code == 200 and resp.json()["code"] == 0
        assert not avatar_file.exists() and not photo_file.exists()
        assert pet["pet_uid"] not in [
            p["pet_uid"] for p in client.get(f"{API}/profiles/pets", headers=headers).json()["data"]["pets"]
        ]

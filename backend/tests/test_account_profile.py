# -*- coding: utf-8 -*-
"""账号资料（昵称/头像）集成测试。

覆盖：
- GET /me 返回 nickname / avatar_url 字段；
- PUT /me/profile 昵称去空白后保存、/me 立即反映、纯空白拒绝 1001；
- POST /me/avatar 上传规范化头像、覆盖时删除旧文件；
- DELETE /me/avatar 幂等移除并同步清理文件；
- 坏图上传返回 1001。

说明：退出登录/切换账号为客户端本机会话操作，不产生服务端数据变更，
故不在本文档覆盖范围内。
"""
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.media_store import media_root  # noqa: E402

API = "/api/v1"


def _image_bytes(fmt: str = "JPEG", size: tuple = (1600, 1200)) -> bytes:
    """生成测试图片字节。

    Args:
        fmt: 编码格式（JPEG/PNG）。
        size: (宽, 高)。

    Returns:
        图片字节。
    """
    buf = io.BytesIO()
    Image.new("RGB", size, (130, 160, 140)).save(buf, format=fmt)
    return buf.getvalue()


def _file_of(media_url: str) -> Path:
    """媒体 URL（/media/...）转磁盘文件路径。

    Args:
        media_url: 对外媒体地址。

    Returns:
        磁盘绝对路径。

    Raises:
        AssertionError: URL 不是合法媒体路径。
    """
    assert media_url and media_url.startswith("/media/"), media_url
    return media_root() / media_url[len("/media/"):]


def test_me_profile_nickname_roundtrip_and_blank_rejected(client, user_token):
    """昵称保存后 /me 立即生效；纯空白昵称返回 1001。"""
    headers, _ = user_token()

    initial = client.get(f"{API}/me", headers=headers)
    assert initial.status_code == 200 and initial.json()["code"] == 0, initial.text
    assert initial.json()["data"]["nickname"] == ""
    assert initial.json()["data"]["avatar_url"] is None

    saved = client.put(
        f"{API}/me/profile", json={"nickname": "  小宝妈妈  "}, headers=headers
    )
    assert saved.status_code == 200 and saved.json()["code"] == 0, saved.text
    assert saved.json()["data"]["nickname"] == "小宝妈妈"

    refreshed = client.get(f"{API}/me", headers=headers)
    assert refreshed.json()["data"]["nickname"] == "小宝妈妈"

    blank = client.put(
        f"{API}/me/profile", json={"nickname": "   "}, headers=headers
    )
    assert blank.status_code == 422, blank.text
    assert blank.json()["code"] == 1001


def test_me_avatar_upload_replace_and_remove(client, user_token):
    """头像上传/覆盖删除旧文件/幂等移除并同步清理磁盘文件。"""
    headers, _ = user_token()
    data = _image_bytes()

    first = client.post(
        f"{API}/me/avatar", files={"file": ("a.jpg", data, "image/jpeg")}, headers=headers
    )
    assert first.status_code == 200 and first.json()["code"] == 0, first.text
    first_url = first.json()["data"]["avatar_url"]
    first_file = _file_of(first_url)
    assert first_file.exists()
    assert first_url.startswith("/media/users/")

    me_view = client.get(f"{API}/me", headers=headers)
    assert me_view.json()["data"]["avatar_url"] == first_url

    second = client.post(
        f"{API}/me/avatar", files={"file": ("b.png", _image_bytes("PNG"), "image/png")}, headers=headers
    )
    assert second.status_code == 200 and second.json()["code"] == 0, second.text
    second_url = second.json()["data"]["avatar_url"]
    assert second_url != first_url
    assert not first_file.exists(), "覆盖头像后旧文件应被删除"

    removed = client.delete(f"{API}/me/avatar", headers=headers)
    assert removed.status_code == 200 and removed.json()["code"] == 0, removed.text
    assert not _file_of(second_url).exists()

    # 幂等：未设置头像时再次移除同样成功
    again = client.delete(f"{API}/me/avatar", headers=headers)
    assert again.status_code == 200 and again.json()["code"] == 0, again.text
    assert client.get(f"{API}/me", headers=headers).json()["data"]["avatar_url"] is None


def test_me_avatar_rejects_invalid_image(client, user_token):
    """坏图上传统一返回 1001，不落库。"""
    headers, _ = user_token()
    resp = client.post(
        f"{API}/me/avatar",
        files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == 1001
    assert client.get(f"{API}/me", headers=headers).json()["data"]["avatar_url"] is None

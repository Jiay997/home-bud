# -*- coding: utf-8 -*-
"""超管账号创建脚本（幂等）：用于忘记密码后重置或首次部署。

用法：python scripts/create_admin.py [username] [password]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.crypto import encrypt_field  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models import AdminUser  # noqa: E402


def create_or_reset_admin(username: str, password: str) -> None:
    """创建或重置超管账号（幂等）。

    Args:
        username: 登录名。
        password: 新密码（明文，内部立即哈希）。

    Raises:
        Exception: 数据库写入失败时抛出。
    """
    db: Session = get_session_factory()()
    try:
        admin = db.query(AdminUser).filter_by(username=username).first()
        if admin:
            admin.password_hash = hash_password(password)
            admin.fail_count = 0
            admin.locked_until = None
            print(f"[create_admin] reset password for '{username}'")
        else:
            db.add(AdminUser(
                username=username, display_name="系统超管",
                password_hash=hash_password(password),
                phone_enc=encrypt_field("13800000000"),
                role="super_admin",
            ))
            print(f"[create_admin] super admin '{username}' created")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    uname = sys.argv[1] if len(sys.argv) > 1 else "admin"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "Admin@123456"
    create_or_reset_admin(uname, pwd)

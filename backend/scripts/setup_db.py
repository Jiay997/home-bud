# -*- coding: utf-8 -*-
"""数据库创建脚本：连接 postgres 系统库创建 jiaban 业务库（幂等）。

用法：python scripts/setup_db.py
"""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402


def create_database_if_not_exists() -> None:
    """创建 jiaban 数据库（已存在则跳过）。

    Raises:
        psycopg2.Error: 数据库服务不可达时抛出。
    """
    settings = get_settings()
    # 解析连接串：postgresql+psycopg2://user:pass@host:port/dbname
    raw = settings.database_url.replace("postgresql+psycopg2://", "")
    cred, _, hostpart = raw.rpartition("@")
    user, _, password = cred.partition(":")
    host, _, port = hostpart.partition(":")
    dbname = port.partition("/")[2]
    port = port.partition("/")[0]

    conn = psycopg2.connect(
        host=host, port=int(port), user=user, password=password, dbname="postgres"
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone():
                print(f"[setup_db] database '{dbname}' already exists")
            else:
                cur.execute(f'CREATE DATABASE "{dbname}" ENCODING \'UTF8\'')
                print(f"[setup_db] database '{dbname}' created")
    finally:
        conn.close()


if __name__ == "__main__":
    create_database_if_not_exists()

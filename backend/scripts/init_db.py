# -*- coding: utf-8 -*-
"""建表脚本：按数据模型文档 V1.1 创建全部 37 张表与索引（幂等可重复执行）。

用法：python scripts/init_db.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.models import ALL_MODELS, Base  # noqa: E402

logger = logging.getLogger("jiaban.init_db")


def ensure_org_id_columns() -> None:
    """幂等迁移：为已有主表补 org_id 列（create_all 不会 ALTER 已有表）。

    覆盖数据模型文档附注要求的 5 张主表；列已存在时跳过。

    Raises:
        Exception: DDL 执行失败时抛出。
    """
    engine = get_engine()
    targets = ["app_user", "child_profile", "pet_profile", "qa_session", "report"]
    with engine.begin() as conn:
        for table in targets:
            cols = {c["name"] for c in inspect(engine).get_columns(table)}
            if "org_id" not in cols:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN org_id VARCHAR NULL')
                )
                print(f"[init_db] ALTER {table} ADD org_id")
            # 索引：存在则跳过
            idx = f"idx_{table}_org_id"
            idx_names = {i["name"] for i in inspect(engine).get_indexes(table)}
            if idx not in idx_names:
                conn.execute(
                    text(f'CREATE INDEX IF NOT EXISTS "{idx}" ON "{table}" (org_id)')
                )
                print(f"[init_db] CREATE INDEX {idx}")


def ensure_profile_media_columns() -> None:
    """幂等迁移：为 child_profile / pet_profile 补 avatar_path 列。

    档案头像功能（甲方需求 2026-10-14）：历史库缺此列时在此补齐，
    已存在则跳过。profile_photo 新表走 create_all 自动创建。

    Raises:
        Exception: DDL 执行失败时抛出。
    """
    engine = get_engine()
    with engine.begin() as conn:
        for table in ("child_profile", "pet_profile"):
            cols = {c["name"] for c in inspect(engine).get_columns(table)}
            if "avatar_path" not in cols:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN avatar_path VARCHAR(255) NULL')
                )
                print(f"[init_db] ALTER {table} ADD avatar_path")
            else:
                print(f"[init_db] {table}.avatar_path already exists, skip")


def ensure_user_profile_columns() -> None:
    """幂等迁移：为 app_user 补账号资料列（昵称密文 / 头像相对路径）。

    create_all 不会 ALTER 已有表，历史库在此补齐；列已存在则跳过。

    Raises:
        Exception: DDL 执行失败时抛出。
    """
    engine = get_engine()
    targets = {"nickname_enc": "TEXT NULL", "avatar_path": "VARCHAR(255) NULL"}
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("app_user")}
        for column, ddl in targets.items():
            if column in cols:
                print(f"[init_db] app_user.{column} already exists, skip")
                continue
            conn.execute(text(f'ALTER TABLE "app_user" ADD COLUMN {column} {ddl}'))
            print(f"[init_db] ALTER app_user ADD {column}")


def init_tables() -> None:
    """创建全部业务表（checkfirst 幂等）并执行补列迁移。

    Raises:
        Exception: 建表失败（如数据库不可达、约束冲突）时抛出。
    """
    engine = get_engine()
    # 防漏注册守卫：基线至少 37 张表（35 + health_record + note），
    # V3.1 新增表后允许大于该值，避免每次扩表都要改硬编码断言。
    assert len(ALL_MODELS) >= 37, f"expect at least 37 tables, got {len(ALL_MODELS)}"
    Base.metadata.create_all(engine, checkfirst=True)
    ensure_org_id_columns()
    ensure_profile_media_columns()
    ensure_user_profile_columns()
    tables = sorted(Base.metadata.tables.keys())
    print(f"[init_db] {len(tables)} tables ensured:")
    for t in tables:
        print(f"  - {t}")


def ensure_wx_session_key_column() -> None:
    """幂等迁移：为 app_user 补 wx_session_key_enc 列（create_all 不会 ALTER 已有表）。

    wx-login 需要将微信 session_key 加密留存（spec 通道抽象 Task 3）；
    历史库缺此列时在此补齐，已存在则跳过。勿并入 ensure_org_id_columns
    （两者目标不同，保持各自独立可回滚）。

    Raises:
        Exception: DDL 执行失败时抛出。
    """
    engine = get_engine()
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("app_user")}
        if "wx_session_key_enc" not in cols:
            conn.execute(
                text('ALTER TABLE "app_user" ADD COLUMN wx_session_key_enc TEXT NULL')
            )
            print("[init_db] ALTER app_user ADD wx_session_key_enc")
        else:
            print("[init_db] app_user.wx_session_key_enc already exists, skip")


def ensure_rag_index() -> None:
    """幂等初始化 Milvus 向量集合（spec milvus-vector-store）。

    经 rag_index.ensure_collection() 创建集合 jiaban_kb_entries
    （2048 维 HNSW COSINE + Strong 一致性）。MILVUS_URI 未配置（主通道
    禁用）或 Milvus 不可达时记录 info 后返回——检索层走 hashing 降级链，
    业务无感。

    Returns:
        None。
    """
    from app.services import rag_index

    if not rag_index._PYMILVUS_OK:
        logger.info(
            "[init_db] pymilvus not installed, skip rag collection setup "
            "(retrieval falls back to hashing path)"
        )
        return
    try:
        if rag_index.ensure_collection():
            print("[init_db] rag index ready: Milvus collection "
                  f"{rag_index.COLLECTION_NAME} (HNSW COSINE, Strong)")
        else:
            logger.info(
                "[init_db] rag collection setup skipped (MILVUS_URI not "
                "configured or Milvus unreachable) — retrieval falls back "
                "to hashing path"
            )
    except Exception as exc:  # noqa: BLE001 — 不可用环境按降级方案运行
        logger.info(
            "[init_db] rag collection setup skipped (Milvus unavailable, "
            "retrieval falls back to hashing): %s",
            exc,
        )


if __name__ == "__main__":
    init_tables()
    ensure_wx_session_key_column()
    ensure_rag_index()

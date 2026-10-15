# -*- coding: utf-8 -*-
"""[历史回滚保留] 旧 pgvector 直连路径迁移执行器。

spec milvus-vector-store：检索主通道已为 Milvus 独立向量库（集合
jiaban_kb_entries，scripts/reindex_rag.py 执行全量重建），本脚本停用；
文件保留作回滚保险（旧 kb_entry.embedding_vec 列不删除）。运行即退出。
"""
raise SystemExit(
    "run_pgvector_migration.py is deprecated: the retrieval main channel "
    "now uses Milvus standalone (collection jiaban_kb_entries). "
    "Use `python scripts/reindex_rag.py` instead. This script is kept only "
    "for rollback reference (old kb_entry.embedding_vec column is preserved)."
)

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db import get_engine, get_session_factory  # noqa: E402
from app.services.retriever import PgVectorStore  # noqa: E402

# 迁移 SQL 与本脚本同目录
SQL_PATH = Path(__file__).resolve().parent / "migrate_pgvector.sql"


def run_migration() -> bool:
    """执行迁移 SQL 两遍并做 PgVectorStore 就绪探测。

    Returns:
        就绪探测通过 True；扩展/列不可用（降级路径）False。

    Raises:
        Exception: SQL 执行失败（语法/连接等）时向上抛出。
    """
    sql = SQL_PATH.read_text(encoding="utf-8")
    engine = get_engine()

    # 建表前置（幂等）：kb_entry 须先存在，create_all checkfirst 无副作用
    from app.models import Base

    Base.metadata.create_all(engine, checkfirst=True)

    # 连续执行两遍验证幂等（DO 块全量 IF NOT EXISTS / TRY-CATCH，重复执行无副作用）
    # 说明：经 text() 执行（语句内 RAISE NOTICE 含 % 格式符，不能带参数路径，
    # text() 无参数编译后 psycopg2 原样发送，% 不会被插值）
    migration_sql = text(sql)
    for i in (1, 2):
        with engine.begin() as conn:
            conn.execute(migration_sql)
        print(f"[run_pgvector_migration] pass {i}/2 executed (idempotent)")

    # PgVectorStore 就绪探测（扩展 + embedding_vec 列；探测结果进程内缓存）
    db = get_session_factory()()
    try:
        ready = PgVectorStore(db).available()
    finally:
        db.close()
    if ready:
        print("[run_pgvector_migration] PgVectorStore ready: extension vector + "
              "kb_entry.embedding_vec both available（本地已验证）")
    else:
        print("[run_pgvector_migration] pgvector unavailable on this database: "
              "extension missing/invalid —— 降级路径生效（检索回退进程内，业务无感）")
    return ready


def main() -> int:
    """脚本入口：执行迁移并按结论输出退出码。

    Returns:
        0 = 执行成功（含降级结论）；1 = 执行异常。
    """
    try:
        run_migration()
        return 0
    except Exception as exc:  # noqa: BLE001 — 脚本顶层兜底，明确输出失败原因
        print(f"[run_pgvector_migration] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

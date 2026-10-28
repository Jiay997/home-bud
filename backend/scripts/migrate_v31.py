# -*- coding: utf-8 -*-
"""V3.1 增量库结构迁移脚本（幂等，可重复执行）。

背景：`scripts/init_db.py` 用 `Base.metadata.create_all()` 只能**建缺失的表**，
不会给既有表补列；V3.1 引入了 11 张新表与 9 个既有表的新列，存量库必须显式
ALTER 才能跑通（否则问答创建会报 `column "input_mode" does not exist`）。

本脚本做三件事：

1. `create_all(checkfirst=True)` 建全部缺失表（V3.1 新增 11 张）；
2. 对既有表逐列 `ADD COLUMN IF NOT EXISTS` 补齐 V3.1 新列（含默认值）；
3. 为新增索引 `CREATE INDEX IF NOT EXISTS`（新表的索引由 create_all 负责，
   这里只补既有表上的新增索引，本版无）。

用法（工作目录 backend/，读 .env 的 DATABASE_URL）：
    python scripts/migrate_v31.py            # 执行迁移
    python scripts/migrate_v31.py --dry-run  # 只打印将要执行的 DDL

约束：脚本不删除任何列、不改列类型、不回填业务数据；播种与品牌名修正
由 `scripts/seed_data.py` 负责（幂等）。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.models import ALL_MODELS, Base  # noqa: E402

# 既有表 → 需要补的列（列名, 类型 SQL, 默认值 SQL 或 None）
# 口径与 app/models/{qa,kb}.py 的列定义保持一致
COLUMN_PATCHES = [
    # 表名, 列名, 类型, 默认/回填
    ("qa_session", "input_mode", "VARCHAR(8)", "'text'"),
    ("qa_session", "photo_meta", "JSONB", None),
    ("qa_session", "triage", "JSONB", None),
    ("qa_session", "triage_level", "VARCHAR(8)", None),
    ("qa_session", "reminder_trace_id", "VARCHAR(64)", None),
    ("crisis_channel", "category", "VARCHAR(32)", "'psychological'"),
    ("crisis_channel", "region", "VARCHAR(32)", "'全国'"),
    ("crisis_channel", "service_hours", "VARCHAR(64)", None),
    ("crisis_channel", "verified_by", "VARCHAR(64)", None),
    ("crisis_channel", "sort_weight", "INTEGER", "100"),
    ("kb_entry", "source_level", "VARCHAR(16)", None),
]

# 新列的非空约束：补列时带默认值填写（避免存量行 NULL 违背 NOT NULL）
NOT_NULL_COLUMNS = {
    ("qa_session", "input_mode"),
    ("crisis_channel", "category"),
    ("crisis_channel", "region"),
    ("crisis_channel", "sort_weight"),
}


def _existing_columns(inspector, table: str) -> set:
    """读取表当前列名集合（表不存在返回空集）。

    Args:
        inspector: SQLAlchemy Inspector。
        table: 表名。

    Returns:
        列名集合。
    """
    try:
        return {col["name"] for col in inspector.get_columns(table)}
    except Exception:  # noqa: BLE001 — 表不存在
        return set()


def main() -> None:
    """执行迁移并打印结果。

    Returns:
        None。

    Raises:
        SystemExit: 迁移失败时以退出码 1 结束。
    """
    parser = argparse.ArgumentParser(description="V3.1 增量库结构迁移")
    parser.add_argument("--dry-run", action="store_true", help="只打印 DDL 不执行")
    args = parser.parse_args()

    engine = get_engine()
    print(f"[migrate-v31] target: {engine.url.render_as_string(hide_password=True)}")

    # 1) 建缺失表
    before = set(inspect(engine).get_table_names())
    expected = {model.__tablename__ for model in ALL_MODELS}
    if args.dry_run:
        print(f"[migrate-v31] dry-run: 将创建缺失表 {sorted(expected - before)}")
    else:
        Base.metadata.create_all(engine, checkfirst=True)
        after = set(inspect(engine).get_table_names())
        print(f"[migrate-v31] 新建表 {sorted(after - before)}")

    # 2) 既有表补列
    inspector = inspect(engine)
    applied = 0
    skipped = 0
    for table, column, col_type, default in COLUMN_PATCHES:
        existing = _existing_columns(inspector, table)
        if not existing:
            print(f"[migrate-v31] SKIP {table}.{column}（表不存在，应由 create_all 新建）")
            skipped += 1
            continue
        if column in existing:
            print(f"[migrate-v31] OK   {table}.{column} 已存在")
            skipped += 1
            continue
        ddl = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'
        if default is not None:
            ddl += f" DEFAULT {default}"
        if (table, column) in NOT_NULL_COLUMNS:
            ddl += " NOT NULL"
        if default is None and (table, column) in NOT_NULL_COLUMNS:
            raise SystemExit(f"[migrate-v31] FAIL: {table}.{column} 非空但无默认值")
        if args.dry_run:
            print(f"[migrate-v31] DDL  {ddl}")
            continue
        with engine.begin() as conn:
            conn.execute(text(ddl))
            # 存量行回填（DEFAULT 已覆盖；此处仅保证语义显式）
            if default is not None:
                conn.execute(
                    text(
                        f'UPDATE "{table}" SET "{column}" = {default} '
                        f'WHERE "{column}" IS NULL'
                    )
                )
        applied += 1
        print(f"[migrate-v31] ADD  {table}.{column} {col_type}")

    # 3) 校验：全部模型表均存在
    final_tables = set(inspect(engine).get_table_names())
    missing = expected - final_tables
    if missing:
        raise SystemExit(f"[migrate-v31] FAIL: 仍缺表 {sorted(missing)}")
    print(
        f"[migrate-v31] 完成：新增列 {applied} 个，跳过/已存在 {skipped} 个，"
        f"业务表共 {len(final_tables & expected)} 张"
    )


if __name__ == "__main__":
    main()

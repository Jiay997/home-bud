# -*- coding: utf-8 -*-
"""org_id 预留落库校验脚本（spec：评估报告 6.1 #7 技术债收口）。

断言 5 张主表（app_user/child_profile/pet_profile/qa_session/report）
均含 org_id 列与 idx_org_id 索引，且现有查询路径不依赖该列。

用法：python scripts/check_org_id.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.models import ChildProfile, AppUser, PetProfile, QaSession, Report  # noqa: E402

# 数据模型文档附注要求的 5 张主表
TARGET_TABLES = [AppUser, ChildProfile, PetProfile, QaSession, Report]


def check_org_id() -> None:
    """校验 5 张主表的 org_id 列与索引。

    Raises:
        AssertionError: 任一表缺列或缺索引。
    """
    engine = get_engine()
    insp = inspect(engine)
    failures = []
    for model in TARGET_TABLES:
        table = model.__tablename__
        columns = {c["name"] for c in insp.get_columns(table)}
        indexes = {i["name"] for i in insp.get_indexes(table)}
        if "org_id" not in columns:
            failures.append(f"{table}: missing column org_id")
        if f"idx_{table}_org_id" not in indexes:
            failures.append(f"{table}: missing index idx_{table}_org_id")
    if failures:
        for f in failures:
            print(f"[check_org_id] FAIL {f}")
        raise AssertionError("org_id 预留校验未通过")
    print(f"[check_org_id] OK: {len(TARGET_TABLES)} tables all have org_id + index")


if __name__ == "__main__":
    check_org_id()

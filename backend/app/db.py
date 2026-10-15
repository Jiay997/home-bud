# -*- coding: utf-8 -*-
"""数据库引擎与会话管理模块。

提供 SQLAlchemy engine、会话工厂与 FastAPI 依赖注入的会话生成器。
"""
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .core.config import get_settings

# 全局引擎：连接池按开发环境小规模配置
_engine = None
_SessionLocal = None


def get_engine():
    """获取（懒创建）全局数据库引擎。

    Returns:
        SQLAlchemy Engine 实例。

    Raises:
        Exception: 数据库连接串非法或数据库不可达时由底层抛出。
    """
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory():
    """获取会话工厂。

    Returns:
        sessionmaker 实例。
    """
    get_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：请求级数据库会话。

    Yields:
        SQLAlchemy Session。

    Raises:
        Exception: 会话创建失败时向上抛出由全局处理器包装。
    """
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connected() -> bool:
    """健康检查：验证数据库连通。

    Returns:
        连通返回 True，否则 False。
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

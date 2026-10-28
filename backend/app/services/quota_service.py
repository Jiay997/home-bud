# -*- coding: utf-8 -*-
"""免费额度服务模块。

QuotaUsage 表为服务端唯一裁决入口（数据模型 §3.5）：
- biz_date 按 Asia/Shanghai 自然日（UTC+8 固定偏移，无夏令时）；
- 会员不受免费额度限制；免费用户 used>=limit 预检拒绝（不预扣）；
- 计次规则（PRD §12.5）：正常生成与申诉放行后重提计次；
  失败/被拦截/缓存命中/重连重试不计次。
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import ApiError, ERR_QUOTA_EXHAUSTED
from ..models import AppUser, QuotaUsage

# 上海时区（UTC+8 固定偏移；规避 Windows tzdata 依赖）
_TZ_SHANGHAI = timezone(timedelta(hours=8))


class QuotaService:
    """免费额度服务：当日行获取/预检/原子计次。"""

    @staticmethod
    def biz_date_today() -> date:
        """获取当前业务日期（Asia/Shanghai 自然日）。

        Returns:
            date 对象。
        """
        return datetime.now(_TZ_SHANGHAI).date()

    @staticmethod
    def seconds_until_reset() -> int:
        """距次日 0 点（Asia/Shanghai）的重置秒数。

        Returns:
            整数秒（额度拒绝响应的 retry_after）。
        """
        now = datetime.now(_TZ_SHANGHAI)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return max(1, int((tomorrow - now).total_seconds()))

    @staticmethod
    def is_member(user: AppUser) -> bool:
        """判定用户是否享受会员权益（状态 + 到期时间双检）。

        Args:
            user: 当前用户 ORM 实例。

        Returns:
            会员有效返回 True。
        """
        if user.member_status != "member":
            return False
        expire = user.member_expire_at
        if expire is None:
            return True
        # 兼容 naive/aware 两种存储形态
        if expire.tzinfo is None:
            expire = expire.replace(tzinfo=timezone.utc)
        return expire > datetime.now(timezone.utc)

    @staticmethod
    def get_or_create_today(db: Session, user: AppUser) -> QuotaUsage:
        """获取（或初始化）用户当日额度行。

        Args:
            db: 数据库会话。
            user: 当前用户。

        Returns:
            QuotaUsage ORM 实例（biz_date=今天；limit_snapshot 取配置）。
        """
        today = QuotaService.biz_date_today()
        limit = get_settings().free_quota_daily
        row = (
            db.query(QuotaUsage)
            .filter(QuotaUsage.user_id == user.id, QuotaUsage.biz_date == today)
            .first()
        )
        if row is None:
            # 并发首查：多个请求同时插入会撞 uk_quota 唯一约束，导致 500/1902。
            # 使用 ON CONFLICT DO NOTHING 让失败方等待赢家提交后复用其行。
            db.execute(
                pg_insert(QuotaUsage)
                .values(
                    user_id=user.id,
                    biz_date=today,
                    used_count=0,
                    limit_snapshot=limit,
                    is_member=QuotaService.is_member(user),
                )
                .on_conflict_do_nothing(index_elements=["user_id", "biz_date"])
            )
            db.flush()
            row = (
                db.query(QuotaUsage)
                .filter(QuotaUsage.user_id == user.id, QuotaUsage.biz_date == today)
                .one()
            )
        return row

    @staticmethod
    def quota_check(db: Session, user: AppUser) -> dict:
        """额度预检（不扣减）。

        会员直接放行；免费用户 used>=limit 抛 1202 并附重置秒数。

        Args:
            db: 数据库会话。
            user: 当前用户。

        Returns:
            {"used": int, "limit": int, "is_member": bool, "allowed": bool,
            "retry_after": int|None}。

        Raises:
            ApiError: 1202 免费额度用尽（http 429，retry_after=次日 0 点秒数）。
        """
        member = QuotaService.is_member(user)
        row = QuotaService.get_or_create_today(db, user)
        limit = row.limit_snapshot or get_settings().free_quota_daily
        if member:
            return {
                "used": row.used_count,
                "limit": limit,
                "is_member": True,
                "allowed": True,
                "retry_after": None,
            }
        if row.used_count >= limit:
            raise ApiError(
                code=ERR_QUOTA_EXHAUSTED[0],
                message=ERR_QUOTA_EXHAUSTED[1],
                http_status=ERR_QUOTA_EXHAUSTED[2],
                retryable=True,
                retry_after=QuotaService.seconds_until_reset(),
            )
        return {
            "used": row.used_count,
            "limit": limit,
            "is_member": False,
            "allowed": True,
            "retry_after": None,
        }

    @staticmethod
    def increment(db: Session, user: AppUser) -> int:
        """额度计次（原子自增，只在成功生成后调用）。

        Args:
            db: 数据库会话。
            user: 当前用户。

        Returns:
            自增后的 used_count。
        """
        member = QuotaService.is_member(user)
        row = QuotaService.get_or_create_today(db, user)
        # 会员不计次（行保留用于观测）
        if member:
            return row.used_count
        # 原子自增避免并发丢失更新（synchronize_session=False：禁止 ORM 把
        # DB 新值同步进对象，否则下方 Python 侧 +1 会基于新值二次自增）
        db.execute(
            update(QuotaUsage)
            .where(QuotaUsage.id == row.id)
            .values(
                used_count=QuotaUsage.used_count + 1,
                updated_at=datetime.now(_TZ_SHANGHAI),
            )
            .execution_options(synchronize_session=False)
        )
        row.used_count = row.used_count + 1
        db.flush()
        return row.used_count

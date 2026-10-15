# -*- coding: utf-8 -*-
"""缓存/限流/额度抽象（CacheStore + RedisCacheStore）。

spec D5/D2：键语义对齐数据模型文档 §5.2 的 Redis 键设计。
- CacheStore：进程内线程安全 TTL 实现（默认回退实现）
- RedisCacheStore：redis-py 可选实现（REDIS_URL 配置时启用）
- get_cache()：工厂——尝试 Redis，失败自动回退进程内并告警；
  模块级单例 `cache` 保持既有 `from app.core.cache import cache` 引用兼容。
"""
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("jiaban.cache")


class CacheStore:
    """线程安全的进程内 TTL 缓存。

    支持字符串值的 set/get/incr 与计数过期，
    覆盖额度计数、限流计数、开关热读、词库快照、活跃会话等键位。
    """

    def __init__(self) -> None:
        """初始化空缓存与读写锁。"""
        self._data: dict = {}
        self._expire_at: dict = {}
        self._lock = threading.RLock()

    def _alive(self, key: str) -> bool:
        """检查键是否存在且未过期（内部方法，调用方需持锁）。

        Args:
            key: 缓存键。

        Returns:
            存活返回 True。
        """
        exp = self._expire_at.get(key)
        if exp is not None and exp < time.time():
            # 惰性淘汰过期键
            self._data.pop(key, None)
            self._expire_at.pop(key, None)
            return False
        return key in self._data

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        """写入键值。

        Args:
            key: 缓存键。
            value: 字符串值。
            ttl_seconds: 过期秒数；None 表示永不过期。
        """
        with self._lock:
            self._data[key] = value
            self._expire_at[key] = (
                time.time() + ttl_seconds if ttl_seconds else None
            )

    def get(self, key: str) -> Optional[str]:
        """读取键值。

        Args:
            key: 缓存键。

        Returns:
            存在且未过期返回值，否则 None。
        """
        with self._lock:
            if self._alive(key):
                return self._data[key]
            return None

    def delete(self, key: str) -> None:
        """删除键。

        Args:
            key: 缓存键。
        """
        with self._lock:
            self._data.pop(key, None)
            self._expire_at.pop(key, None)

    def incr(self, key: str, ttl_seconds: Optional[int] = None) -> int:
        """原子自增计数（限流/额度）。

        首次创建时设置 TTL；返回自增后的值。

        Args:
            key: 计数键。
            ttl_seconds: 首次创建时的过期秒数。

        Returns:
            自增后的整数值。
        """
        with self._lock:
            if not self._alive(key):
                self._data[key] = "0"
                if ttl_seconds:
                    self._expire_at[key] = time.time() + ttl_seconds
            self._data[key] = str(int(self._data[key]) + 1)
            return int(self._data[key])

    def get_int(self, key: str) -> int:
        """以整数读取计数键。

        Args:
            key: 计数键。

        Returns:
            整数值；键不存在或非数字返回 0。
        """
        val = self.get(key)
        try:
            return int(val) if val is not None else 0
        except ValueError:
            return 0


class RedisCacheStore(CacheStore):
    """Redis 缓存实现（与 CacheStore 同接口）。

    redis-py 为可选依赖：导入失败或连接不可达时由 get_cache() 回退。
    """

    def __init__(self, redis_url: str) -> None:
        """初始化 Redis 客户端。

        Args:
            redis_url: 形如 redis://localhost:6379/0 的连接串。

        Raises:
            ImportError: redis 包未安装。
            Exception: 连接失败（由 get_cache 捕获回退）。
        """
        import redis  # 延迟导入：可选依赖

        self._client = redis.Redis.from_url(
            redis_url, decode_responses=True, socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._client.ping()  # 立即探活，失败向上抛由工厂回退

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        """写入键值（SETEX/SET）。

        Args:
            key: 缓存键。
            value: 字符串值。
            ttl_seconds: 过期秒数；None 表示永不过期。
        """
        self._client.set(key, value, ex=ttl_seconds)

    def get(self, key: str) -> Optional[str]:
        """读取键值（GET）。

        Args:
            key: 缓存键。

        Returns:
            存在返回值，否则 None。
        """
        return self._client.get(key)

    def delete(self, key: str) -> None:
        """删除键（DEL）。

        Args:
            key: 缓存键。
        """
        self._client.delete(key)

    def incr(self, key: str, ttl_seconds: Optional[int] = None) -> int:
        """原子自增（INCR + 首次 EXPIRE）。

        Args:
            key: 计数键。
            ttl_seconds: 首次创建时的过期秒数。

        Returns:
            自增后的整数值。
        """
        val = self._client.incr(key)
        if val == 1 and ttl_seconds:
            self._client.expire(key, ttl_seconds)
        return int(val)

    def get_int(self, key: str) -> int:
        """以整数读取计数键。

        Args:
            key: 计数键。

        Returns:
            整数值；键不存在返回 0。
        """
        val = self._client.get(key)
        try:
            return int(val) if val is not None else 0
        except (ValueError, TypeError):
            return 0


# Redis 回退原因（进程级记录：避免每次请求重试连接）
_fallback_reason: Optional[str] = None


def get_cache() -> CacheStore:
    """缓存工厂：按配置选择 Redis 或进程内实现。

    读取 settings.redis_url（pydantic-settings：环境变量优先、其次 .env 文件；
    注意不可用 os.environ——.env 文件值不会写入进程环境变量）；未配置或
    连接失败一律回退进程内实现，回退原因记入模块级 _fallback_reason 并打
    告警日志（仅首次）。

    Returns:
        CacheStore 或 RedisCacheStore 实例。
    """
    global _fallback_reason

    from .config import get_settings

    redis_url = (get_settings().redis_url or "").strip()
    if redis_url and _fallback_reason is None:
        try:
            store = RedisCacheStore(redis_url)
            logger.info("cache backend: redis (%s)", redis_url)
            return store
        except Exception as exc:  # noqa: BLE001 — 可选依赖失败不阻断启动
            _fallback_reason = str(exc)
            logger.warning(
                "cache backend fallback to in-memory: redis unavailable (%s)", exc
            )
    elif not redis_url and _fallback_reason is None:
        _fallback_reason = "REDIS_URL not configured"
        logger.warning(
            "cache backend fallback to in-memory: REDIS_URL not configured"
        )
    return CacheStore()


# 模块级单例：经 get_cache() 工厂创建——REDIS_URL 配置且可达时为
# RedisCacheStore（额度/限流/快照键位真实写入 Redis），未配置或连接失败
# 自动回退进程内实现（失败原因进程级固化，重启后端方可重试）。保持既有
# `from app.core.cache import cache` 引用兼容，业务调用点零改动。
cache = get_cache()

# -*- coding: utf-8 -*-
"""Redis 缓存层测试（可选依赖，无 Redis 环境自动 skip）。

覆盖：
- RedisCacheStore：set/get/incr/get_int 与键删除（需可用 Redis 实例，
  先探测 REDIS_URL 或本机 TCP 6379，不可达则 skip 整组用例）；
- get_cache() 工厂：REDIS_URL 指向不可达地址时回退进程内 CacheStore
  并记录告警日志（不污染全局单例 cache，模块状态用 monkeypatch 恢复）。
"""
import logging
import os
import socket
from urllib.parse import urlparse
from uuid import uuid4

import pytest

# redis 为可选依赖：未安装则整模块 skip（不阻塞其余测试）
pytest.importorskip("redis", reason="redis 包未安装（可选依赖）")

from app.core import cache as cache_module  # noqa: E402
from app.core.cache import CacheStore, RedisCacheStore  # noqa: E402


def _probe_redis_url():
    """探测可用 Redis 实例，返回连接串或 None。

    探测顺序：环境变量 REDIS_URL（含本机默认 redis://127.0.0.1:6379/0），
    解析出 host/port 后做 TCP 连通性探测（0.5s 超时）。

    Returns:
        可达时返回 Redis 连接串；不可达或地址非法返回 None。
    """
    url = os.environ.get("REDIS_URL", "").strip() or "redis://127.0.0.1:6379/0"
    parsed = urlparse(url)
    if parsed.scheme not in ("redis", "rediss"):
        return None
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return url
    except OSError:
        return None


@pytest.fixture(scope="module")
def redis_url():
    """模块级夹具：探测可用 Redis，不可达则 skip 整组集成用例。

    Yields:
        可达的 Redis 连接串。

    Raises:
        pytest.skip: Redis 不可达（未配置且本机 6379 无实例）。
    """
    url = _probe_redis_url()
    if url is None:
        pytest.skip("Redis 不可达（未配置 REDIS_URL 且本机 6379 无实例），跳过 Redis 集成测试")
    yield url


class TestRedisCacheStore:
    """RedisCacheStore 行为测试（需要可用 Redis 实例）。"""

    def test_set_get_incr_get_int_and_delete(self, redis_url):
        """set/get/incr/get_int 生效且键可删除（含 TTL 语义）。

        Args:
            redis_url: 探测可达的 Redis 连接串夹具。

        Returns:
            None。

        Raises:
            AssertionError: 任一缓存操作结果与预期不符。
        """
        store = RedisCacheStore(redis_url)
        # 随机前缀避免污染实例上的其他键
        prefix = f"test:redis_cache:{uuid4().hex}"
        try:
            store.set(f"{prefix}:k", "v1", ttl_seconds=60)
            assert store.get(f"{prefix}:k") == "v1"
            # 原子自增：首次创建=1，续增=2
            assert store.incr(f"{prefix}:cnt", ttl_seconds=60) == 1
            assert store.incr(f"{prefix}:cnt") == 2
            assert store.get_int(f"{prefix}:cnt") == 2
        finally:
            store.delete(f"{prefix}:k")
            store.delete(f"{prefix}:cnt")
        # 删除后读取应返回空/0
        assert store.get(f"{prefix}:k") is None
        assert store.get_int(f"{prefix}:cnt") == 0


class TestGetCacheFallback:
    """get_cache() 工厂回退语义测试（不需要可用 Redis）。"""

    def test_fallback_to_in_memory_on_unreachable(self, monkeypatch, caplog):
        """REDIS_URL 指向不可达地址时回退进程内 CacheStore 并告警。

        用 monkeypatch 设置不可达地址并重置模块级回退标记（测后自动恢复），
        全局单例 cache 不被触碰；断言返回实例类型与告警日志。

        Args:
            monkeypatch: pytest 夹具（环境变量/模块属性打补丁）。
            caplog: pytest 日志捕获夹具。

        Returns:
            None。

        Raises:
            AssertionError: 回退类型不符或告警日志缺失。
        """
        # 重置回退标记，强制 get_cache 走"尝试 Redis → 失败回退"分支
        monkeypatch.setattr(cache_module, "_fallback_reason", None)
        # 端口 1 几乎必然无监听，等价"不可达实例"
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
        with caplog.at_level(logging.WARNING, logger="jiaban.cache"):
            store = cache_module.get_cache()
        # 回退实现必须是进程内 CacheStore（而非其 Redis 子类）
        assert type(store) is CacheStore
        assert not isinstance(store, RedisCacheStore)
        # 回退时必须记录告警日志
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings, "回退进程内缓存时应记录 logging.warning 告警"

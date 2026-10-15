# -*- coding: utf-8 -*-
"""横切基础设施单测：缓存回退 / 密钥轮换 / org_id 声明（spec close-module-gaps Task 1）。

不依赖 Redis 服务与真实库连接（org_id 部分只断言 ORM 声明，
实际建库校验由 scripts/check_org_id.py 承担）。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# 缓存回退
# ---------------------------------------------------------------------------
class TestCacheFallback:
    """get_cache() 工厂回退行为。"""

    def test_fallback_without_redis_url(self, monkeypatch):
        """REDIS_URL 为空时返回进程内 CacheStore 且行为正确。"""
        from app.core.cache import CacheStore, get_cache

        monkeypatch.setenv("REDIS_URL", "")
        store = get_cache()
        assert isinstance(store, CacheStore)
        # 基础读写语义
        store.set("k1", "v1", ttl_seconds=60)
        assert store.get("k1") == "v1"
        assert store.incr("c1") == 1
        assert store.incr("c1") == 2
        assert store.get_int("c1") == 2
        store.delete("k1")
        assert store.get("k1") is None

    def test_fallback_on_unreachable_redis(self, monkeypatch):
        """REDIS_URL 指向不可达地址时回退进程内实现，不抛异常。"""
        from app.core.cache import CacheStore, get_cache

        # 重置进程级回退标记，强制重新探测
        import app.core.cache as cache_mod

        monkeypatch.setattr(cache_mod, "_fallback_reason", None)
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:59999/0")  # 无服务端口
        store = get_cache()
        assert isinstance(store, CacheStore)
        # 回退原因被记录（异常消息非空即视为已回退并告警）
        assert cache_mod._fallback_reason

    def test_module_level_cache_still_works(self):
        """既有 `from app.core.cache import cache` 引用兼容。"""
        from app.core.cache import cache

        cache.set("compat", "1")
        assert cache.get("compat") == "1"
        cache.delete("compat")


# ---------------------------------------------------------------------------
# 密钥轮换
# ---------------------------------------------------------------------------
class TestKeyRotation:
    """密文版本前缀与多版本解密。"""

    def _reload_crypto(self, monkeypatch, current: str, old: str):
        """以指定密钥配置重建 crypto 模块缓存。

        Args:
            current: 当前密钥。
            old: 历史密钥（逗号分隔）。
        """
        import app.core.crypto as crypto

        monkeypatch.setenv("FIELD_ENC_KEY", current)
        monkeypatch.setenv("FIELD_ENC_KEYS_OLD", old)
        crypto._fernet_cache.clear()
        # settings 是 lru_cache 单例——直接改实例属性
        s = crypto.get_settings()
        s.field_enc_key = current
        s.field_enc_keys_old = old
        return crypto

    def test_encrypt_has_version_prefix(self, monkeypatch):
        """新加密密文带 v1: 前缀（无历史密钥时当前版本=1）。"""
        crypto = self._reload_crypto(monkeypatch, "keyA", "")
        ct = crypto.encrypt_field("hello")
        assert ct.startswith("v1:")
        assert crypto.decrypt_field(ct) == "hello"

    def test_rotation_old_ciphertext_readable(self, monkeypatch):
        """轮换后旧密文按 v1 历史密钥可读，新写入用 v2。"""
        # 阶段1：v1 密钥 keyA 加密
        crypto = self._reload_crypto(monkeypatch, "keyA", "")
        ct_v1 = crypto.encrypt_field("秘密数据")

        # 阶段2：轮换——keyA 变历史，keyB 变当前
        crypto = self._reload_crypto(monkeypatch, "keyB", "keyA")
        # 旧密文可读
        assert crypto.decrypt_field(ct_v1) == "秘密数据"
        # 新写入带 v2 前缀
        ct_v2 = crypto.encrypt_field("新数据")
        assert ct_v2.startswith("v2:")
        assert crypto.decrypt_field(ct_v2) == "新数据"

    def test_legacy_unprefixed_ciphertext(self, monkeypatch):
        """无前缀旧格式密文按 v1 兼容解密。"""
        crypto = self._reload_crypto(monkeypatch, "keyA", "")
        # 手工构造 v1 旧格式密文（无前缀）
        from cryptography.fernet import Fernet
        import base64, hashlib

        raw = hashlib.sha256(b"keyA").digest()
        f = Fernet(base64.urlsafe_b64encode(raw))
        legacy_ct = f.encrypt("旧格式".encode()).decode()
        assert crypto.decrypt_field(legacy_ct) == "旧格式"

    def test_reencrypt_upgrades_version(self, monkeypatch):
        """reencrypt_field 将旧版本密文升级为当前版本。"""
        crypto = self._reload_crypto(monkeypatch, "keyA", "")
        ct_v1 = crypto.encrypt_field("数据")
        crypto = self._reload_crypto(monkeypatch, "keyB", "keyA")
        upgraded = crypto.reencrypt_field(ct_v1)
        assert upgraded.startswith("v2:")
        assert crypto.decrypt_field(upgraded) == "数据"


# ---------------------------------------------------------------------------
# org_id 声明
# ---------------------------------------------------------------------------
class TestOrgIdDeclaration:
    """五张主表 ORM 声明含 org_id（建库校验由 check_org_id.py 承担）。"""

    def test_five_tables_have_org_id_column(self):
        """AppUser/ChildProfile/PetProfile/QaSession/Report 均含 org_id 列。"""
        from app.models import AppUser, ChildProfile, PetProfile, QaSession, Report

        for model in (AppUser, ChildProfile, PetProfile, QaSession, Report):
            cols = model.__table__.columns.keys()
            assert "org_id" in cols, f"{model.__tablename__} missing org_id"

    def test_org_id_indexes_declared(self):
        """五表 __table_args__ 声明 idx_<table>_org_id 索引。"""
        from app.models import AppUser, ChildProfile, PetProfile, QaSession, Report

        for model in (AppUser, ChildProfile, PetProfile, QaSession, Report):
            idx_names = {i.name for i in model.__table__.indexes}
            assert f"idx_{model.__tablename__}_org_id" in idx_names, (
                f"{model.__tablename__} missing org_id index"
            )

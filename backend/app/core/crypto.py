# -*- coding: utf-8 -*-
"""敏感字段加密模块（CryptoProvider 抽象：本地 Fernet / KMS 信封加密 + 密钥轮换）。

架构文档 T-3 / spec D4：密钥与数据分离、可轮换、解密可审计。

Provider 体系（Task 3.3：配置即切）：
- CryptoProvider 抽象：encrypt_field / decrypt_field / reencrypt_field 同签名；
- LocalFernetProvider（默认）：包装既有本地 Fernet + 轮换逻辑（既有密文
  无需迁移，Local 路径输出格式不变）；
  - 密文格式：`v{N}:{fernet_token}`（N = 加密时的密钥版本）
  - 写路径恒用当前（最新版）密钥；读路径按前缀选密钥；旧格式（无前缀）
    按 v1 历史密钥兼容解密；
- KmsEnvelopeProvider：KMS 信封加密语义——配置的主密钥句柄 KEK 经可插拔
  接口（KekAdapter）获取数据密钥 DEK，DEK 以 AES-256-GCM 加密字段，密文
  头带 provider 标记（kms1:）与 DEK id；KEK 获取接口为适配点，本模块内置
  基于环境变量主密钥（KMS_MASTER_KEY）的本地实现（EnvVarKekAdapter）使其
  可测试、可离线运行；接云 KMS（如阿里云 KMS GenerateDataKey/Decrypt 或
  AWS KMS）时仅需实现 KekAdapter 并注册，无需改动调用方。
  - 密文格式：`kms1:{dek_id}:{nonce_b64}:{ciphertext_b64}`；
  - DEK id 本地实现为自包含句柄（KEK 包裹后的 DEK 编码进 id）；云实现为
    密钥 ID（wrapped DEK 由 KMS 保管），密文结构不变；
  - 兼容性：kms 通道解密时对既有 `v{N}:` 格式自动回退本地实现（先切配置
    再跑轮换脚本即可全量迁移到信封格式）；模块级 decrypt_field 对 kms1:
    密文恒走信封解密（反向迁移同样支持）。

分发：get_crypto_provider() 按 settings.crypto_provider 分发（local 默认 /
kms）；模块级 encrypt_field / decrypt_field / reencrypt_field 委托 Provider，
既有调用点（auth_api、rotate_field_key.py 等）零改动即获得配置即切能力。
"""
import base64
import hashlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

logger = logging.getLogger("jiaban.crypto")

# 解密审计回调：由调用方（依赖注入）注册，记录(字段, 对象, 操作人, 原因)
_decrypt_audit_hook = None

# 密钥缓存（进程级：版本 → Fernet 实例）
_fernet_cache: Dict[int, Fernet] = {}

# KMS 信封密文头标记（provider 标识 + 格式版本）
KMS_PREFIX = "kms1:"

# DEK 包裹时的关联数据（KEK 与 DEK 绑定域分隔，防跨用途重放）
_KEK_AAD = b"jiaban-kms-envelope-dek"


class CryptoConfigError(Exception):
    """字段加密通道配置缺失异常（如 CRYPTO_PROVIDER=kms 但 KMS_MASTER_KEY 未配置）。

    Attributes:
        message: 人类可读的缺失项描述（一次性列全全部缺失配置项）。
    """

    pass


# ---------------------------------------------------------------------------
# 本地 Fernet 实现（既有逻辑，抽为内部函数供 LocalFernetProvider 包装）
# ---------------------------------------------------------------------------
def _key_to_fernet(raw: str) -> Fernet:
    """将任意字符串密钥派生为合法 Fernet 实例。

    用 SHA-256 派生 32 字节密钥，避免开发环境手工构造 base64 失败。

    Args:
        raw: 原始密钥字符串。

    Returns:
        Fernet 加解密实例。
    """
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _get_fernet_by_version(version: int) -> Fernet:
    """获取指定版本的 Fernet 实例（带进程级缓存）。

    版本映射规则：
    - v{n}（n < 当前版本）对应 FIELD_ENC_KEYS_OLD 逗号分隔列表的第 n 项
    - 当前版本对应 FIELD_ENC_KEY

    Args:
        version: 密钥版本号（从 1 开始）。

    Returns:
        对应版本的 Fernet 实例。

    Raises:
        ValueError: 版本号超出可用范围（密钥缺失）。
    """
    if version in _fernet_cache:
        return _fernet_cache[version]

    settings = get_settings()
    old_keys = [k.strip() for k in settings.field_enc_keys_old.split(",") if k.strip()]
    current_version = len(old_keys) + 1

    if version < current_version:
        raw = old_keys[version - 1]
    elif version == current_version:
        raw = settings.field_enc_key
    else:
        raise ValueError(f"field enc key v{version} not configured")

    f = _key_to_fernet(raw)
    _fernet_cache[version] = f
    return f


def current_key_version() -> int:
    """返回当前（最新）密钥版本号。

    Returns:
        版本号 = 历史密钥数 + 1。
    """
    settings = get_settings()
    old_keys = [k.strip() for k in settings.field_enc_keys_old.split(",") if k.strip()]
    return len(old_keys) + 1


def _local_encrypt_field(plaintext: str) -> str:
    """本地通道加密敏感字段明文（恒用当前最新版密钥）。

    Args:
        plaintext: 明文内容（不可为 None）。

    Returns:
        密文字符串，格式 `v{N}:{token}`，可直接落库。

    Raises:
        ValueError: 明文为 None。
    """
    if plaintext is None:
        raise ValueError("encrypt_field: plaintext must not be None")
    token = _get_fernet_by_version(current_key_version()).encrypt(
        plaintext.encode("utf-8")
    ).decode("utf-8")
    return f"v{current_key_version()}:{token}"


def _local_decrypt_field(ciphertext: str) -> str:
    """本地通道解密敏感字段密文（按前缀选密钥；旧格式按 v1 兼容）。

    Args:
        ciphertext: 库中密文字符串（`v{N}:{token}` 或旧格式纯 token）。

    Returns:
        明文内容。

    Raises:
        ValueError: 密文为空或版本号未配置。
        InvalidToken: 密文损坏或密钥不匹配。
    """
    if not ciphertext:
        raise ValueError("decrypt_field: ciphertext must not be empty")
    if ciphertext.startswith("v") and ":" in ciphertext:
        prefix, token = ciphertext.split(":", 1)
        version = int(prefix[1:])
        return _get_fernet_by_version(version).decrypt(token.encode("utf-8")).decode("utf-8")
    # 旧格式（无前缀）：按 v1 历史密钥兼容解密
    return _get_fernet_by_version(1).decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# CryptoProvider 抽象与两个实现
# ---------------------------------------------------------------------------
class CryptoProvider(ABC):
    """敏感字段加解密 Provider 抽象（encrypt/decrypt/reencrypt 同签名）。

    约定：
    - encrypt_field 输出格式由实现自描述（密文头带 provider 标记）；
    - decrypt_field 对非本通道格式显式抛 ValueError（模块级分发已做跨
      格式路由，实现内部只需处理自有格式与遗留兼容）；
    - reencrypt_field = decrypt + encrypt（轮换写回用）。
    """

    @abstractmethod
    def encrypt_field(self, plaintext: str) -> str:
        """加密敏感字段明文。

        Args:
            plaintext: 明文内容（不可为 None）。

        Returns:
            密文字符串（可直接落库）。

        Raises:
            ValueError: 明文为 None 等非法输入。
        """
        raise NotImplementedError

    @abstractmethod
    def decrypt_field(self, ciphertext: str) -> str:
        """解密敏感字段密文。

        Args:
            ciphertext: 库中密文字符串。

        Returns:
            明文内容。

        Raises:
            ValueError: 密文为空/格式未知/版本未配置。
        """
        raise NotImplementedError

    @abstractmethod
    def reencrypt_field(self, ciphertext: str) -> str:
        """将旧密文重加密为当前通道当前密钥格式（轮换写回用）。

        Args:
            ciphertext: 库中旧密文。

        Returns:
            当前通道当前版本密文。

        Raises:
            ValueError: 旧密文无法解密。
        """
        raise NotImplementedError


class LocalFernetProvider(CryptoProvider):
    """本地 Fernet 实现（默认）：包装既有 v{N}: 前缀多密钥轮换逻辑。

    输出格式与既有实现完全一致（`v{N}:{token}`），既有密文无需迁移；
    配置 crypto_provider=local（或缺省）时全系统走本实现。
    """

    def encrypt_field(self, plaintext: str) -> str:
        """加密敏感字段明文（本地 Fernet，当前版本密钥）。

        Args:
            plaintext: 明文内容（不可为 None）。

        Returns:
            密文字符串 `v{N}:{token}`。

        Raises:
            ValueError: 明文为 None。
        """
        return _local_encrypt_field(plaintext)

    def decrypt_field(self, ciphertext: str) -> str:
        """解密敏感字段密文（本地 Fernet，按版本前缀选密钥）。

        Args:
            ciphertext: 库中密文（`v{N}:{token}` 或旧格式纯 token）。

        Returns:
            明文内容。

        Raises:
            ValueError: 密文为空或版本号未配置。
            InvalidToken: 密文损坏或密钥不匹配。
        """
        return _local_decrypt_field(ciphertext)

    def reencrypt_field(self, ciphertext: str) -> str:
        """将旧版本密文重加密为当前版本（轮换写回用）。

        Args:
            ciphertext: 库中旧密文。

        Returns:
            当前版本密文（`v{CUR}:{token}`）。

        Raises:
            InvalidToken: 旧密文无法用任何已配置密钥解密。
        """
        return self.encrypt_field(self.decrypt_field(ciphertext))


class KekAdapter(ABC):
    """KEK（主密钥）获取适配点（KMS 信封加密的可插拔接口）。

    语义对齐云 KMS GenerateDataKey / Decrypt：
    - generate_data_key：生成新 DEK，返回 (dek_id, dek 明文)；dek_id 为
      可回溯句柄——云实现为密钥 ID（wrapped DEK 由 KMS 保管），本地实现
      将 KEK 包裹后的 DEK 自包含编入句柄；
    - decrypt_data_key：由 dek_id 还原 DEK 明文（云实现调 KMS Decrypt）。

    接云 KMS 时实现本接口并在 KmsEnvelopeProvider 注入即可，调用方零改动。
    """

    @abstractmethod
    def generate_data_key(self) -> Tuple[str, bytes]:
        """生成新数据密钥（DEK）。

        Returns:
            (dek_id, dek_bytes) 二元组；dek_id 须能被 decrypt_data_key 还原。

        Raises:
            CryptoConfigError: 主密钥未配置。
        """
        raise NotImplementedError

    @abstractmethod
    def decrypt_data_key(self, dek_id: str) -> bytes:
        """由句柄还原 DEK 明文。

        Args:
            dek_id: generate_data_key 返回的句柄。

        Returns:
            DEK 明文字节（32 字节）。

        Raises:
            ValueError: 句柄非法或 KEK 不匹配（无法解包）。
            CryptoConfigError: 主密钥未配置。
        """
        raise NotImplementedError


class EnvVarKekAdapter(KekAdapter):
    """基于环境变量主密钥（KMS_MASTER_KEY）的本地 KEK 实现（可测试运行）。

    KEK = SHA-256(KMS_MASTER_KEY)；DEK 句柄自包含：
        dek_id = "env1:" + urlsafe_b64(nonce(12B) || KEK 包裹后的 DEK)
    语义与云 KMS 对齐（句柄→DEK 明文），差异仅在 wrapped DEK 的存放位置
    （句柄内 vs KMS 侧），密文结构与调用方均无感知。

    Attributes:
        _master_key: 主密钥原文（None 时从 settings.kms_master_key 读取）。
    """

    # 句柄版本前缀（格式演进留位；不含冒号——外层密文以 ":" 分段，
    # 句柄须为单段安全字符：urlsafe_base64 字母表 + "=" padding）
    _HANDLE_PREFIX = "env1_"

    def __init__(self, master_key: Optional[str] = None) -> None:
        """初始化适配器。

        Args:
            master_key: 主密钥原文；缺省从 settings.kms_master_key 读取
            （便于测试注入独立密钥）。
        """
        self._master_key = master_key

    def _kek(self) -> bytes:
        """派生 KEK（32 字节）。

        Returns:
            KEK 字节（SHA-256 摘要）。

        Raises:
            CryptoConfigError: KMS_MASTER_KEY 未配置（一次性点名缺失项）。
        """
        master = self._master_key or get_settings().kms_master_key
        if not master:
            raise CryptoConfigError("kms crypto credentials not configured: KMS_MASTER_KEY")
        return hashlib.sha256(master.encode("utf-8")).digest()

    def generate_data_key(self) -> Tuple[str, bytes]:
        """生成随机 DEK 并以 KEK 包裹，句柄自包含 wrapped DEK。

        Returns:
            (dek_id, dek_bytes)：dek_id = "env1:" + b64(nonce||wrapped)。

        Raises:
            CryptoConfigError: 主密钥未配置。
        """
        dek = os.urandom(32)
        nonce = os.urandom(12)
        wrapped = AESGCM(self._kek()).encrypt(nonce, dek, _KEK_AAD)
        dek_id = self._HANDLE_PREFIX + base64.urlsafe_b64encode(nonce + wrapped).decode("utf-8")
        return dek_id, dek

    def decrypt_data_key(self, dek_id: str) -> bytes:
        """解析句柄并以 KEK 解包还原 DEK 明文。

        Args:
            dek_id: "env1_" 前缀的自包含句柄。

        Returns:
            DEK 明文字节。

        Raises:
            ValueError: 句柄格式非法或 KEK 不匹配（解包失败）。
            CryptoConfigError: 主密钥未配置。
        """
        if not dek_id or not dek_id.startswith(self._HANDLE_PREFIX):
            raise ValueError("invalid dek id: unknown handle format")
        try:
            raw = base64.urlsafe_b64decode(dek_id[len(self._HANDLE_PREFIX):])
            nonce, wrapped = raw[:12], raw[12:]
            return AESGCM(self._kek()).decrypt(nonce, wrapped, _KEK_AAD)
        except InvalidTag as exc:
            # KEK 不匹配（主密钥轮换/配置错误）：明确报错便于排障
            raise ValueError(
                "dek unwrap failed: KMS_MASTER_KEY mismatch or handle corrupted"
            ) from exc


class KmsEnvelopeProvider(CryptoProvider):
    """KMS 信封加密实现：KEK 包裹 DEK，DEK 加密字段（AES-256-GCM）。

    密文格式：`kms1:{dek_id}:{nonce_b64}:{ciphertext_b64}`——密文头带
    provider 标记（kms1:）与 DEK id；dek_id 作为 AES-GCM 关联数据参与
    加解密（头部与密文体绑定，防篡改拆装）。

    兼容性：对既有本地 `v{N}:` 格式（及无前缀旧格式）自动回退本地实现
    解密——先切 CRYPTO_PROVIDER=kms 再跑轮换脚本，即可将存量数据渐进
    迁移为信封格式，既有密文无需一次性迁移。
    """

    # AES-GCM nonce 长度（96 bit，GCM 标准推荐）
    _NONCE_BYTES = 12

    def __init__(self, kek_adapter: Optional[KekAdapter] = None) -> None:
        """初始化信封加密 Provider。

        Args:
            kek_adapter: KEK 获取适配器；缺省使用 EnvVarKekAdapter（基于
            KMS_MASTER_KEY 环境变量主密钥，可离线测试运行）。
        """
        self._adapter = kek_adapter or EnvVarKekAdapter()

    def encrypt_field(self, plaintext: str) -> str:
        """信封加密：生成 DEK → AES-GCM 加密 → 密文头带 provider 标记与 DEK id。

        Args:
            plaintext: 明文内容（不可为 None）。

        Returns:
            密文 `kms1:{dek_id}:{nonce_b64}:{ciphertext_b64}`。

        Raises:
            ValueError: 明文为 None。
            CryptoConfigError: 主密钥未配置。
        """
        if plaintext is None:
            raise ValueError("encrypt_field: plaintext must not be None")
        dek_id, dek = self._adapter.generate_data_key()
        nonce = os.urandom(self._NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(
            nonce, plaintext.encode("utf-8"), dek_id.encode("utf-8")
        )
        return (
            f"{KMS_PREFIX}{dek_id}:"
            f"{base64.b64encode(nonce).decode('utf-8')}:"
            f"{base64.b64encode(ciphertext).decode('utf-8')}"
        )

    def decrypt_field(self, ciphertext: str) -> str:
        """信封解密：解析头部 → 适配器还原 DEK → AES-GCM 解密。

        兼容路径：非 kms1: 格式（本地 `v{N}:` 或旧格式）回退本地实现。

        Args:
            ciphertext: 库中密文。

        Returns:
            明文内容。

        Raises:
            ValueError: 密文为空/格式非法/DEK 解包失败/密文被篡改。
            CryptoConfigError: 主密钥未配置。
        """
        if not ciphertext:
            raise ValueError("decrypt_field: ciphertext must not be empty")
        if not ciphertext.startswith(KMS_PREFIX):
            # 既有本地格式兼容（含 v{N}: 前缀与无前缀旧格式）
            return _local_decrypt_field(ciphertext)
        try:
            body = ciphertext[len(KMS_PREFIX):]
            dek_id, nonce_b64, ct_b64 = body.split(":", 2)
            nonce = base64.b64decode(nonce_b64)
            ct = base64.b64decode(ct_b64)
        except (ValueError, TypeError) as exc:
            raise ValueError("kms envelope ciphertext format invalid") from exc
        dek = self._adapter.decrypt_data_key(dek_id)
        try:
            plaintext = AESGCM(dek).decrypt(
                nonce, ct, dek_id.encode("utf-8")
            )
        except InvalidTag as exc:
            raise ValueError("kms envelope decrypt failed: invalid tag") from exc
        return plaintext.decode("utf-8")

    def reencrypt_field(self, ciphertext: str) -> str:
        """解密（含既有本地格式兼容）后以新 DEK 重加密（轮换写回用）。

        Args:
            ciphertext: 库中旧密文（kms1: 或本地 v{N}: 格式均可）。

        Returns:
            当前信封格式密文（每次生成新 DEK）。

        Raises:
            ValueError: 旧密文无法解密。
        """
        return self.encrypt_field(self.decrypt_field(ciphertext))


# ---------------------------------------------------------------------------
# Provider 分发与模块级委托（既有调用点零改动获得配置即切能力）
# ---------------------------------------------------------------------------
# 本地 Provider 进程级单例（无状态，免重复构造）
_LOCAL_PROVIDER = LocalFernetProvider()


def get_crypto_provider() -> CryptoProvider:
    """按 settings.crypto_provider 分发字段加密 Provider（local 默认 / kms）。

    启动校验语义：crypto_provider='kms' 但 KMS_MASTER_KEY 缺失时显式抛
    CryptoConfigError（一次性列全缺失配置项），不静默回退 local。

    Returns:
        CryptoProvider: 对应实现实例。

    Raises:
        CryptoConfigError: kms 通道缺 KMS_MASTER_KEY，或取值未知时抛出。
    """
    settings = get_settings()
    name = (settings.crypto_provider or "local").strip().lower()
    if name == "local":
        return _LOCAL_PROVIDER
    if name == "kms":
        if not settings.kms_master_key:
            raise CryptoConfigError("kms crypto credentials not configured: KMS_MASTER_KEY")
        return KmsEnvelopeProvider()
    raise CryptoConfigError(f"unknown crypto_provider: {name}")


def register_decrypt_audit_hook(hook) -> None:
    """注册解密审计回调。

    Args:
        hook: 回调函数，签名为 hook(field: str, object_id: str,
            operator: str, reason: str) -> None。
    """
    global _decrypt_audit_hook
    _decrypt_audit_hook = hook


def encrypt_field(plaintext: str) -> str:
    """加密敏感字段明文（委托当前配置 Provider；Local 输出格式不变）。

    Args:
        plaintext: 明文内容（不可为 None）。

    Returns:
        密文字符串（local: `v{N}:{token}`；kms: `kms1:{dek_id}:{nonce}:{ct}`）。

    Raises:
        ValueError: 明文为 None。
        CryptoConfigError: kms 通道缺 KMS_MASTER_KEY。
    """
    return get_crypto_provider().encrypt_field(plaintext)


def decrypt_field(ciphertext: str) -> str:
    """解密敏感字段密文（按配置分发；kms1: 密文恒走信封解密）。

    跨格式路由：kms1: 前缀密文无论当前配置走 local 还是 kms，均经信封
    实现解密（轮换脚本双向迁移依赖此行为）；其余格式交由当前 Provider。

    Args:
        ciphertext: 库中密文字符串。

    Returns:
        明文内容。

    Raises:
        ValueError: 密文为空、格式未知或 DEK 解包失败。
        InvalidToken: local 格式密文损坏或密钥不匹配。
        CryptoConfigError: kms 通道缺 KMS_MASTER_KEY。
    """
    if ciphertext and ciphertext.startswith(KMS_PREFIX):
        # 跨格式兼容：信封密文恒走 KMS 实现（与当前配置无关）
        return KmsEnvelopeProvider().decrypt_field(ciphertext)
    return get_crypto_provider().decrypt_field(ciphertext)


def reencrypt_field(ciphertext: str) -> str:
    """将旧密文重加密为当前配置 Provider 的当前格式（轮换写回用）。

    解密侧经跨格式路由（kms1:/v{N}: 均可读），加密侧恒用当前 Provider——
    轮换脚本在 local / kms 两种配置下均可直接运行。

    Args:
        ciphertext: 库中旧密文。

    Returns:
        当前 Provider 当前格式密文。

    Raises:
        ValueError: 旧密文无法用任何已配置通道解密。
        CryptoConfigError: kms 通道缺 KMS_MASTER_KEY。
    """
    return encrypt_field(decrypt_field(ciphertext))


def decrypt_field_audited(
    ciphertext: str, field: str, object_id: str, operator: str = "-", reason: str = "-"
) -> str:
    """带审计的解密：用于后台敏感字段展开场景。

    Args:
        ciphertext: 库中密文。
        field: 字段名（如 nickname_enc）。
        object_id: 所属对象标识（如 profile_uid）。
        operator: 操作人标识。
        reason: 展开原因（后台必填）。

    Returns:
        明文内容。

    Raises:
        InvalidToken: 密文损坏。
    """
    plaintext = decrypt_field(ciphertext)
    if _decrypt_audit_hook:
        try:
            _decrypt_audit_hook(field, object_id, operator, reason)
        except Exception:  # noqa: BLE001 — 审计回调失败不阻断解密
            logger.exception("decrypt audit hook failed")
    return plaintext


def sha256_hex(value: str) -> str:
    """计算字符串的 SHA-256 十六进制摘要。

    用于 user_id 不可逆哈希（risk_event）、输入摘要（agent_call_log）、
    词条哈希（lexicon_term）等场景。

    Args:
        value: 原始字符串。

    Returns:
        64 位十六进制摘要字符串。
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_phone(phone: str) -> str:
    """手机号脱敏展示。

    Args:
        phone: 完整手机号。

    Returns:
        形如 138****5678 的脱敏值；长度不足时全部打码。
    """
    if not phone or len(phone) < 7:
        return "****"
    return phone[:3] + "****" + phone[-4:]

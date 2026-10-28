# -*- coding: utf-8 -*-
"""API 集成测试夹具（spec Task 6.1/6.2 测试基础设施）。

策略：
- 独立测试数据库 jiaban_test：session 级 fixture 重建库并建表 + 种子数据，
  会话结束 best effort 删库；连接地址与凭据取自 backend/.env 的 DATABASE_URL
  （仅替换库名），源码不硬编码账号密码；
- 在任何 app 包导入前设置 DATABASE_URL 环境变量，保证 app.db 的全局懒加载
  engine 指向测试库（不依赖运行中的 8000 服务）；
- function 级 autouse fixture：每个测试前 TRUNCATE 全部业务表 + 重新种子 +
  清空进程内缓存，保证用例间完全隔离；
- client / user_token / admin_token / llm_mock 等通用夹具。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# ---------------------------------------------------------------------------
# 关键顺序：必须在任何 app.* 导入前覆盖 DATABASE_URL，
# 使 app.core.config.get_settings() 与 app.db 懒加载 engine 指向测试库。
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _env_value(name: str, default: str = "") -> str:
    """读取配置值：进程环境变量优先，其次 backend/.env 文件。

    Args:
        name: 变量名（此处仅用 DATABASE_URL）。
        default: 两处均未配置时的兜底值。

    Returns:
        变量值字符串。
    """
    if os.environ.get(name):
        return os.environ[name]
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


# 复用 backend/.env 的 DATABASE_URL 凭据，仅替换库名；源码不硬编码账号密码
_BASE_DB_URL = _env_value(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/jiaban"
)
TEST_DB_NAME = "jiaban_test"
ADMIN_DB_URL = urlunsplit(urlsplit(_BASE_DB_URL)._replace(path="/postgres"))
TEST_DB_URL = urlunsplit(urlsplit(_BASE_DB_URL)._replace(path=f"/{TEST_DB_NAME}"))

os.environ["DATABASE_URL"] = TEST_DB_URL

# 测试进程强制进程内缓存：显式置空 REDIS_URL（环境变量优先级高于 .env 文件，
# 覆盖开发配置），使 cache 单例为 CacheStore——conftest 的 _clear_cache 依赖
# 进程内私有结构做用例间隔离；Redis 真实链路语义由 test_redis_cache.py 显式
# 探测覆盖（可达即真实跑集成用例），与运行中的 8000 后端（Redis db0）互不串扰。
os.environ["REDIS_URL"] = ""

# 测试进程强制 local 加密通道：同理置位 CRYPTO_PROVIDER（环境变量优先级高于
# .env 文件，覆盖开发配置里的 kms），保证密文格式断言（v{N}: 前缀、轮换版本
# 升级）在 local 基线下确定性通过；kms 信封加密语义由 test_finalize_task3.py
# 用例内显式配置覆盖（dispatch/往返/旧格式兼容等，不依赖进程级默认值）。
os.environ["CRYPTO_PROVIDER"] = "local"

# 测试进程强制 mock 嵌入：显式置位 EMBEDDING_PROVIDER（覆盖开发配置里的
# zhipu），保证 pytest 全量不触网、嵌入跨进程确定性（spec rag-llamaindex-
# migration）；智谱真实链路由 pgvector_gated 集成用例显式探测覆盖。
os.environ["EMBEDDING_PROVIDER"] = "mock"

# 测试进程强制 Milvus 主通道禁用：显式置空 MILVUS_URI（覆盖开发配置里的
# localhost:19531），保证 rag_index.available()=False 走 hashing 降级链
# （spec milvus-vector-store）；Milvus 真实链路由 milvus_gated 集成用例
# 显式探测覆盖（可达即真实跑），测试进程不触真库。
os.environ["MILVUS_URI"] = ""

# 测试进程强制 dev 认证通道：显式置位 AUTH_PROVIDER（覆盖开发配置里的 wx，
# 2026-10-12 阶段 0 微信联调已切换），保证 test_dev_channel_unchanged 的
# 「缺省 dev 不漂移」断言基线稳定；同时置空 WX 凭据，杜绝测试进程内任何
# 意外真实调用微信 API（渠道真实链路由 test_channel_providers.py 用例内
# 显式 monkeypatch 凭据 + MockTransport 覆盖，不依赖进程级默认值）。
os.environ["AUTH_PROVIDER"] = "dev"
os.environ["WX_APPID"] = ""
os.environ["WX_SECRET"] = ""

# 测试进程隔离档案媒体目录：显式置位 UPLOAD_DIR 指向临时目录（环境变量
# 优先级高于 .env 文件），保证媒体用例的上传/删除文件不落开发目录
# backend/data/uploads；app.main 在导入期即挂载 /media 静态目录，故此处置位。
# 沙箱/CI 适配：若外部已显式传入 JIABAN_TEST_UPLOAD_DIR（例如受限环境下
# mkdtemp 生成的目录不可写），优先使用该目录，避免用例因环境级权限失败。
_explicit_upload_dir = os.environ.get("JIABAN_TEST_UPLOAD_DIR", "").strip()
if _explicit_upload_dir:
    Path(_explicit_upload_dir).mkdir(parents=True, exist_ok=True)
    os.environ["UPLOAD_DIR"] = _explicit_upload_dir
else:
    os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="jiaban-uploads-")

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import app.main as app_main  # noqa: E402
from app.core.cache import cache  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import ALL_MODELS, Base  # noqa: E402

# 后台账号种子（与 scripts/seed_data.py 一致）
ADMIN_PASSWORD = "Admin@123456"


# ---------------------------------------------------------------------------
# 测试库生命周期（session 级）
# ---------------------------------------------------------------------------
def _admin_engine():
    """创建连接 postgres 系统库的管理引擎（AUTOCOMMIT，供 DDL 使用）。

    Returns:
        SQLAlchemy Engine 实例。

    Raises:
        Exception: 数据库不可达时由底层抛出。
    """
    return create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")


def _drop_test_db() -> None:
    """删除测试数据库（先断开全部连接再 DROP，兼容 PG 13 以下版本）。

    Returns:
        None。

    Raises:
        Exception: 删除失败时向上抛出（仅 session 收尾调用，失败不致命）。
    """
    eng = _admin_engine()
    try:
        with eng.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": TEST_DB_NAME},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
    finally:
        eng.dispose()


@pytest.fixture(scope="session")
def test_database():
    """session 级测试库夹具：重建 jiaban_test + 全量建表 + 种子数据。

    Yields:
        测试库连接字符串。

    Raises:
        Exception: 建库/建表/种子失败时向上抛出（阻断全部集成测试）。
    """
    _drop_test_db()
    eng = _admin_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        eng.dispose()

    # 建表（等价 scripts/init_db.py：create_all + org_id 补列防御）
    engine = get_engine()
    Base.metadata.create_all(engine, checkfirst=True)
    from sqlalchemy import inspect as sa_inspect

    with engine.begin() as conn:
        for table in ("app_user", "child_profile", "pet_profile", "qa_session", "report"):
            cols = {c["name"] for c in sa_inspect(engine).get_columns(table)}
            if "org_id" not in cols:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN org_id VARCHAR NULL'))
            conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS "idx_{table}_org_id" '
                    f'ON "{table}" (org_id)'
                )
            )

    _seed_all()
    yield TEST_DB_URL

    # 会话收尾：断开连接池后 best effort 删库
    try:
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    try:
        _drop_test_db()
    except Exception:  # noqa: BLE001
        pass


def _truncate_all() -> None:
    """清空测试库全部业务表（TRUNCATE ... CASCADE 一条语句）+ RAG 向量表。

    data_kb_dense 为 LlamaIndex PGVectorStore 自管表（不在 ORM metadata），
    仅在表已存在时追加 TRUNCATE（测试库无 vector 扩展时自然跳过）。

    Returns:
        None。

    Raises:
        Exception: 清理失败时向上抛出。
    """
    tables = ", ".join(f'"{t}"' for t in Base.metadata.tables.keys())
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        # RAG 向量表（存在性防御：无扩展测试库无此表，跳过）
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF to_regclass('data_kb_dense') IS NOT NULL THEN "
                "TRUNCATE TABLE data_kb_dense; END IF; END $$;"
            )
        )


# pgvector 门控探测缓存（session 级：测试库无扩展恒 False，有扩展 True）
_pgvector_gated_probe: bool | None = None


@pytest.fixture(scope="session")
def pgvector_gated():
    """pgvector 门控 fixture：测试库具备 vector 扩展时才执行集成用例。

    Yields:
        True（仅当扩展就绪）；无扩展时 pytest.skip 整组用例。
    """
    global _pgvector_gated_probe
    if _pgvector_gated_probe is None:
        try:
            from sqlalchemy import text as _t

            engine = get_engine()
            with engine.begin() as conn:
                row = conn.execute(
                    _t("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
                ).first()
            _pgvector_gated_probe = bool(row is not None and row[0])
        except Exception:  # noqa: BLE001 — 方言不支持按不可用处理
            _pgvector_gated_probe = False
    if not _pgvector_gated_probe:
        pytest.skip("测试库无 pgvector 扩展，跳过向量集成用例（降级链用例正常执行）")
    yield True


# Milvus 门控探测缓存（session 级）
_milvus_gated_probe: bool | None = None


@pytest.fixture(scope="session")
def milvus_gated():
    """Milvus 门控 fixture：宿主 Milvus 可达时才执行集成用例。

    探测顺序：环境变量 MILVUS_TEST_URI（专用测试实例）→ 开发配置
    localhost:19531；不可达时 pytest.skip 整组用例（主通道降级链用例
    正常执行）。

    Yields:
        True（仅当 Milvus 可达且集合可建）。
    """
    global _milvus_gated_probe
    if _milvus_gated_probe is None:
        uri = os.environ.get("MILVUS_TEST_URI", "").strip() or "http://localhost:19531"
        try:
            from pymilvus import MilvusClient

            client = MilvusClient(uri=uri)
            _milvus_gated_probe = bool(client is not None)
        except Exception:  # noqa: BLE001 — 不可达按 skip 处理
            _milvus_gated_probe = False
    if not _milvus_gated_probe:
        pytest.skip("宿主 Milvus 不可达（19531），跳过向量集成用例（降级链用例正常执行）")
    # gated 用例需要主通道指向测试实例：直接改 settings 实例属性（get_settings
    # 为 lru_cache 单例，仅 setenv 不生效）并重置 rag_index 单例缓存；yield 后
    # 恢复测试进程基线（空 URI），普通用例仍不触真库。
    from app.core.config import get_settings
    import app.services.rag_index as _ri

    _settings = get_settings()
    _orig_uri = _settings.milvus_uri
    _settings.milvus_uri = (
        os.environ.get("MILVUS_TEST_URI", "").strip() or "http://localhost:19531"
    )
    _ri._client = None
    _ri._probe_cache = None
    yield True
    _settings.milvus_uri = _orig_uri
    _ri._client = None
    _ri._probe_cache = None


def _seed_all() -> None:
    """写入种子数据（复用 scripts/seed_data.py 的幂等种子函数）。

    Returns:
        None。

    Raises:
        Exception: 种子写入失败时抛出。
    """
    from scripts.seed_data import seed, seed_admins

    from app.db import get_session_factory

    db = get_session_factory()()
    try:
        seed_admins(db)
        seed(db)
    finally:
        db.close()


def _clear_cache() -> None:
    """清空进程内缓存单例（词库快照/活跃会话/问答缓存等键位）。

    Returns:
        None。

    Raises:
        无（直接清空内部字典，不做异常处理）。
    """
    cache._data.clear()
    cache._expire_at.clear()


@pytest.fixture(autouse=True)
def clean_state(test_database):
    """function 级状态隔离夹具：每个测试前清表 + 重种子 + 清缓存。

    Args:
        test_database: session 级测试库夹具（依赖注入保证库已就绪）。

    Yields:
        None。

    Raises:
        Exception: 清理/种子失败时向上抛出。
    """
    _truncate_all()
    _seed_all()
    _clear_cache()
    yield
    _clear_cache()


@pytest.fixture(autouse=True)
def llm_mock():
    """autouse 夹具：强制 llm_mock=True，保证 qa/风险扫描确定性。

    Yields:
        None。

    Raises:
        无。
    """
    from app.core.config import get_settings

    get_settings().llm_mock = True
    yield
    get_settings().llm_mock = False


# ---------------------------------------------------------------------------
# 通用夹具
# ---------------------------------------------------------------------------
@pytest.fixture
def client(test_database):
    """FastAPI TestClient 夹具（不触发 lifespan，避免启动定时任务）。

    Args:
        test_database: session 级测试库夹具。

    Yields:
        TestClient 实例（复用全局 app）。

    Raises:
        无。
    """
    yield TestClient(app_main.app)


@pytest.fixture
def user_token(client):
    """C 端用户登录夹具工厂：dev-login 后返回 (headers, user_uid)。

    默认同时完成「基础同意」（D2 修复：问答/测评入口已强制 1301 门禁，
    绝大多数用例需要已同意的基础态）；断言未同意行为的用例传
    agree=False 获取未同意用户。

    Args:
        client: TestClient 夹具。

    Returns:
        工厂函数 _login(device_id, agree=True)；返回 (鉴权 headers dict, user_uid str)。

    Raises:
        AssertionError: 登录/同意响应非 200 或 code 非 0。
    """

    def _login(device_id: str = "dev-itest-1", agree: bool = True):
        """执行 dev-login（可选签署基础同意）。

        Args:
            device_id: 设备唯一标识。
            agree: 是否顺带签署基础同意（base）。

        Returns:
            (headers, user_uid) 二元组。

        Raises:
            AssertionError: 登录或同意失败。
        """
        resp = client.post("/api/v1/auth/dev-login", json={"device_id": device_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0, body
        data = body["data"]
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        if agree:
            consent = client.post(
                "/api/v1/consent/agree",
                json={"consent_type": "base"},
                headers=headers,
            )
            assert consent.status_code == 200, consent.text
            assert consent.json()["code"] == 0, consent.text
        return headers, data["user_uid"]

    return _login


@pytest.fixture
def admin_token(client):
    """后台管理员登录夹具工厂：login → mfa/verify → 返回鉴权 headers。

    Args:
        client: TestClient 夹具。

    Returns:
        工厂函数 _make(role)；role 取 admin/operator/support/expert_child/expert_pet。

    Raises:
        AssertionError: 登录或 MFA 校验失败。
    """

    def _make(role: str):
        """两步登录指定角色。

        Args:
            role: 后台账号用户名（同时即角色标识）。

        Returns:
            鉴权 headers dict。

        Raises:
            AssertionError: 任一步失败。
        """
        resp = client.post(
            "/api/v1/admin/login",
            json={"username": role, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        ticket = resp.json()["data"]["mfa_ticket"]
        resp2 = client.post(
            "/api/v1/admin/mfa/verify", json={"mfa_ticket": ticket, "code": "123456"}
        )
        assert resp2.status_code == 200, resp2.text
        token = resp2.json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


# ---------------------------------------------------------------------------
# 公共工具函数（供测试模块导入复用）
# ---------------------------------------------------------------------------
def parse_sse(raw: str):
    """解析 SSE 文本为 (event, data_dict) 帧序列。

    Args:
        raw: StreamingResponse 完整文本（event/data 帧以空行分隔）。

    Returns:
        [(event_type, data_dict or None), ...] 列表。

    Raises:
        json.JSONDecodeError: data 段非合法 JSON（测试自身问题）。
    """
    frames = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        frames.append((event, json.loads(data) if data else None))
    return frames


def mock_pay_sign(transaction_id: str) -> str:
    """按 mock 通道口径计算支付回调验签。

    Args:
        transaction_id: 渠道交易号。

    Returns:
        sha256_hex(transaction_id + pay_mock_sign_key) 十六进制摘要。

    Raises:
        无。
    """
    from app.core.config import get_settings
    from app.core.crypto import sha256_hex

    return sha256_hex(transaction_id + get_settings().pay_mock_sign_key)


def db_query_user_id(user_uid: str):
    """按 user_uid 查询数据库主键 id（并发测试构造 cache 键用）。

    Args:
        user_uid: 用户对外唯一标识。

    Returns:
        数据库主键 int。

    Raises:
        AssertionError: 用户不存在。
    """
    from app.db import get_session_factory
    from app.models import AppUser

    db = get_session_factory()()
    try:
        row = db.query(AppUser).filter(AppUser.user_uid == user_uid).first()
        assert row is not None, f"user {user_uid} not found"
        return row.id
    finally:
        db.close()


# 保证导入面完整（供 pytest fixture 发现；ALL_MODELS 用于断言表数量）
# 37 张 V3.0 基线表 + 11 张 V3.1 增量表（PRD V3.1 §6.1）= 48
assert len(ALL_MODELS) == 48

# -*- coding: utf-8 -*-
"""RAG 向量索引模块（Milvus 独立向量库，spec milvus-vector-store）。

全项目唯一的向量库触点：检索层主通道（原生 pymilvus MilvusClient + Milvus
standalone 3.0.2 集合 `jiaban_kb_entries` + 智谱 embedding-3 2048 维）与知识
库写路径的索引同步（upsert_entry/delete_entry/sync_entry/reindex_all）都收敛
到本模块；顶层 try-import——pymilvus 未安装/导入失败时 available()=False，
检索自动走 hashing 降级链，业务无感。

对外契约（与 rag-llamaindex-migration 轮完全一致，业务接线零改动）：
available / query / upsert_entry / delete_entry / sync_entry / reindex_all。

关键语义（方案已核实，与 Python 降级分支同构）：
- 集合 schema：kb_id VarChar(64) 主键 + embedding FloatVector(2048) +
  status/kb_kind/domain/age_band/species 过滤标量（空值写哨兵 'any'）；
  正文不落 Milvus，命中后按 kb_id 回主库取条目；
- 索引/一致性：HNSW(M=16, efConstruction=200) COSINE（搜索 ef=128），
  集合级 Strong——sync_entry 写返回后查询立即可见（写后立读）；
- 原生 upsert（无需 delete+add）；delete 按 kb_id 主键删；
- 过滤表达式：status/kb_kind 固定 + domain IN 别名集 + 哨兵 IN [v,'any']
  （species 仅 pet 域）；**所有插入值过白名单正则，非法值丢弃该条件**
  （表达式注入防护）；
- 一致性双保险：Strong + retriever 候选回查复核 published/child/pet
  （下架内容绝不泄露）；写同步失败吞异常 + warning（reindex_all 自愈）。

降级链（spec D6 保持不变）：MILVUS_URI 空 / pymilvus 缺失 / 探测失败 /
查询异常 → hashing JSONB + Python 余弦 → 纯关键词，业务无感。
"""
import logging
import re
from typing import List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from ..models import KbEntry
from ..llm.embed_client import embed_texts

logger = logging.getLogger("jiaban.rag_index")

# ---------------------------------------------------------------------------
# 顶层 try-import：pymilvus 不可用时整体降级（available()=False）
# ---------------------------------------------------------------------------
try:
    from pymilvus import DataType, MilvusClient  # noqa: F401 — DataType 供建集合用

    _PYMILVUS_OK = True
    _PYMILVUS_IMPORT_ERROR = ""
except Exception as _exc:  # noqa: BLE001 — 可选依赖缺失按降级处理
    _PYMILVUS_OK = False
    _PYMILVUS_IMPORT_ERROR = str(_exc)

# 集合名（模块常量，不引入配置项）
COLLECTION_NAME = "jiaban_kb_entries"

# 元数据空值哨兵（空 age_band/species 写 'any'，过滤 IN [value, 'any']）
ANY_SENTINEL = "any"

# 检索搜索参数（HNSW ef 值；COSINE 下 distance 即余弦相似度）
_SEARCH_EF = 128

# 过滤表达式值白名单（字母/数字/下划线/中文/点/连字符；防表达式注入）
_SAFE_VALUE_RE = re.compile(r"^[\w\u4e00-\u9fff.\-]+$")

# 进程内缓存（客户端单例；探测仅缓存 True——失败不缓存，Milvus 后启自动恢复）
_client = None
_probe_cache: Optional[bool] = None


def get_client():
    """获取/构建 MilvusClient（进程内单例）。

    Returns:
        MilvusClient 实例；pymilvus 不可用或 milvus_uri 未配置时返回 None。
    """
    global _client
    if not _PYMILVUS_OK:
        return None
    if _client is not None:
        return _client
    from ..core.config import get_settings

    settings = get_settings()
    uri = (settings.milvus_uri or "").strip()
    if not uri:
        return None
    token = (settings.milvus_token or "").strip() or None
    _client = MilvusClient(uri=uri, token=token)
    return _client


def _configured() -> bool:
    """快路径：pymilvus 就绪且 milvus_uri 已配置（不发起连接）。

    Returns:
        主通道可能可用返回 True。
    """
    if not _PYMILVUS_OK:
        return False
    from ..core.config import get_settings

    return bool((get_settings().milvus_uri or "").strip())


def available() -> bool:
    """探测 Milvus 主通道是否可用（配置 + 集合存在）。

    探测结果仅缓存 True——失败不缓存（Milvus 后启即可自动恢复，
    无需重启后端）。

    Returns:
        可用返回 True；任一环节缺失/失败返回 False（检索走降级链）。
    """
    global _probe_cache
    if not _configured():
        return False
    if _probe_cache:
        return True
    try:
        client = get_client()
        if client is None:
            return False
        if client.has_collection(COLLECTION_NAME):
            _probe_cache = True
            return True
        return False
    except Exception as exc:  # noqa: BLE001 — 不可用按降级处理（不缓存失败）
        logger.info("rag_index Milvus unavailable, retrieval falls back to hashing: %s", exc)
        return False


def ensure_collection() -> bool:
    """确保集合存在（不存在则建：schema + HNSW 索引 + Strong + load）。

    供 init_db / reindex_all 调用；运行期不自愈建表（异常回退降级链）。

    Returns:
        集合就绪返回 True；pymilvus/URI 缺失或建集合失败返回 False。
    """
    if not _configured():
        return False
    client = get_client()
    if client is None:
        return False
    try:
        if client.has_collection(COLLECTION_NAME):
            return True
        from ..core.config import get_settings

        dim = get_settings().embedding_dimensions
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        # 注意：pymilvus 3.0.2 的主键参数名为 is_primary（方案文档的
        # is_primary_key 写法会被静默忽略致 Schema 无主键）
        schema.add_field("kb_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field("status", DataType.VARCHAR, max_length=16)
        schema.add_field("kb_kind", DataType.VARCHAR, max_length=8)
        schema.add_field("domain", DataType.VARCHAR, max_length=32)
        schema.add_field("age_band", DataType.VARCHAR, max_length=16)
        schema.add_field("species", DataType.VARCHAR, max_length=16)
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding", index_type="HNSW", metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        client.create_collection(
            COLLECTION_NAME, schema=schema, index_params=index_params,
            consistency_level="Strong",
        )
        client.load_collection(COLLECTION_NAME)
        logger.info("rag_index collection created: %s (dim=%s, HNSW, Strong)", COLLECTION_NAME, dim)
        return True
    except Exception as exc:  # noqa: BLE001 — 建集合失败按降级处理
        logger.warning("rag_index ensure_collection failed: %s", exc)
        return False


def _safe_value(value: object) -> bool:
    """过滤表达式值白名单校验（防表达式注入）。

    Args:
        value: 待插入表达式的标量值。

    Returns:
        合法（字母/数字/下划线/中文/点/连字符）返回 True。
    """
    return bool(_SAFE_VALUE_RE.match(str(value)))


def build_filter_expr(
    domain_alias: Sequence[str],
    age_band: Optional[str] = None,
    species: Optional[str] = None,
) -> str:
    """构建 Milvus 过滤表达式（与旧 build_filters 完全同构）。

    固定：status == 'published' + kb_kind IN (child, pet) + domain IN 别名集
    （防御未及时 delete 的脏数据，下架内容绝不泄露）；查询参数非空时
    age_band/species 追加 IN [value, 'any']（哨兵 OR 语义）；species 仅
    pet 域参与过滤。**注入防护**：所有值先过白名单正则，非法值丢弃该
    条件（绝不原样拼接）。

    Args:
        domain_alias: domain 命名映射集合（英文码/中文别名）。
        age_band: 儿童年龄段（None 时不做年龄段过滤）。
        species: 宠物物种 cat/dog（None 或非 pet 域时不过滤）。

    Returns:
        Milvus 过滤表达式字符串（and 组合）。
    """
    conds = ['status == "published"', 'kb_kind in ["child", "pet"]']
    # domain：逐项白名单过滤（别名来自代码内映射，非法值防御性剔除）
    domains = [str(d) for d in (domain_alias or ()) if _safe_value(d)]
    if domains:
        conds.append("domain in [" + ", ".join(f'"{d}"' for d in domains) + "]")
    else:
        logger.warning("build_filter_expr: all domain values rejected by whitelist: %r", domain_alias)
    if age_band:
        if _safe_value(age_band):
            conds.append(f'age_band in ["{age_band}", "{ANY_SENTINEL}"]')
        else:
            logger.warning("build_filter_expr: age_band value rejected: %r", age_band)
    if species and "pet" in (domain_alias or ()):
        if _safe_value(species):
            conds.append(f'species in ["{species}", "{ANY_SENTINEL}"]')
        else:
            logger.warning("build_filter_expr: species value rejected: %r", species)
    return " and ".join(conds)


def _entry_text(entry: KbEntry) -> str:
    """条目向量输入文本（title + content，与降级链 hashing 口径同源）。

    Args:
        entry: KbEntry 实例。

    Returns:
        拼接文本。
    """
    return f"{entry.title}\n{entry.content}"


def _entry_row(entry: KbEntry, vector: List[float]) -> dict:
    """条目转 Milvus 行（主键 + 向量 + 过滤标量，空值哨兵 'any'）。

    Args:
        entry: KbEntry 实例。
        vector: 该条目的稠密向量（embed_texts 生成）。

    Returns:
        可直接 upsert 的行 dict。
    """
    return {
        "kb_id": entry.kb_id,
        "embedding": vector,
        "status": entry.status,
        "kb_kind": entry.kb_kind,
        "domain": entry.domain,
        "age_band": entry.age_band or ANY_SENTINEL,
        "species": entry.species or ANY_SENTINEL,
    }


def upsert_entry(db: Session, kb_id: str) -> None:
    """把条目写入 Milvus（原生 upsert，同 kb_id 幂等单条）。

    调用方保证 available() 为真；向量经 embed_texts 生成（provider 分发）。

    Args:
        db: 数据库会话（读取条目最新内容）。
        kb_id: 知识条目业务编号。

    Raises:
        RuntimeError: 主通道不可用时抛出（sync_entry 已捕获）。
        sqlalchemy 异常: 条目读取失败时向上抛出。
        EmbeddingError: 向量生成失败时向上抛出。
    """
    entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
    if entry is None:
        return
    client = get_client()
    if client is None:
        raise RuntimeError("Milvus client unavailable")
    vector = embed_texts([_entry_text(entry)])[0]
    client.upsert(collection_name=COLLECTION_NAME, data=[_entry_row(entry, vector)])


def delete_entry(kb_id: str) -> None:
    """按 kb_id 主键从 Milvus 删除（下架/驳回/删除场景）。

    Args:
        kb_id: 知识条目业务编号。

    Raises:
        RuntimeError: 主通道不可用时抛出（sync_entry 已捕获）。
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Milvus client unavailable")
    client.delete(collection_name=COLLECTION_NAME, ids=[kb_id])


def sync_entry(db: Session, kb_id: str) -> None:
    """按条目当前状态同步索引（best-effort，失败不回滚主流程）。

    published 且 kb_kind ∈ {child, pet} → upsert；其余状态（draft/pending/
    rejected/unpublished/merged）或条目已删除 → delete。任何异常仅
    logger.warning——Strong 一致性 + 检索侧复核兜底下架内容不泄露，
    reindex_all 可自愈。

    Args:
        db: 数据库会话（与业务写入同一会话，状态已更新）。
        kb_id: 知识条目业务编号。

    Returns:
        None。
    """
    try:
        if not available():
            return
        entry = db.query(KbEntry).filter(KbEntry.kb_id == kb_id).first()
        if entry is not None and entry.status == "published" and entry.kb_kind in ("child", "pet"):
            upsert_entry(db, kb_id)
        else:
            delete_entry(kb_id)
    except Exception as exc:  # noqa: BLE001 — 索引同步失败不阻断业务写入
        logger.warning("rag_index sync_entry skipped for %s: %s", kb_id, exc)


def reindex_all(db: Session, batch_size: int = 32) -> int:
    """全量重建向量索引（published child/pet 条目，幂等自愈）。

    drop 集合后重建（维护动作，执行窗口自控；期间检索走降级链），
    再分批向量化原生 upsert（批内文本经 embed_texts 批量生成，智谱
    通道单批 ≤64 上限由 embed_client 管理）。

    Args:
        db: 数据库会话（读取条目全集）。
        batch_size: 每批写入条目数。

    Returns:
        本次写入的条目数。

    Raises:
        RuntimeError: 主通道不可用时抛出（调用方决定处理）。
    """
    if not ensure_collection():
        raise RuntimeError("Milvus unavailable: collection not ready")
    client = get_client()
    rows = (
        db.query(KbEntry)
        .filter(
            KbEntry.status == "published",
            KbEntry.kb_kind.in_(("child", "pet")),
        )
        .all()
    )
    written = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        texts = [_entry_text(e) for e in chunk]
        vectors = embed_texts(texts)
        data = [_entry_row(e, v) for e, v in zip(chunk, vectors)]
        client.upsert(collection_name=COLLECTION_NAME, data=data)
        written += len(data)
    logger.info("rag_index reindex_all written=%s", written)
    return written


def query(
    question: str,
    domain_alias: Sequence[str],
    age_band: Optional[str] = None,
    species: Optional[str] = None,
    top_k: int = 8,
) -> List[Tuple[str, float]]:
    """向量近邻检索（主通道，返回 kb_id 与余弦相似度）。

    Args:
        question: 用户问题原文。
        domain_alias: domain 命名映射集合（英文码/中文别名）。
        age_band: 儿童年龄段（None 时不做年龄段过滤）。
        species: 宠物物种（None 或非 pet 域时不过滤）。
        top_k: 候选上限（粗筛口径，后续混合重排取 top5）。

    Returns:
        [(kb_id, 余弦相似度)] 列表，按相似度降序。

    Raises:
        RuntimeError: 主通道不可用时抛出（调用方保证 available() 为真，
        异常由 retrieve 三分支捕获回退降级链）。
        EmbeddingError: 查询向量生成失败时向上抛出。
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Milvus client unavailable")
    expr = build_filter_expr(domain_alias, age_band, species)
    qvec = embed_texts([question])[0]
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[qvec],
        filter=expr,
        limit=top_k,
        search_params={"metric_type": "COSINE", "params": {"ef": _SEARCH_EF}},
        output_fields=["kb_id"],
    )
    out: List[Tuple[str, float]] = []
    for hits in results or []:
        for hit in hits:
            kb_id = hit.get("id") or (hit.get("entity") or {}).get("kb_id")
            if kb_id:
                # COSINE 下 distance 即余弦相似度（越大越相似）
                out.append((str(kb_id), float(hit.get("distance", 0.0))))
    return out

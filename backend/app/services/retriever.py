# -*- coding: utf-8 -*-
"""知识库混合检索服务模块（余弦 + 关键词双通道打分，三分支降级链）。

检索主通道（spec rag-llamaindex-migration + milvus-vector-store）：
- 主路径：rag_index（原生 pymilvus MilvusClient + Milvus standalone 集合
  `jiaban_kb_entries` + 智谱 embedding-3 2048 维稠密向量）——余弦项取自
  向量近邻检索，关键词通道沿用本模块逻辑；
- 回退路径：主通道异常（检索抛错/库不可达）时本次回退降级路径并 warning；
- 降级路径（spec D6 保留）：`_retrieve_fallback` 全量捞取后 Python 侧
  打分——向量通道为「字符 3-gram hashing 512 维稀疏向量」余弦
  （cosine_sparse，与条目侧同一表征空间），关键词通道为分词命中归一化，
  总分 = 0.6 × 余弦 + 0.4 × 关键词；条目缺 embedding 时余弦项按 0。

约束（三条路径一致）：
- 只检索 status='published' 的 child/pet 条目；
- domain 必须匹配（英文码/中文别名），age_band/species 允许条目为空
  （通用条目）或相等；
- 候选取 top8，再按分数取前 5 条。

输出条目结构与架构约定一致：
{kb_id, kb_version, title, content, preconditions, stance, topic_key, domain}。
"""
import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..models import KbEntry
from . import rag_index

logger = logging.getLogger("jiaban.retriever")

# 检索返回的最大条数
TOP_K = 5

# 打分候选池大小（先粗筛 top8，再精选前 5）
CANDIDATE_SIZE = 8

# 知识条目版本号（MVP 固定 v1，与 evidence_ref 口径一致）
KB_VERSION = "v1"

# 中文单字/常见虚词停用表（极简，避免 2-gram 噪声）
_STOPWORDS = frozenset({"的", "了", "吗", "呢", "啊", "是", "我", "有", "和", "怎", "么", "什么"})

# hashing 向量维度（3-gram 经哈希折叠映射到 [0, EMBED_DIM) 桶位）
EMBED_DIM = 512

# 混合打分权重：余弦通道 / 关键词通道
W_COSINE = 0.6
W_KEYWORD = 0.4


def tokenize(text: str) -> set:
    """问题分词：提取英文/数字单词与中文连续片段的 2-gram。

    Args:
        text: 原始文本。

    Returns:
        无重复的 token 集合（英文转小写）。
    """
    tokens: set = set()
    if not text:
        return tokens
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    for word in cleaned.split():
        if word.isdigit() or word in _STOPWORDS:
            continue
        # 含中文的连续片段做 2-gram（单字噪声大，不收单字）
        if re.search(r"[\u4e00-\u9fff]", word):
            if len(word) == 1:
                tokens.add(word)
                continue
            for i in range(len(word) - 1):
                gram = word[i : i + 2]
                # 2-gram 落入停用表则跳过
                if gram not in _STOPWORDS:
                    tokens.add(gram)
        else:
            tokens.add(word)
    return tokens


def hashing_embed(text: str) -> Dict[int, float]:
    """字符 3-gram hashing 到 512 维稀疏向量（零外部依赖）。

    对清洗后的小写文本滑动取字符 3-gram，逐 gram 用 MD5 折叠到
    [0, EMBED_DIM) 桶位并累计词频，权重 = 1 + log(tf)（sublinear tf）。
    哈希采用 MD5 而非内建 hash()（PYTHONHASHSEED 随机化），
    保证跨进程/重启的向量可复现。

    Args:
        text: 原始文本（标题/正文/问题均可）。

    Returns:
        {index: weight} 稀疏表示（可直接 JSONB 持久化）；
        空文本或不足 3 个字符时返回空 dict。
    """
    tf: Dict[int, float] = {}
    if not text:
        return {}
    # 清洗：去除全部空白并小写，中英文统一处理
    cleaned = re.sub(r"\s+", "", text.lower())
    for i in range(len(cleaned) - 2):
        gram = cleaned[i : i + 3]
        # MD5 前 8 位十六进制折叠到固定维度，桶位分布均匀
        idx = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16) % EMBED_DIM
        tf[idx] = tf.get(idx, 0.0) + 1.0
    # sublinear tf 折减高频 gram 的权重
    return {idx: 1.0 + math.log(cnt) for idx, cnt in tf.items()}


def cosine_sparse(a: Dict[int, float], b: Dict[int, float]) -> float:
    """稀疏向量余弦相似度（0-1）。

    Args:
        a: 稀疏向量 A（{index: weight}）。
        b: 稀疏向量 B（{index: weight}）。

    Returns:
        余弦相似度；任一向量为空或模长为 0 时返回 0.0。
    """
    if not a or not b:
        return 0.0
    dot = 0.0
    for idx, weight in a.items():
        other = b.get(idx)
        if other is not None:
            dot += weight * other
    if dot <= 0.0:
        # 权重恒非负：dot<=0 即无公共桶位
        return 0.0
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    # 权重恒正时余弦取值 (0,1]；min 兜底浮点误差
    return min(dot / (norm_a * norm_b), 1.0)


def _keyword_score(entry, tokens: Set[str]) -> float:
    """关键词通道归一化打分（0-1）。

    title 命中权重 2、正文命中权重 1，再除以理论满分
    kw_max（len(tokens) × 2）归一化到 0-1。

    Args:
        entry: KbEntry（或具备 title/content 属性的替身对象）。
        tokens: 问题分词集合。

    Returns:
        0-1 区间的关键词归一化分；tokens 为空时返回 0.0。
    """
    kw_score = 0.0
    for tok in tokens:
        if tok in entry.title:
            kw_score += 2.0
        elif tok in entry.content:
            kw_score += 1.0
    kw_max = len(tokens) * 2.0 if tokens else 0.0
    return min(kw_score / kw_max, 1.0) if kw_max > 0 else 0.0


def _score_entry(entry, tokens: Set[str], question_vec: Dict[int, float]) -> float:
    """单条目混合打分：0.6 × 余弦 + 0.4 × 关键词归一化分。

    向量通道：条目 embedding 缺失或格式非法时余弦项按 0 处理。

    Args:
        entry: KbEntry（或具备 title/content/embedding 属性的替身对象）。
        tokens: 问题分词集合。
        question_vec: 问题的 hashing 稀疏向量。

    Returns:
        0-1 区间的混合得分。
    """
    # ---- 向量通道：embedding 缺失/非法按 0 ----
    embedding = entry.embedding if isinstance(entry.embedding, dict) else None
    cos = cosine_sparse(question_vec, embedding) if embedding else 0.0
    return W_COSINE * cos + W_KEYWORD * _keyword_score(entry, tokens)


def _entry_doc(entry) -> dict:
    """条目序列化为检索输出契约结构。

    Args:
        entry: KbEntry（或具备同名属性的替身对象）。

    Returns:
        {kb_id, kb_version, title, content, preconditions, stance,
        topic_key, domain}。
    """
    return {
        "kb_id": entry.kb_id,
        "kb_version": KB_VERSION,
        "title": entry.title,
        "content": entry.content,
        "preconditions": entry.preconditions,
        "stance": entry.stance,
        "topic_key": entry.topic_key,
        "domain": entry.domain,
    }


class Retriever:
    """知识库混合检索器（余弦 + 关键词双通道，三分支降级链）。

    无状态，逐次按域检索；供 LangGraph retrieve 节点调用。
    主通道 rag_index（LlamaIndex+智谱）→ 异常回退 → hashing 降级。
    """

    def retrieve(
        self,
        db: Session,
        question: str,
        domain: str,
        age_band: Optional[str] = None,
        species: Optional[str] = None,
    ) -> dict:
        """按领域执行混合检索并打分排序（三分支降级链）。

        主通道 rag_index（LlamaIndex 向量检索）就绪时余弦项取自向量近邻，
        关键词通道沿用现有逻辑，混合口径不变；主通道异常时本次回退降级
        路径并 warning；不可用/回退走与降级方案完全一致的进程内路径。

        Args:
            db: 数据库会话。
            question: 用户问题原文。
            domain: 知识领域（child / pet）。
            age_band: 儿童年龄段（None 时不做年龄段过滤）。
            species: 宠物物种 cat/dog（None 或非 pet 域时不过滤）。

        Returns:
            {"hit": bool, "docs": [...前 5 条]}，每条含
            {kb_id, kb_version, title, content, preconditions, stance,
            topic_key, domain}。
        """
        tokens = tokenize(question)
        # 问题侧向量：字符 3-gram hashing（降级链与条目侧同一表征空间）
        question_vec = hashing_embed(question)
        # domain 兼容映射：检索入参用英文码（child/pet），
        # 库内条目 domain 可能存中文（育儿/宠物）或英文码，两者都纳入过滤
        domain_alias = {
            "child": ("child", "育儿"),
            "pet": ("pet", "宠物"),
        }.get(domain, (domain,))
        docs: Optional[List[dict]] = None
        if rag_index.available():
            try:
                docs = self._retrieve_by_index(
                    db, tokens, question, domain_alias, age_band, species
                )
            except Exception as exc:  # noqa: BLE001 — 主通道故障回退降级链
                logger.warning(
                    "rag_index retrieve failed, fallback to hashing path: %s", exc
                )
        if docs is None:
            docs = self._retrieve_fallback(
                db, tokens, question_vec, domain_alias, age_band, species
            )
        return {"hit": bool(docs), "docs": docs}

    def _retrieve_by_index(
        self,
        db: Session,
        tokens: Set[str],
        question: str,
        domain_alias: Sequence[str],
        age_band: Optional[str],
        species: Optional[str],
    ) -> List[dict]:
        """LlamaIndex 向量检索路径：先取近邻候选，再按混合口径精选。

        存储后端为 Milvus 独立向量库（spec milvus-vector-store，集合
        jiaban_kb_entries）。余弦项直接取 rag_index 返回的相似度；
        关键词打分沿用现有 _keyword_score 逻辑，总分口径仍为
        0.6×余弦 + 0.4×关键词。候选按 kb_id 批量取回，回查复核
        published/child/pet（Strong 之外的防御纵深，下架内容绝不泄露）。

        Args:
            db: 数据库会话（按 kb_id 批量取候选条目）。
            tokens: 问题分词集合。
            question: 用户问题原文（向量检索入参）。
            domain_alias: domain 命名映射集合（英文码/中文别名）。
            age_band: 儿童年龄段（None 时不做年龄段过滤）。
            species: 宠物物种（None 时不过滤）。

        Returns:
            检索文档列表（前 TOP_K 条，契约结构与降级路径一致）。

        Raises:
            RuntimeError/sqlalchemy 异常: 主通道故障时向上抛出
            （retrieve 捕获后回退降级路径）。
        """
        hits = rag_index.query(
            question, domain_alias, age_band=age_band, species=species,
            top_k=CANDIDATE_SIZE,
        )
        if not hits:
            return []
        cos_map = {kb_id: cos for kb_id, cos in hits}
        # 候选条目按业务编号 kb_id 批量取回；回查复核 published + child/pet
        # （一致性双保险第二层：Milvus 中未及时 delete 的下架脏数据绝不泄露）
        rows = (
            db.query(KbEntry)
            .filter(
                KbEntry.kb_id.in_(list(cos_map)),
                KbEntry.status == "published",
                KbEntry.kb_kind.in_(("child", "pet")),
            )
            .all()
        )
        scored: List[tuple] = []
        for entry in rows:
            cos = cos_map.get(entry.kb_id, 0.0)
            score = W_COSINE * cos + W_KEYWORD * _keyword_score(entry, tokens)
            scored.append((score, entry))
        # 与降级路径同语义：有 token 时过滤零分条目
        if tokens:
            scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: (-s[0], s[1].id))
        return [_entry_doc(entry) for _, entry in scored[:TOP_K]]

    def _retrieve_fallback(
        self,
        db: Session,
        tokens: Set[str],
        question_vec: Dict[int, float],
        domain_alias: Sequence[str],
        age_band: Optional[str],
        species: Optional[str],
    ) -> List[dict]:
        """进程内回退检索路径（全量捞取后 Python 侧打分，行为与降级方案一致）。

        Args:
            db: 数据库会话。
            tokens: 问题分词集合。
            question_vec: 问题的 hashing 稀疏向量。
            domain_alias: domain 命名映射集合（英文码/中文别名）。
            age_band: 儿童年龄段（None 时不做年龄段过滤）。
            species: 宠物物种（None 时不过滤）。

        Returns:
            检索文档列表（前 TOP_K 条）。
        """
        rows = (
            db.query(KbEntry)
            .filter(
                KbEntry.status == "published",
                KbEntry.domain.in_(domain_alias),
                # 只检索育儿/宠物知识库；题库与词库类条目不参与问答检索（数据模型 §5.1）
                KbEntry.kb_kind.in_(("child", "pet")),
            )
            .all()
        )
        scored: List[tuple] = []
        for entry in rows:
            # 年龄段/物种过滤：条目未标注视为通用，标注了则须相等
            if entry.age_band and age_band and entry.age_band != age_band:
                continue
            if species and entry.species and entry.species != species:
                continue
            scored.append((_score_entry(entry, tokens, question_vec), entry))
        # 有 token 时过滤零分条目；无 token 时全部候选按余弦通道参与排序
        if tokens:
            scored = [s for s in scored if s[0] > 0]
        # 粗筛 top8（分数降序，同分按主键稳定排序）
        scored.sort(key=lambda s: (-s[0], s[1].id))
        candidates = scored[:CANDIDATE_SIZE]
        return [_entry_doc(entry) for _, entry in candidates[:TOP_K]]

    def ensure_embeddings(self, db: Session) -> int:
        """为缺失向量的 published child/pet 条目补算 embedding（幂等可重跑）。

        筛选条件与 retrieve 检索池一致（status='published' 且
        kb_kind ∈ {child, pet} 且 embedding IS NULL）；逐条计算
        hashing_embed(title+content) 后写入 embedding 与 vector_synced_at。

        Args:
            db: 数据库会话。

        Returns:
            本次补算的条目数（无缺失时为 0，重复调用幂等）。

        Raises:
            sqlalchemy 异常：落库失败时向上抛出（由调用方回滚）。
        """
        rows = (
            db.query(KbEntry)
            .filter(
                KbEntry.status == "published",
                KbEntry.kb_kind.in_(("child", "pet")),
                KbEntry.embedding.is_(None),
            )
            .all()
        )
        if not rows:
            return 0
        now = datetime.now(timezone.utc)
        for entry in rows:
            # 向量输入与检索打分同源：title + content
            entry.embedding = hashing_embed(f"{entry.title}\n{entry.content}")
            entry.vector_synced_at = now
        db.commit()
        return len(rows)
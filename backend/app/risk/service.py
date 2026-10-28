# -*- coding: utf-8 -*-
"""风险控制服务模块。

engine.py 之上的数据库/网关装配层：
- 词库快照加载（LexiconTerm 解密 + RiskRuleConfig 正则），进程内缓存 60s
  （cache 键 "lexicon:snapshot"）；
- scan 入口：两级流水线判定 + 命中后 RiskEvent 落库与 qa_session 状态置位；
- 危机干预渠道卡匹配（按 category_scope）。
"""
import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..core.cache import cache
from ..core.crypto import decrypt_field, sha256_hex
from ..llm.gateway import extract_json, get_gateway
from ..models import CrisisChannel, KbEntry, LexiconTerm, QaSession, RiskEvent, RiskRuleConfig
from . import engine
from .engine import LexiconSnapshot

logger = logging.getLogger("jiaban.risk")

# 词库快照缓存键与 TTL（秒）——变更后最迟 1 分钟全量生效
LEXICON_CACHE_KEY = "lexicon:snapshot"
LEXICON_CACHE_TTL = 60

# 风险服务不可用时的类别码（按命中保守处理的留痕类别）
UNAVAILABLE_CATEGORY = "risk_unavailable"

# 文案合规词表类型（RQ-02 / NFR-C14）：入库但**不参与**输入侧风险拦截
ANTHROPOMORPHIC_TYPE = "anthropomorphic"

# 处置动作取值集合（非风险类别码）：RiskRuleConfig 平铺存法把动作写在 action，
# 加载时不得把动作词当成 risk 类别（否则 risk_event/渠道卡按 "block_or_rewrite" 分派）
ACTION_VALUES = frozenset(
    {"block", "rewrite", "degrade", "block_or_rewrite", "block_or_degrade"}
)

# 类别 → 危机渠道覆盖别名（命中类别可复用其他类别的渠道卡）。
# 「风险服务不可用」复用「儿科急症就诊」渠道：拦截必须给出可执行的求助
# 入口，避免 unavailable 类别在渠道表中无匹配而只返回空列表。
# medicine_dosage（药名+剂量 / 误食药物）同属用药安全红线，复用「儿科急症
# 就诊」卡——命中药量问法时给出「立即就医/勿自行用药」的可执行落点。
CATEGORY_SCOPE_ALIAS: Dict[str, tuple] = {
    "risk_unavailable": ("risk_unavailable", "high_fever"),
    "medicine_dosage": ("medicine_dosage", "high_fever"),
}

# 上海时区（UTC+8 固定偏移，无夏令时；规避 Windows tzdata 依赖）
_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _now_shanghai() -> datetime:
    """获取当前上海时区时间。

    Returns:
        带时区的 datetime（UTC+8）。
    """
    return datetime.now(_TZ_SHANGHAI)


class RiskService:
    """风险控制服务：词库快照、两级扫描入口、事件落库、渠道卡。"""

    # ------------------------------------------------------------------
    # 词库快照
    # ------------------------------------------------------------------
    @staticmethod
    def load_snapshot(db: Session, force_refresh: bool = False) -> LexiconSnapshot:
        """加载词库快照（进程内缓存 60s）。

        安全依赖自检（缺陷 D1 修复）：库内存在 effective 词条却全部解密失败
        （FIELD_ENC_KEY 不匹配 / 密文被截断）时，一级词库等于空表——此时
        快照标记 degraded_reason，由 scan 入口按「命中」保守处理，避免
        安全依赖静默失效后整条风险链放行。

        Args:
            db: 数据库会话。
            force_refresh: True 时绕过缓存强制刷新。

        Returns:
            LexiconSnapshot：词条（解密后明文）+ 正则配置。
            全部词条解密失败时 degraded_reason 非 None（不抛异常，由调用方
            决定是否按命中处理）。
        """
        if not force_refresh:
            cached = cache.get(LEXICON_CACHE_KEY)
            if cached:
                try:
                    raw = json.loads(cached)
                    return LexiconSnapshot(
                        terms=raw.get("terms", []),
                        patterns=raw.get("patterns", {}),
                        loaded_at=raw.get("loaded_at", 0.0),
                        term_rows=raw.get("term_rows", 0),
                        term_decrypt_failed=raw.get("term_decrypt_failed", 0),
                        degraded_reason=raw.get("degraded_reason"),
                    )
                except Exception:  # noqa: BLE001 — 缓存损坏则回源重建
                    pass
        # 词条：effective=True，密文解密为明文（埋点只记哈希，此处为扫描必需）
        # V3.1 RQ-02：`anthropomorphic` 类型为**文案合规**词表（供 CI / 后台
        # 扫描固定文案使用），不得参与输入侧风险拦截——否则「陪伴」「伙伴」
        # 这类合规词会被当作高危词阻断用户正常提问。
        terms: List[dict] = []
        rows = (
            db.query(LexiconTerm)
            .filter(
                LexiconTerm.effective.is_(True),
                LexiconTerm.lexicon_type != ANTHROPOMORPHIC_TYPE,
            )
            .all()
        )
        failed = 0
        for row in rows:
            try:
                term = decrypt_field(row.term_enc)
            except Exception:  # noqa: BLE001 — 单条解密失败不拖垮快照
                failed += 1
                continue
            if not term:
                failed += 1
                continue
            terms.append(
                {
                    "term": term,
                    "category_code": row.category_code,
                    "strategy": row.strategy,
                }
            )
        # 安全依赖自检：有词条行但一条都没解密出来 → 快照不可信
        degraded_reason: Optional[str] = None
        if rows and not terms:
            degraded_reason = (
                f"词库快照不可用：{len(rows)} 条有效词条全部解密失败"
                f"（疑似 FIELD_ENC_KEY 不匹配或密文损坏，失败 {failed} 条）"
            )
            logger.error("risk lexicon snapshot degraded: %s", degraded_reason)
        elif failed:
            # 部分失败：可用但留痕，便于运维发现密钥轮换遗漏
            logger.warning(
                "risk lexicon snapshot partial: %s/%s 条词条解密失败", failed, len(rows)
            )
        # 正则：按 config_key 分组取 version 最大行，合并 config_value
        patterns: Dict[str, dict] = dict(engine.DEFAULT_PATTERNS)
        configs = db.query(RiskRuleConfig).all()
        latest: Dict[str, RiskRuleConfig] = {}
        for row in configs:
            kept = latest.get(row.config_key)
            if kept is None or (row.version or 0) > (kept.version or 0):
                latest[row.config_key] = row
        for row in latest.values():
            value = row.config_value or {}
            if not isinstance(value, dict):
                continue
            # 兼容三种存法：
            # ① {"patterns": {规则键: 规则}} 包裹形态；
            # ② {规则键: 规则} 字典形态；
            # ③ {pattern/regex, action} 单条规则形态（seed_data 平铺存法，e2e 实测曾致正则全部失效）
            if isinstance(value.get("patterns"), dict):
                items = value["patterns"].items()
            elif value.get("pattern") or value.get("regex"):
                items = [(row.config_key, value)]
            else:
                continue
            for key, cfg in items:
                if not isinstance(cfg, dict):
                    continue
                # 引擎消费 "regex" 键；库内存法为 "pattern"——此处统一归一化；
                # exclude_if（可选）为语境排除正则（宠物语境消歧），一并透传。
                # 类别口径：显式 category_code 优先；否则若 action 是「处置动作」
                # （block/rewrite/block_or_rewrite…）而非类别码，则按规则键推导
                # （medicine_dosage_pattern → medicine_dosage），避免把动作词当
                # 风险类别落库/下发（D1 实测：库里 {pattern, action} 平铺存法
                # 曾使 risk_event 类别为 "block_or_rewrite"，渠道卡与后台分派失准）。
                regex_expr = cfg.get("regex") or cfg.get("pattern")
                if regex_expr:
                    category = cfg.get("category_code")
                    if not category:
                        action = cfg.get("action")
                        if action in ACTION_VALUES:
                            category = (
                                key[: -len("_pattern")]
                                if key.endswith("_pattern")
                                else key
                            )
                        else:
                            category = action or key
                    pattern_cfg = {
                        "regex": regex_expr,
                        "category_code": category,
                    }
                    if cfg.get("exclude_if"):
                        pattern_cfg["exclude_if"] = cfg["exclude_if"]
                    patterns[key] = pattern_cfg
        snapshot = LexiconSnapshot(
            terms=terms,
            patterns=patterns,
            loaded_at=time.time(),
            term_rows=len(rows),
            term_decrypt_failed=failed,
            degraded_reason=degraded_reason,
        )
        cache.set(
            LEXICON_CACHE_KEY,
            json.dumps(
                {
                    "terms": terms,
                    "patterns": patterns,
                    "loaded_at": snapshot.loaded_at,
                    "term_rows": snapshot.term_rows,
                    "term_decrypt_failed": snapshot.term_decrypt_failed,
                    "degraded_reason": snapshot.degraded_reason,
                },
                ensure_ascii=False,
            ),
            ttl_seconds=LEXICON_CACHE_TTL,
        )
        return snapshot

    # ------------------------------------------------------------------
    # 扫描入口
    # ------------------------------------------------------------------
    @staticmethod
    def scan(
        db: Session,
        question: str,
        user_id: int,
        session: Optional[QaSession] = None,
        source_scene: str = "qa",
    ) -> dict:
        """两级风险扫描入口：先于一切生成动作执行。

        一级未命中时调 DeepSeek 语义分类（10s 超时，异常按命中保守处理）；
        命中时写 RiskEvent 并将 qa_session 置 blocked/high。

        缺陷 D1 修复（fail-closed）：词库快照加载异常或快照不可信
        （词条整体解密失败）时，不再静默放行，而是按 PRD「风险服务不可用
        按命中处理」返回保守拦截结果（category=risk_unavailable），
        并尽力留痕 RiskEvent（落库失败不影响拦截结论）。

        Args:
            db: 数据库会话。
            question: 用户问题原文（纯输入侧判定，不读档案）。
            user_id: 当前用户 id（仅用于哈希落库）。
            session: 关联问答会话（None 时不落会话状态）。
            source_scene: 事件来源场景（qa/appeal）。

        Returns:
            {"risk_result": 完整判定结果, "risk_event_no": 事件号或 None}。
        """
        # ---- 安全依赖：词库快照（异常/不可信 → 按命中处理） ----
        try:
            snapshot = RiskService.load_snapshot(db)
        except Exception as exc:  # noqa: BLE001 — 快照装配失败按命中保守处理
            logger.exception("risk lexicon snapshot load failed")
            return RiskService._unavailable(
                db, question, user_id, session, source_scene, f"词库快照加载失败：{exc}"
            )
        if not snapshot.usable():
            return RiskService._unavailable(
                db,
                question,
                user_id,
                session,
                source_scene,
                snapshot.degraded_reason or "词库快照不可信",
            )

        gateway = get_gateway()

        def semantic_fn(text: str) -> dict:
            """语义分类闭包：10s 超时，JSON 解析失败视为异常（保守命中）。

            Args:
                text: 待分类文本。

            Returns:
                {"score": float, "category": str|None}。

            Raises:
                LlmGatewayError: 网关调用失败/超时。
                ValueError: 返回内容无法解析为 JSON。
            """
            resp = gateway.chat(
                engine.build_semantic_messages(text), purpose="semantic", timeout=10.0
            )
            parsed = extract_json(resp["content"])
            if parsed is None or "score" not in parsed:
                raise ValueError("semantic risk response not json")
            return parsed

        risk_result = engine.decide(question, snapshot, semantic_fn)
        event_no = None
        if risk_result.get("blocked"):
            try:
                event_no = RiskService._record_event(
                    db, question, user_id, risk_result, session, source_scene
                )
            except Exception:  # noqa: BLE001 — 留痕失败不得推翻「命中即阻断」
                logger.exception("risk event record failed, keep blocked verdict")
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass
                if session is not None:
                    session.status = "blocked"
                    session.risk_level = "high"
                    session.risk_score_band = risk_result.get("score_band")
        return {"risk_result": risk_result, "risk_event_no": event_no}

    @staticmethod
    def unavailable_result(reason: str = "风险扫描服务不可用") -> dict:
        """构造「风险服务不可用」的保守拦截结果（PRD：按命中处理）。

        Args:
            reason: 不可用原因（写入 reason 便于后台排查）。

        Returns:
            与 engine 口径一致的 risk_result 字典（blocked=True，硬类别）。
        """
        return {
            "blocked": True,
            "level": "L1",
            "category_code": UNAVAILABLE_CATEGORY,
            "score": None,
            "score_band": "rule_hit",
            "hit_term": UNAVAILABLE_CATEGORY,
            "hit_source": "unavailable",
            "guide": False,
            "hard": True,
            "reason": f"风险扫描服务不可用，按命中保守处理（{reason}）",
        }

    @staticmethod
    def _unavailable(
        db: Session,
        question: str,
        user_id: int,
        session: Optional[QaSession],
        source_scene: str,
        reason: str,
    ) -> dict:
        """按命中保守处理：生成拦截结果并尽力留痕事件。

        Args:
            db: 数据库会话。
            question: 问题原文（仅用于字符长度观测）。
            user_id: 用户 id（落库前哈希）。
            session: 关联会话。
            source_scene: 来源场景。
            reason: 不可用原因。

        Returns:
            {"risk_result", "risk_event_no"}（落库失败时 event_no 为 None）。
        """
        risk_result = RiskService.unavailable_result(reason)
        try:
            event_no = RiskService._record_event(
                db, question, user_id, risk_result, session, source_scene
            )
        except Exception:  # noqa: BLE001 — 留痕失败不得推翻拦截结论
            logger.exception("risk unavailable event record failed")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            if session is not None:
                session.status = "blocked"
                session.risk_level = "high"
                session.risk_score_band = "rule_hit"
            event_no = None
        return {"risk_result": risk_result, "risk_event_no": event_no}

    @staticmethod
    def _record_event(
        db: Session,
        question: str,
        user_id: int,
        risk_result: dict,
        session: Optional[QaSession],
        source_scene: str,
    ) -> str:
        """命中后落库：写 RiskEvent + 置 qa_session blocked/high。

        Args:
            db: 数据库会话。
            question: 触发问题原文（仅用于 char_len 观测，不落原文）。
            user_id: 用户 id（落库前哈希，不可逆）。
            risk_result: 判定结果。
            session: 关联会话（None 时跳过会话置位）。
            source_scene: 来源场景。

        Returns:
            事件号 event_no。
        """
        event_no = f"RISK{_now_shanghai().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        event = RiskEvent(
            event_no=event_no,
            user_id_hash=sha256_hex(str(user_id)),
            session_id=session.id if session is not None else None,
            category_code=risk_result.get("category_code"),
            level=risk_result.get("level") or "L1",
            score_band=risk_result.get("score_band"),
            rule_hit_id=risk_result.get("category_code"),
            source_scene=source_scene,
            # 命中后正文为空 100%：不创建任何 answer section
            body_emitted=False,
            response_bytes=0,
        )
        db.add(event)
        if session is not None:
            session.status = "blocked"
            session.risk_level = "high"
            session.risk_score_band = risk_result.get("score_band")
        db.flush()
        return event_no

    # ------------------------------------------------------------------
    # 渠道卡
    # ------------------------------------------------------------------
    @staticmethod
    def get_channels(db: Session, category_code: Optional[str]) -> List[dict]:
        """按风险类别匹配危机干预渠道卡（RQ-03 单一数据源）。

        V3.1 起统一走 `services.channel_service`：渠道号码只来自
        `crisis_channel` 表（DR-26），后台维护页与拦截卡读同一张表
        （修复缺陷 N3 双数据源）；超期未复核条目自动降级为占位，
        前端不再展示号码（AC-RQ03-4）。

        Args:
            db: 数据库会话。
            category_code: 风险类别代码（None 时返回空列表）。

        Returns:
            渠道卡列表（含占位 / 维护中语义字段）。
        """
        from ..services import channel_service

        try:
            return channel_service.get_channels_for_category(db, category_code)
        except Exception:  # noqa: BLE001 — 渠道卡失败不推翻拦截结论
            logger.exception("channel lookup failed, fallback to empty list")
            return []

    # ------------------------------------------------------------------
    # 输出过滤（graph output_filter 节点使用）
    # ------------------------------------------------------------------
    @staticmethod
    def filter_blocks_content(sections: Any, snapshot: LexiconSnapshot) -> Any:
        """对全部 block content 再过一遍词库/正则，命中置空。

        Args:
            sections: 分节容器——dict {key: section} 或 List[section]，
                每个 section 含 blocks 列表（block 含 content 键）。
            snapshot: 词库快照。

        Returns:
            过滤后的原容器（命中 block 的 content 为空串，原地更新）。
        """
        container = sections.values() if isinstance(sections, dict) else (sections or [])
        for section in container:
            for block in section.get("blocks", []) or []:
                content = block.get("content")
                if isinstance(content, str):
                    block["content"] = engine.filter_content(content, snapshot)
        return sections

    # ------------------------------------------------------------------
    # 检索引用校验辅助
    # ------------------------------------------------------------------
    @staticmethod
    def evidence_filter(evidence_ref: Any, retrieved_docs: List[dict]) -> List[str]:
        """约束 evidence_ref 必须来自本次检索命中的 kb_id。

        Args:
            evidence_ref: 模型输出的引用列表（可能包含编造 id）。
            retrieved_docs: 本次检索返回的知识条目列表。

        Returns:
            过滤后合法 kb_id 列表（去重保序）。
        """
        if not evidence_ref:
            return []
        valid = {d.get("kb_id") for d in retrieved_docs if d.get("kb_id")}
        out: List[str] = []
        for ref in evidence_ref:
            if ref in valid and ref not in out:
                out.append(ref)
        return out


def load_kb_domain_names(db: Session) -> List[str]:  # pragma: no cover - 预留扩展
    """查询已发布知识条目覆盖的领域清单（预留：动态参与域判定）。

    Args:
        db: 数据库会话。

    Returns:
        领域代码列表（child/pet）。
    """
    rows = (
        db.query(KbEntry.domain)
        .filter(KbEntry.status == "published")
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows})

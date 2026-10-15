# -*- coding: utf-8 -*-
"""风险控制服务模块。

engine.py 之上的数据库/网关装配层：
- 词库快照加载（LexiconTerm 解密 + RiskRuleConfig 正则），进程内缓存 60s
  （cache 键 "lexicon:snapshot"）；
- scan 入口：两级流水线判定 + 命中后 RiskEvent 落库与 qa_session 状态置位；
- 危机干预渠道卡匹配（按 category_scope）。
"""
import json
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

# 词库快照缓存键与 TTL（秒）——变更后最迟 1 分钟全量生效
LEXICON_CACHE_KEY = "lexicon:snapshot"
LEXICON_CACHE_TTL = 60

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

        Args:
            db: 数据库会话。
            force_refresh: True 时绕过缓存强制刷新。

        Returns:
            LexiconSnapshot：词条（解密后明文）+ 正则配置。
            解密失败的词条跳过（不阻断扫描）。
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
                    )
                except Exception:  # noqa: BLE001 — 缓存损坏则回源重建
                    pass
        # 词条：effective=True，密文解密为明文（埋点只记哈希，此处为扫描必需）
        terms: List[dict] = []
        rows = db.query(LexiconTerm).filter(LexiconTerm.effective.is_(True)).all()
        for row in rows:
            try:
                term = decrypt_field(row.term_enc)
            except Exception:  # noqa: BLE001 — 单条解密失败不拖垮快照
                continue
            terms.append(
                {
                    "term": term,
                    "category_code": row.category_code,
                    "strategy": row.strategy,
                }
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
                # 引擎消费 "regex" 键；库内存法为 "pattern"——此处统一归一化
                regex_expr = cfg.get("regex") or cfg.get("pattern")
                if regex_expr:
                    patterns[key] = {
                        "regex": regex_expr,
                        "category_code": cfg.get("category_code") or cfg.get("action") or key,
                    }
        snapshot = LexiconSnapshot(
            terms=terms, patterns=patterns, loaded_at=time.time()
        )
        cache.set(
            LEXICON_CACHE_KEY,
            json.dumps(
                {
                    "terms": terms,
                    "patterns": patterns,
                    "loaded_at": snapshot.loaded_at,
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

        一级未命中时调 DeepSeek 语义分类（3s 超时，异常按命中保守处理）；
        命中时写 RiskEvent 并将 qa_session 置 blocked/high。

        Args:
            db: 数据库会话。
            question: 用户问题原文（纯输入侧判定，不读档案）。
            user_id: 当前用户 id（仅用于哈希落库）。
            session: 关联问答会话（None 时不落会话状态）。
            source_scene: 事件来源场景（qa/appeal）。

        Returns:
            {"risk_result": 完整判定结果, "risk_event_no": 事件号或 None}。
        """
        snapshot = RiskService.load_snapshot(db)
        gateway = get_gateway()

        def semantic_fn(text: str) -> dict:
            """语义分类闭包：3s 超时，JSON 解析失败视为异常（保守命中）。

            Args:
                text: 待分类文本。

            Returns:
                {"score": float, "category": str|None}。

            Raises:
                LlmGatewayError: 网关调用失败/超时。
                ValueError: 返回内容无法解析为 JSON。
            """
            resp = gateway.chat(
                engine.build_semantic_messages(text), purpose="semantic", timeout=3.0
            )
            parsed = extract_json(resp["content"])
            if parsed is None or "score" not in parsed:
                raise ValueError("semantic risk response not json")
            return parsed

        risk_result = engine.decide(question, snapshot, semantic_fn)
        event_no = None
        if risk_result.get("blocked"):
            event_no = RiskService._record_event(
                db, question, user_id, risk_result, session, source_scene
            )
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
        """按风险类别匹配危机干预渠道卡。

        Args:
            db: 数据库会话。
            category_code: 风险类别代码（None 时返回空列表）。

        Returns:
            渠道卡列表 [{channel_code, channel_name, phone_number, script}]，
            按 category_scope 包含该类别匹配（JSONB 数组）。
        """
        if not category_code:
            return []
        rows = db.query(CrisisChannel).all()
        out: List[dict] = []
        for row in rows:
            scope = row.category_scope or []
            if isinstance(scope, str):
                try:
                    scope = json.loads(scope)
                except Exception:  # noqa: BLE001
                    scope = []
            # category_scope 数组包含该类别才下发
            if category_code in scope:
                out.append(
                    {
                        "channel_code": row.channel_code,
                        "channel_name": row.channel_name,
                        "phone_number": row.phone_number,
                        "script": row.script,
                    }
                )
        return out

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

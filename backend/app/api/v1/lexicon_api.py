# -*- coding: utf-8 -*-
"""词库与风险规则维护路由模块。

覆盖词库热维护与一级规则引擎（PRD §14 / PA-04）：
- 词条 CRUD（term 密文存储、term_hash 去重、删除需二次确认）
- 风险规则配置（RiskRuleConfig 读写，变更后删缓存快照实现 1 分钟内生效）
- 规则测试器（对任意文本做词库 + 正则的一级引擎匹配，只读不改数据）

词条明文与哈希均不出审计（审计仅记录 hash/类型/策略等元数据）。
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.cache import cache
from ...core.crypto import decrypt_field, encrypt_field, sha256_hex
from ...core.deps import get_admin, require_admin_perm, require_confirm, write_audit
from ...core.envelope import ok
from ...core.errors import ERR_NOT_FOUND, ApiError
from ...db import get_db
from ...llm.gateway import extract_json, get_gateway
from ...models import AdminUser, ConfigVersion, LexiconTerm, RiskRuleConfig
from ...risk import engine as risk_engine
from ...risk.service import RiskService

# 词库路由统一挂在 /admin/lexicon 前缀
router = APIRouter(prefix="/admin/lexicon", tags=["后台-词库"])

# 词库快照缓存键（读取方以 TTL 60s 写入；变更时删除即 1 分钟内全量生效）
_LEXICON_SNAPSHOT_KEY = "lexicon:snapshot"

# 词库配置版本族键（后台「变更历史 / 一键回滚」经 /admin/configs/{key} 复用）
_LEXICON_CONFIG_KEY = "lexicon"

# 正则规则在 RiskRuleConfig 中的约定键名
_REGEX_RULES_KEY = "regex_rules"


def _now() -> datetime:
    """获取当前 UTC 时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(timezone.utc)


def _iso(dt) -> Optional[str]:
    """datetime 转 ISO 字符串（JSON 序列化辅助）。

    Args:
        dt: 时间对象，可为 None。

    Returns:
        ISO8601 字符串；入参为 None 时返回 None。
    """
    return dt.isoformat() if dt is not None else None


def _term_dict(t: LexiconTerm) -> dict:
    """词条序列化（term 解密展示）。

    Args:
        t: LexiconTerm ORM 实例。

    Returns:
        词条字典；密文解密失败时 term 为占位文本。
    """
    try:
        plain = decrypt_field(t.term_enc)
    except Exception:
        plain = "(解密失败)"
    return {
        "id": t.id,
        "term": plain,
        "term_hash": t.term_hash,
        "lexicon_type": t.lexicon_type,
        "strategy": t.strategy,
        "threshold_band": t.threshold_band,
        "category_code": t.category_code,
        "effective": t.effective,
        "version": t.version,
        "updated_at": _iso(t.updated_at),
    }


# ==================== 请求体模型 ====================


class TermCreateBody(BaseModel):
    """词条创建请求体。"""

    term: str = Field(..., min_length=1, description="词条明文（服务端加密落库）")
    lexicon_type: str = Field(..., description="词库类型：risk / sensitive")
    strategy: str = Field(..., description="处置策略：block / rewrite / degrade")
    threshold_band: Optional[str] = Field(None, description="分数带")
    category_code: Optional[str] = Field(None, description="类目编码")
    effective: bool = Field(True, description="是否生效")


class TermUpdateBody(BaseModel):
    """词条更新请求体（部分更新）。"""

    term: Optional[str] = Field(None, description="词条明文（变更时重算哈希）")
    strategy: Optional[str] = Field(None, description="处置策略")
    threshold_band: Optional[str] = Field(None, description="分数带")
    category_code: Optional[str] = Field(None, description="类目编码")
    effective: Optional[bool] = Field(None, description="是否生效")


class TermDeleteBody(BaseModel):
    """词条删除请求体（危险操作需二次确认）。"""

    confirm_token: Optional[str] = Field(None, description="二次确认凭证")


class RiskConfigBody(BaseModel):
    """风险规则配置更新请求体。"""

    config_value: Dict[str, Any] = Field(..., description="配置值（JSON 全量）")
    reason: Optional[str] = Field(None, description="变更原因（审计）")


class LexiconTestBody(BaseModel):
    """规则测试器请求体。"""

    text: str = Field(..., min_length=1, description="待检测文本")


# ==================== 词条管理 ====================


@router.get("/terms", summary="词条列表", description="分页查询（term 解密展示，含策略/分数带/生效态）")
def list_terms(
    type: Optional[str] = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """分页查询词库词条（term 解密展示，含策略/分数带/生效态/版本）。

    Args:
        type: 词库类型过滤（risk / sensitive）。
        page: 页码。
        page_size: 每页条数。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items, total, page, page_size}。

    Raises:
        ApiError: 1103 缺少 lex:view 权限。
    """
    require_admin_perm(admin, "lex:view")
    q = db.query(LexiconTerm)
    if type:
        q = q.filter(LexiconTerm.lexicon_type == type)
    total = q.count()
    rows = (
        q.order_by(LexiconTerm.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return ok(
        {"items": [_term_dict(t) for t in rows], "total": total, "page": page, "page_size": page_size}
    )


@router.post("/terms", summary="新增词条", description="term_hash 去重，明文加密落库，删词库缓存快照")
def create_term(
    body: TermCreateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """新增词条：term_hash 去重，明文加密落库，删词库缓存快照。

    Args:
        body: 词条创建请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{id, term_hash, lexicon_type, strategy}。

    Raises:
        ApiError: 1001 词条已存在；1103 缺少 lex:edit 权限。
    """
    require_admin_perm(admin, "lex:edit")
    term_hash = sha256_hex(body.term)
    exists = db.query(LexiconTerm).filter(LexiconTerm.term_hash == term_hash).first()
    if exists is not None:
        raise ApiError(1001, "词条已存在", 409)
    term = LexiconTerm(
        term_hash=term_hash,
        term_enc=encrypt_field(body.term),
        lexicon_type=body.lexicon_type,
        strategy=body.strategy,
        threshold_band=body.threshold_band,
        category_code=body.category_code,
        effective=body.effective,
        updated_by=admin.id,
        updated_at=_now(),
    )
    db.add(term)
    db.flush()
    # 快照缓存失效：读取方按 TTL 60s 重建，实现 1 分钟内全量生效
    cache.delete(_LEXICON_SNAPSHOT_KEY)
    # 审计不落词条明文/哈希原文语义（term_hash 本身即脱敏标识）
    write_audit(
        db,
        admin,
        "lexicon_add",
        "lexicon_term",
        str(term.id),
        reason="-",
        after={"term_hash": term_hash, "lexicon_type": term.lexicon_type, "strategy": term.strategy},
    )
    return ok(
        {"id": term.id, "term_hash": term_hash, "lexicon_type": term.lexicon_type, "strategy": term.strategy}
    )


@router.put("/terms/{term_id}", summary="更新词条", description="部分更新；term 变更时重算密文与哈希")
def update_term(
    term_id: int,
    body: TermUpdateBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """更新词条（部分字段），term 变更时重算密文与哈希。

    Args:
        term_id: 词条主键。
        body: 更新请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：更新后的词条。

    Raises:
        ApiError: 1002 词条不存在；1103 缺少 lex:edit 权限。
    """
    require_admin_perm(admin, "lex:edit")
    term = db.get(LexiconTerm, term_id)
    if term is None:
        raise ApiError(*ERR_NOT_FOUND)
    before = {"term_hash": term.term_hash, "strategy": term.strategy, "effective": term.effective}
    if body.term is not None:
        term.term_enc = encrypt_field(body.term)
        term.term_hash = sha256_hex(body.term)
    if body.strategy is not None:
        term.strategy = body.strategy
    if body.threshold_band is not None:
        term.threshold_band = body.threshold_band
    if body.category_code is not None:
        term.category_code = body.category_code
    if body.effective is not None:
        term.effective = body.effective
    term.updated_by = admin.id
    term.updated_at = _now()
    cache.delete(_LEXICON_SNAPSHOT_KEY)
    write_audit(
        db,
        admin,
        "lexicon_update",
        "lexicon_term",
        str(term.id),
        reason="-",
        before=before,
        after={"term_hash": term.term_hash, "strategy": term.strategy, "effective": term.effective},
    )
    return ok(_term_dict(term))


@router.delete("/terms/{term_id}", summary="删除词条", description="危险操作需二次确认（缺凭证 1602 无副作用）")
def delete_term(
    term_id: int,
    body: TermDeleteBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """删除词条（危险操作，缺二次确认直接 1602 且无副作用）。

    Args:
        term_id: 词条主键。
        body: 删除请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{id, deleted: True}。

    Raises:
        ApiError: 1002 词条不存在；1103 缺少 lex:edit；1602 缺少二次确认。
    """
    require_admin_perm(admin, "lex:edit")
    require_confirm(body.confirm_token, "lexicon_delete")
    term = db.get(LexiconTerm, term_id)
    if term is None:
        raise ApiError(*ERR_NOT_FOUND)
    before = {"term_hash": term.term_hash, "lexicon_type": term.lexicon_type}
    db.delete(term)
    cache.delete(_LEXICON_SNAPSHOT_KEY)
    write_audit(
        db,
        admin,
        "lexicon_delete",
        "lexicon_term",
        str(term_id),
        reason="-",
        before=before,
        confirm_used=True,
    )
    return ok({"id": term_id, "deleted": True})


# ==================== 风险规则配置 ====================


@router.get("/config", summary="风险规则配置列表", description="全部 RiskRuleConfig（two_level_threshold 等）")
def list_risk_configs(
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """查询全部风险规则配置（two_level_threshold 等）。

    Args:
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{items}。

    Raises:
        ApiError: 1103 缺少 lex:view 权限。
    """
    require_admin_perm(admin, "lex:view")
    rows = db.query(RiskRuleConfig).order_by(RiskRuleConfig.config_key.asc()).all()
    items = [
        {
            "config_key": r.config_key,
            "config_value": r.config_value,
            "effective_at": _iso(r.effective_at),
            "version": r.version,
            "updated_by": r.updated_by,
        }
        for r in rows
    ]
    return ok({"items": items})


@router.put("/config/{config_key}", summary="更新风险规则配置", description="upsert 配置并删词库快照缓存（1 分钟内生效）")
def update_risk_config(
    config_key: str,
    body: RiskConfigBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """更新风险规则配置（存在则改，不存在则建），删词库快照缓存。

    Args:
        config_key: 配置键（如 two_level_threshold）。
        body: 更新请求体。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{config_key, config_value}。

    Raises:
        ApiError: 1103 缺少 lex:edit 权限。
    """
    require_admin_perm(admin, "lex:edit")
    row = db.query(RiskRuleConfig).filter(RiskRuleConfig.config_key == config_key).first()
    before = None
    if row is not None:
        before = {"config_value": row.config_value}
        row.config_value = body.config_value
        row.effective_at = _now()
        row.updated_by = admin.id
        row.version += 1
    else:
        row = RiskRuleConfig(
            config_key=config_key,
            config_value=body.config_value,
            effective_at=_now(),
            updated_by=admin.id,
        )
        db.add(row)
        db.flush()
    cache.delete(_LEXICON_SNAPSHOT_KEY)
    write_audit(
        db,
        admin,
        "risk_config_update",
        "risk_rule_config",
        config_key,
        reason=body.reason or "-",
        before=before,
        after={"config_value": body.config_value},
    )
    # 版本留痕（DEF-18）：后台「变更历史」抽屉与一键回滚依赖 ConfigVersion；
    # 快照为全量（config_key → config_value），保证任意版本可完整回写
    version_rows = (
        db.query(ConfigVersion)
        .filter(ConfigVersion.config_key == _LEXICON_CONFIG_KEY)
        .all()
    )
    max_version = max((v.version for v in version_rows), default=0)
    for v in version_rows:
        if v.status == "active":
            v.status = "rolled_back"
    snapshot = {
        r.config_key: r.config_value
        for r in db.query(RiskRuleConfig).order_by(RiskRuleConfig.config_key.asc()).all()
    }
    db.add(
        ConfigVersion(
            config_type="lexicon",
            config_key=_LEXICON_CONFIG_KEY,
            version=max_version + 1,
            snapshot=snapshot,
            status="active",
            effective_at=_now(),
            reason=(body.reason or "-")[:128],
            operator_id=admin.id,
        )
    )
    # 响应返回即已提交（否则提交窗口内读取方可能仍命中删除前的旧词库快照）
    db.commit()
    return ok({"config_key": config_key, "config_value": row.config_value})


# ==================== 规则测试器（只读） ====================


@router.post("/test", summary="规则匹配测试", description="一级引擎只读测试：词库包含匹配 + 正则规则")
def test_lexicon(
    body: LexiconTestBody,
    admin: AdminUser = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """一级规则引擎匹配测试（PA-04）：只检测不改任何数据。

    词库命中：对全部生效词条解密后做包含匹配；
    正则命中：读 risk_rule_config.regex_rules（list[str]）逐条 re.search。

    Args:
        body: 测试请求体（text）。
        admin: 当前账号。
        db: 数据库会话。

    Returns:
        包络：{hit, matched_terms, matched_patterns, risk_result}，
        risk_result 为与线上问答风险引擎（engine.decide）完全一致的
        完整分级判定结构（level L1/L2 + score_band 档位 + category_code 类别），
        仅新增字段、向后兼容。

    Raises:
        ApiError: 1103 缺少 lex:view 权限。
    """
    require_admin_perm(admin, "lex:view")
    # P1 修复（e2e 实测发现）：规则测试器此前自查约定键 regex_rules（库中不存在），
    # 与线上问答引擎口径不一致——统一改走 RiskService.load_snapshot，
    # 保证 PA-04 测试器命中的规则与一级引擎实际执行完全一致
    snapshot = RiskService.load_snapshot(db)
    matched_terms: List[Dict[str, Any]] = []
    for t in snapshot.terms:
        plain = t.get("term") or ""
        if plain and plain in body.text:
            matched_terms.append(
                {
                    "term": plain,
                    "lexicon_type": t.get("lexicon_type", ""),
                    "strategy": t.get("strategy", ""),
                }
            )
    # 正则规则：与问答引擎同一快照（medicine_dosage/diagnosis/efficacy 等）
    matched_patterns: List[str] = []
    for key, cfg in snapshot.patterns.items():
        pattern = (cfg or {}).get("regex")
        if not pattern:
            continue
        try:
            if re.search(pattern, body.text):
                matched_patterns.append(f"{key}:{pattern}")
        except re.error:
            # 非法正则跳过，不影响其余规则
            continue
    hit = bool(matched_terms or matched_patterns)

    # 分级档位判定（SIM 台账 2.3）：复用与线上问答完全相同的两级流水线
    # （一级词库/正则 → 二级语义分级），响应新增 risk_result 字段供前端
    # 展示「命中 · 类别 · 一级拦截/二级引导」档位；只增不改，向后兼容
    gateway = get_gateway()

    def _semantic(text: str) -> dict:
        """语义分类闭包：与 RiskService.scan 内部实现同口径。

        Args:
            text: 待分类文本。

        Returns:
            {"score": float, "category": str|None}。

        Raises:
            LlmGatewayError: 网关调用失败/超时。
            ValueError: 返回内容无法解析为 JSON。
        """
        resp = gateway.chat(
            risk_engine.build_semantic_messages(text), purpose="semantic", timeout=10.0
        )
        parsed = extract_json(resp["content"])
        if parsed is None or "score" not in parsed:
            raise ValueError("semantic risk response not json")
        return parsed

    risk_result = risk_engine.decide(body.text, snapshot, _semantic)
    return ok(
        {
            "hit": hit,
            "matched_terms": matched_terms,
            "matched_patterns": matched_patterns,
            "risk_result": risk_result,
        }
    )

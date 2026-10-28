# -*- coding: utf-8 -*-
"""Agent 展示权重配置服务（PRD F12.7 / AC-F12-07-1~3）。

职责：

- 读取当前生效权重（`config_version` 表 `config_type=agent_weight`），
  60 秒进程内缓存，避免每次问答查询数据库；
- 保存新权重：校验取值范围与归一化、写新版本、旧 active 版本置
  `rolled_back`，并记录变更原因与操作人（diff 由调用方基于前后快照生成）；
- 历史查询与按版本回滚（回滚本身生成一个新版本，保留完整链路）。

设计口径：

- **安全分节 `pinned=true`，不参与权重排序**（GR-4），因此权重只允许
  `child` / `pet` 两个领域键；
- 未配置时返回默认等权（0.5 / 0.5，version=0），保证问答链路可用；
- 权重只影响非安全分节的展示顺序，不改变档位判定与内容生成。
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..core.cache import cache
from ..models import ConfigVersion

logger = logging.getLogger("jiaban.agent_weight")

# 配置版本键（与既有 ConfigVersion 复用，无需新表）
CONFIG_TYPE = "agent_weight"
CONFIG_KEY = "agent_weights"

# 运行时缓存键与 TTL（与词库/分级快照同口径：60 秒内全量生效）
CACHE_KEY = "agent_weights:active"
CACHE_TTL = 60

# 可配置领域（安全分节固定置顶，不参与权重排序）
WEIGHT_KEYS = ("child", "pet")

# 默认等权
DEFAULT_WEIGHTS: Dict[str, float] = {"child": 0.5, "pet": 0.5}


class WeightValidationError(ValueError):
    """权重非法（键不合法 / 越界 / 总和不等于 1）。"""


def _normalize_weights(raw: Any) -> Dict[str, float]:
    """校验并归一化权重字典。

    Args:
        raw: 原始权重（应为 {child: float, pet: float}）。

    Returns:
        归一化后的权重字典。

    Raises:
        WeightValidationError: 键非法、值非数字/越界、总和不等于 1（容差 1e-6）。
    """
    if not isinstance(raw, dict):
        raise WeightValidationError("weights 必须为对象")
    unknown = set(raw) - set(WEIGHT_KEYS)
    if unknown:
        raise WeightValidationError(f"不支持的权重键: {sorted(unknown)}")
    missing = set(WEIGHT_KEYS) - set(raw)
    if missing:
        raise WeightValidationError(f"缺少权重键: {sorted(missing)}")
    weights: Dict[str, float] = {}
    for key in WEIGHT_KEYS:
        try:
            value = float(raw[key])
        except (TypeError, ValueError) as exc:
            raise WeightValidationError(f"{key} 权重必须为数字") from exc
        if value < 0 or value > 1:
            raise WeightValidationError(f"{key} 权重必须在 0–1 之间")
        weights[key] = round(value, 4)
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise WeightValidationError(f"权重之和必须为 1（当前 {total:.4f}）")
    return weights


def _serialize_active(row: Optional[ConfigVersion]) -> Dict[str, Any]:
    """把配置行转为对外视图。

    Args:
        row: active 配置行（None 时返回默认值）。

    Returns:
        {weights, version, updated_at, operator_id, reason, defaults}。
    """
    if row is None:
        return {
            "weights": dict(DEFAULT_WEIGHTS),
            "version": 0,
            "updated_at": None,
            "operator_id": None,
            "reason": None,
            "defaults": dict(DEFAULT_WEIGHTS),
            "safety_pinned": True,
        }
    snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
    weights = snapshot.get("weights") if isinstance(snapshot, dict) else None
    try:
        weights = _normalize_weights(weights)
    except WeightValidationError:
        weights = dict(DEFAULT_WEIGHTS)
    return {
        "weights": weights,
        "version": int(row.version or 0),
        "updated_at": row.effective_at.isoformat() if row.effective_at else None,
        "operator_id": row.operator_id,
        "reason": row.reason,
        "defaults": dict(DEFAULT_WEIGHTS),
        "safety_pinned": True,
    }


def get_active(db: Optional[Session] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """读取当前生效权重（缓存 60 秒；无配置时返回默认等权）。

    Args:
        db: 数据库会话（None 时返回默认权重）。
        force_refresh: True 时绕过缓存。

    Returns:
        {weights, version, updated_at, operator_id, reason, defaults, safety_pinned}
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except Exception:  # noqa: BLE001 — 缓存损坏回源重建
                pass
    view = _serialize_active(None)
    if db is not None:
        try:
            row = (
                db.query(ConfigVersion)
                .filter(
                    ConfigVersion.config_type == CONFIG_TYPE,
                    ConfigVersion.config_key == CONFIG_KEY,
                    ConfigVersion.status == "active",
                )
                .order_by(ConfigVersion.version.desc())
                .first()
            )
            view = _serialize_active(row)
        except Exception:  # noqa: BLE001 — 表未建/查询失败回退默认等权
            logger.warning("agent weight query failed, fallback to defaults", exc_info=True)
    try:
        cache.set(CACHE_KEY, json.dumps(view, ensure_ascii=False), ttl_seconds=CACHE_TTL)
    except Exception:  # noqa: BLE001 — 缓存写入失败不影响本次读取
        pass
    return view


def save_weights(
    db: Session,
    operator_id: Optional[int],
    weights: Any,
    reason: str,
    rollback_from_version: Optional[int] = None,
) -> Dict[str, Any]:
    """保存新权重版本（旧 active 置 rolled_back）。

    Args:
        db: 数据库会话。
        operator_id: 操作人主键（后台账号）。
        weights: 待保存权重（未 commit）。
        reason: 变更原因（必填，≤128 字）。
        rollback_from_version: 回滚来源版本（非回滚时 None）。

    Returns:
        {weights, version, before, diff, rollback_from_version}。

    Raises:
        WeightValidationError: 权重非法。
    """
    normalized = _normalize_weights(weights)
    text = (reason or "").strip()
    if not text:
        raise WeightValidationError("变更原因不能为空")
    before_view = get_active(db, force_refresh=True)
    rows = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.config_type == CONFIG_TYPE,
            ConfigVersion.config_key == CONFIG_KEY,
        )
        .all()
    )
    max_version = max((row.version for row in rows), default=0)
    for row in rows:
        if row.status == "active":
            row.status = "rolled_back"
    version = max_version + 1
    db.add(
        ConfigVersion(
            config_type=CONFIG_TYPE,
            config_key=CONFIG_KEY,
            version=version,
            snapshot={"weights": normalized, "safety_pinned": True},
            status="active",
            effective_at=datetime.now(timezone.utc),
            reason=text[:128],
            operator_id=operator_id,
            rollback_from_version=rollback_from_version,
        )
    )
    db.flush()
    diff = {
        key: {
            "before": before_view["weights"].get(key),
            "after": normalized.get(key),
        }
        for key in WEIGHT_KEYS
        if before_view["weights"].get(key) != normalized.get(key)
    }
    view = {
        "weights": normalized,
        "version": version,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "operator_id": operator_id,
        "reason": text[:128],
        "defaults": dict(DEFAULT_WEIGHTS),
        "safety_pinned": True,
    }
    cache.set(CACHE_KEY, json.dumps(view, ensure_ascii=False), ttl_seconds=CACHE_TTL)
    return {
        "weights": normalized,
        "version": version,
        "before": before_view["weights"],
        "diff": diff,
        "rollback_from_version": rollback_from_version,
    }


def list_history(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """查询权重历史版本（按版本倒序）。

    Args:
        db: 数据库会话。
        limit: 最大返回条数。

    Returns:
        历史版本列表（含当前 active 标记）。
    """
    rows = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.config_type == CONFIG_TYPE,
            ConfigVersion.config_key == CONFIG_KEY,
        )
        .order_by(ConfigVersion.version.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    items: List[Dict[str, Any]] = []
    for row in rows:
        snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
        try:
            weights = _normalize_weights(snapshot.get("weights"))
        except WeightValidationError:
            weights = dict(DEFAULT_WEIGHTS)
        items.append(
            {
                "version": int(row.version),
                "weights": weights,
                "status": row.status,
                "effective_at": row.effective_at.isoformat() if row.effective_at else None,
                "operator_id": row.operator_id,
                "reason": row.reason,
                "rollback_from_version": row.rollback_from_version,
            }
        )
    return items


def rollback_to(
    db: Session, operator_id: Optional[int], target_version: int, reason: str
) -> Dict[str, Any]:
    """回滚到指定历史版本（以新版本形式生效）。

    Args:
        db: 数据库会话。
        operator_id: 操作人主键。
        target_version: 目标版本号。
        reason: 回滚原因（必填）。

    Returns:
        save_weights 的返回结构。

    Raises:
        WeightValidationError: 目标版本不存在或快照非法。
    """
    row = (
        db.query(ConfigVersion)
        .filter(
            ConfigVersion.config_type == CONFIG_TYPE,
            ConfigVersion.config_key == CONFIG_KEY,
            ConfigVersion.version == target_version,
        )
        .first()
    )
    if row is None:
        raise WeightValidationError(f"目标版本不存在: {target_version}")
    snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
    weights = snapshot.get("weights")
    return save_weights(
        db,
        operator_id,
        weights,
        reason,
        rollback_from_version=target_version,
    )

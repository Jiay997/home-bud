# -*- coding: utf-8 -*-
"""图片提问链路服务（RQ-05 / NFR-S7 / DR-27 / DR-28）。

链路（PRD §5.4）：拍照/相册 → **场景化前置说明 + 授权** → 选图 ≤3 张
（前端压缩、剥离 EXIF）→ **微信图片送检** → 通过后进入多模态解析 →
科普解析 + 就医引导（无诊断结论）→ **24 h 内原图删除（任务 + 日志）**。

红线落地（逐条可核验）：

- AC-RQ05-2：送检未通过或超配额**即拒绝、不进入推理**，且**不扣额度**；
- AC-RQ05-3 / DR-27：原图与中间帧 24 h 内删除，删除任务出执行日志
  （`photo_asset.delete_log`），仅保留元数据；
- AC-RQ05-4 / DR-28 / NFR-S7：图片**不用于训练、不进日志、不进埋点**、
  后台**无原图查看接口**；`photo_asset` 表只存元数据，`file_path` 仅供
  删除任务使用，任何接口都不下发；
- EXIF 在上传时剥离（复用 `media_store.save_image` 的规范化路径，Pillow
  重编码天然不保留 EXIF）；
- 儿童影像按敏感个人信息处理：目的仅限本次问答解析，处理后即删。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import PhotoAsset
from . import media_store
from .safety_scan import SafetyScanService

logger = logging.getLogger("jiaban.photo")

# 上海时区
_TZ_SHANGHAI = timezone(timedelta(hours=8))

# 场景枚举（五类高频视觉场景 + unknown）
SCENES = ("rash", "stool", "vomit", "food_label", "medicine_pack", "unknown")

# 场景 → 拍摄要点（AC-RQ05-1 场景化前置说明文案）
SCENE_GUIDES: Dict[str, Dict[str, str]] = {
    "rash": {"label": "皮疹", "guide": "在自然光下拍全皮疹区域，避免逆光与滤镜"},
    "stool": {"label": "便便", "guide": "拍全性状与颜色，注明拍摄时间"},
    "vomit": {"label": "呕吐物", "guide": "拍全性状与量，避免只拍局部"},
    "food_label": {"label": "宠粮配料表", "guide": "配料表拍全、文字清晰、光线充足"},
    "medicine_pack": {"label": "药品包装", "guide": "拍全药名与规格，**不要**拍剂量用法特写"},
    "unknown": {"label": "其他", "guide": "尽量拍全主体，光线充足"},
}

# 场景化前置说明（AC-RQ05-1：拍什么、照片如何被处理、何时删除）
PRIVACY_NOTICE = (
    "照片仅用于本次问答的科普解析，不用于模型训练、不进日志与埋点，"
    f"服务端在 {get_settings().photo_qa_ttl_hours} 小时内自动删除原图。"
    "请只拍摄自家孩子或自家宠物，避免拍到他人在场。"
)

# 送检未通过提示（同时给出文字问答降级路径）
REJECT_NOTICE = "图片内容安全送检未通过，已停止解析；你可以改为文字描述继续提问。"

# 多模态解析占位口径（真实多模态链路未接入时的诚实回复）
PARSE_STUB_NOTICE = (
    "已收到你的图片，但当前环境未接入多模态解析能力，无法从图片中提取内容；"
    "请补充文字描述（例如部位、颜色、持续时间），我会按文字问答为你提供科普参考。"
)

# 平台配额超限提示
QUOTA_NOTICE = "今日图片安全送检配额已用尽，图片未进入解析（不扣额度）；请改用文字提问。"


def _now() -> datetime:
    """当前上海时间。

    Returns:
        带时区的 datetime。
    """
    return datetime.now(_TZ_SHANGHAI)


def scene_guide(scene: Optional[str] = None) -> Dict[str, Any]:
    """返回场景化前置说明（授权前的信息告知）。

    Args:
        scene: 场景枚举（None 表示返回全部场景引导）。

    Returns:
        {scenes: [...], selected: {...}|None, privacy_notice, max_count, ttl_hours}。
    """
    settings = get_settings()
    items = [
        {"scene": key, "label": value["label"], "guide": value["guide"]}
        for key, value in SCENE_GUIDES.items()
    ]
    selected = None
    if scene:
        value = SCENE_GUIDES.get(scene)
        if value is not None:
            selected = {"scene": scene, "label": value["label"], "guide": value["guide"]}
    return {
        "scenes": items,
        "selected": selected,
        "privacy_notice": PRIVACY_NOTICE,
        "max_count": settings.photo_qa_max_count,
        "ttl_hours": settings.photo_qa_ttl_hours,
        "degradation": "拒绝相机 / 相册授权可直接使用文字问答，不影响主流程",
    }


def submit_photo(
    db: Session,
    user_id: int,
    data: bytes,
    filename: str,
    scene: str = "unknown",
    now: Optional[datetime] = None,
) -> Tuple[Optional[PhotoAsset], Optional[Tuple[int, str, int]]]:
    """上传并送检一张图片（送检未通过即拒绝，不进入推理）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        data: 原始图片字节（前端已压缩、剥离 EXIF）。
        filename: 原始文件名（仅用于格式校验提示，不入盘不入库）。
        scene: 场景枚举。
        now: 参考时间。

    Returns:
        (photo_asset, error)：成功时 error 为 None；失败时 asset 为 None 且
        error 为 (code, message, http_status) 三元组（供路由层抛 ApiError）。

    Raises:
        无（所有失败以返回值表达，避免留下半成品文件）。
    """
    settings = get_settings()
    current = now or _now()
    if scene not in SCENES:
        scene = "unknown"
    # 配额闸门先查：超配额直接拒绝（不占存储、不落元数据）
    try:
        SafetyScanService.check_quota(db)
    except Exception:  # noqa: BLE001 — 1303 配额超限
        logger.warning("photo quota exceeded before moderation: user=%s", user_id)
        return None, (1303, QUOTA_NOTICE, 429)
    try:
        # save_image 重编码为 JPEG：EXIF 与原始元数据在编码时被剥离
        rel_path, width, height, size = media_store.save_image(
            data, "qa_photos", media_store.PHOTO_MAX_SIDE
        )
    except media_store.MediaValidationError as exc:
        return None, (1001, f"图片校验失败：{exc}", 422)
    except Exception as exc:  # noqa: BLE001 — 落盘异常按参数/依赖错误处理
        logger.exception("photo save failed: %s", exc)
        return None, (1001, "图片保存失败，请重试", 422)
    # 送检：文本化裁决（真实平台接入后改为图片二进制送检）
    record = SafetyScanService.submit(
        db, object_type="photo", object_id=f"{user_id}-{current.timestamp():.0f}", scene=scene,
        content=f"photo:{scene}:{size}",
    )
    verdict = SafetyScanService._local_rule_verdict(f"photo:{scene}:{size}")
    SafetyScanService.resolve(db, record.id, verdict=verdict, note="photo-pipeline")
    if verdict != "pass":
        # 送检未通过：立即删除文件，不留存、不扣额度
        media_store.delete_file(rel_path)
        return None, (1303, REJECT_NOTICE, 403)
    asset = PhotoAsset(
        user_id=user_id,
        scene=scene,
        moderation_result="pass",
        moderation_at=current,
        file_path=rel_path,
        file_size=size,
        width=width,
        height=height,
        expires_at=current + timedelta(hours=settings.photo_qa_ttl_hours),
    )
    db.add(asset)
    db.flush()
    return asset, None


def validate_photo_refs(
    db: Session, user_id: int, photo_uids: List[str], now: Optional[datetime] = None
) -> Optional[Tuple[int, str, int]]:
    """校验图片标识（归属 / 已送检 / 未过期 / 张数上限）。

    Args:
        db: 数据库会话。
        user_id: 用户主键。
        photo_uids: 图片标识列表。
        now: 参考时间。

    Returns:
        None 表示校验通过；否则返回 (code, message, http_status)。
    """
    settings = get_settings()
    uids = [uid for uid in (photo_uids or []) if uid]
    if not uids:
        return (1001, "photo 模式需至少提供 1 张图片", 422)
    if len(uids) > settings.photo_qa_max_count:
        return (1001, f"单次最多上传 {settings.photo_qa_max_count} 张图片", 422)
    if len(set(uids)) != len(uids):
        return (1001, "图片标识重复", 422)
    current = now or _now()
    rows = (
        db.query(PhotoAsset)
        .filter(PhotoAsset.photo_uid.in_(uids), PhotoAsset.user_id == user_id)
        .all()
    )
    by_uid = {row.photo_uid: row for row in rows}
    for uid in uids:
        asset = by_uid.get(uid)
        if asset is None:
            return (1002, "图片不存在或已过期", 404)
        if asset.moderation_result != "pass":
            return (1303, REJECT_NOTICE, 403)
        if asset.deleted_at is not None or asset.expires_at <= current:
            return (1002, "图片已过期（原图已删除），请重新上传", 404)
        if asset.session_id is not None:
            return (1001, "该图片已用于其他提问", 422)
    return None


def bind_to_session(db: Session, session_id: int, photo_uids: List[str]) -> Dict[str, Any]:
    """把图片绑定到会话并返回会话级元数据摘要（无 URL、无原图）。

    Args:
        db: 数据库会话。
        session_id: 会话主键。
        photo_uids: 图片标识列表。

    Returns:
        photo_meta 摘要：{count, scenes[], moderation_results[], expires_at,
        deleted_at, photo_uids[]}（供 qa_session.photo_meta 落库）。
    """
    if not photo_uids:
        return {}
    rows = (
        db.query(PhotoAsset).filter(PhotoAsset.photo_uid.in_(photo_uids)).all()
    )
    scenes: List[str] = []
    results: List[str] = []
    expires: List[str] = []
    for row in rows:
        row.session_id = session_id
        if row.scene not in scenes:
            scenes.append(row.scene)
        results.append(row.moderation_result)
        expires.append(row.expires_at.isoformat() if row.expires_at else "")
    return {
        "count": len(rows),
        "scenes": scenes,
        "moderation_results": results,
        "expires_at": max(expires) if expires else None,
        "photo_uids": list(photo_uids),
        "deleted_at": None,
    }


def photo_context_hint(db: Session, photo_uids: List[str]) -> str:
    """构造图片上下文的**文本**提示（不传图片数据给模型）。

    Args:
        db: 数据库会话。
        photo_uids: 图片标识列表。

    Returns:
        中文提示串（为空表示无图片）。
    """
    if not photo_uids:
        return ""
    rows = db.query(PhotoAsset).filter(PhotoAsset.photo_uid.in_(photo_uids)).all()
    labels = []
    for row in rows:
        label = SCENE_GUIDES.get(row.scene, SCENE_GUIDES["unknown"])["label"]
        if label not in labels:
            labels.append(label)
    if not labels:
        return ""
    return (
        f"用户上传了 {len(rows)} 张图片（类型：{'、'.join(labels)}）。"
        f"当前环境未接入多模态解析，{PARSE_STUB_NOTICE}"
    )


def purge_expired(db: Session, now: Optional[datetime] = None) -> int:
    """删除到期原图并写删除日志（DR-27 / AC-RQ05-3）。

    Args:
        db: 数据库会话。
        now: 参考时间。

    Returns:
        本次删除的图片数（含文件已丢失的情况，仍记删除日志）。
    """
    current = now or _now()
    rows = (
        db.query(PhotoAsset)
        .filter(
            PhotoAsset.deleted_at.is_(None),
            PhotoAsset.expires_at <= current,
        )
        .all()
    )
    removed = 0
    for row in rows:
        existed = False
        try:
            existed = media_store.delete_file(row.file_path or "")
        except Exception as exc:  # noqa: BLE001 — 单条删除失败不中断整批
            logger.error("photo purge failed uid=%s: %s", row.photo_uid, exc)
        row.deleted_at = current
        row.delete_log = {
            "deleted_at": current.isoformat(),
            "by": "job:photo_purge",
            "file_existed": existed,
            "bytes": row.file_size,
            "result": "ok",
        }
        row.file_path = None  # 删除后不再保有路径（最小化）
        removed += 1
        logger.info(
            "photo_deleted_done uid=%s existed=%s bytes=%s",
            row.photo_uid,
            existed,
            row.file_size,
        )
    if removed:
        db.commit()
    return removed


def meta_summary(db: Session, photo_uids: List[str]) -> Dict[str, Any]:
    """查询图片元数据摘要（不返回任何可访问原图的信息）。

    Args:
        db: 数据库会话。
        photo_uids: 图片标识列表。

    Returns:
        {items: [{photo_uid, scene, moderation_result, expires_at, deleted_at}]}。
    """
    if not photo_uids:
        return {"items": []}
    rows = db.query(PhotoAsset).filter(PhotoAsset.photo_uid.in_(photo_uids)).all()
    return {
        "items": [
            {
                "photo_uid": row.photo_uid,
                "scene": row.scene,
                "moderation_result": row.moderation_result,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
            }
            for row in rows
        ]
    }

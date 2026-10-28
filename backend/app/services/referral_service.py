# -*- coding: utf-8 -*-
"""LBS 就近就医转介服务（RQ-04 预留实现 / NFR-S8）。

合规红线（逐条落地）：

- **精确坐标不落库、不进埋点**（AC-RQ04-4 / DR-28）：入口只接受
  `region_city` / `region_district` 文本与可选的 `lat/lng`（仅用于
  本次排序计算，**立即丢弃，不写库、不写日志**）；
- **只推荐官方与持牌机构 POI**，每条带 `data_source` 与更新时间
  （AC-RQ04-5）；POI 数据源未接入时**不编造机构**，返回
  `available=false` + 城市级急诊指引降级（AC-RQ04-3 / §3.4.4）；
- **不排名、不导流**（NG-10 / AC-RQ04-2 / AC-RQ04-6）：不出现「推荐 /
  最佳 / 官方合作」表述，统一口径「附近机构信息，请自行核实接诊状态」；
- 转介记录只写市 / 区级（`referral_log`）。

依赖状态（诚实声明）：`settings.referral_enabled` 默认 **False**——
位置能力类目资质（D11）与 POI 数据源口径（Q-52）未定稿前不对外承诺可用。
"""
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import ReferralLog

logger = logging.getLogger("jiaban.referral")

# 触发场景（PRD §3.4.3 触发点）
SCENES = ("emergency_block", "triage_red", "pet_redflag")

# 免责与展示口径（AC-RQ04-6：禁止「推荐 / 最佳 / 官方合作」表述）
DISPLAY_NOTICE = "附近机构信息，请自行核实接诊状态。"

# POI 数据来源标注（AC-RQ04-5）
DATA_SOURCES = {
    "official_directory": "官方机构名录",
    "licensed_vet": "持牌宠物医院公开名录",
    "partner_network": "合作问诊网络公开信息",
}

# 距离档（不展示精确距离，避免暴露位置精度）
DISTANCE_BANDS = ("近（≤3km）", "中（3–10km）", "远（>10km）")

# 城市级降级指引（无 POI 时）
CITY_FALLBACK_GUIDE = (
    "可就近选择设有急诊的儿童医院 / 24 小时宠物医院；紧急情况请拨打 120 / 110，"
    "宠物急症可先电话确认是否接诊。"
)

# 单次返回机构上限（AC-RQ04-2：≤5 家）
MAX_POI = 5


class PoiUnavailable(RuntimeError):
    """POI 数据源不可用（按降级口径返回城市级指引）。"""


def _band(distance_km: Optional[float]) -> Optional[str]:
    """把距离换算为距离档（不暴露精确坐标）。

    Args:
        distance_km: 距离（公里）。

    Returns:
        距离档文案；无法计算返回 None。
    """
    if distance_km is None:
        return None
    if distance_km <= 3:
        return DISTANCE_BANDS[0]
    if distance_km <= 10:
        return DISTANCE_BANDS[1]
    return DISTANCE_BANDS[2]


def haversine_km(
    lat1: Optional[float], lng1: Optional[float], lat2: Optional[float], lng2: Optional[float]
) -> Optional[float]:
    """计算球面距离（仅用于即时排序，不落库）。

    Args:
        lat1: 用户纬度。
        lng1: 用户经度。
        lat2: 机构纬度。
        lng2: 机构经度。

    Returns:
        距离（公里）；任一参数缺失返回 None。
    """
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        radius = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)
        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return round(2 * radius * math.asin(math.sqrt(a)), 2)
    except Exception:  # noqa: BLE001 — 计算异常按不可用处理
        return None


def list_poi(db: Session, city: Optional[str], district: Optional[str]) -> List[Dict[str, Any]]:
    """读取合规 POI 列表（当前无数据源接入，返回空列表）。

    真实接入口径（Q-52 定稿后实现）：官方机构名录 + 持牌宠物医院公开名录，
    逐条带 `data_source` 与 `updated_at`；**不得爬取、不得编造**。

    Args:
        db: 数据库会话。
        city: 城市。
        district: 区县。

    Returns:
        机构列表（当前实现恒为空，触发降级口径）。
    """
    return []


def nearby(
    db: Session,
    scene: str,
    city: Optional[str],
    district: Optional[str],
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    clicked: bool = False,
) -> Dict[str, Any]:
    """查询附近合规机构（含降级与合规留痕）。

    Args:
        db: 数据库会话。
        scene: 触发场景。
        city: 城市（唯一可落库的位置信息）。
        district: 区县。
        lat: 用户纬度（仅本次计算，不落库、不写日志）。
        lng: 用户经度（同上）。
        session_id: 会话主键（归因）。
        user_id: 用户主键。
        clicked: 是否已点击机构条目。

    Returns:
        {available, items[], notice, fallback_guide, region, data_sources, enabled}。
    """
    settings = get_settings()
    if scene not in SCENES:
        scene = "emergency_block"
    region = {"city": city, "district": district}
    if not settings.referral_enabled:
        record_referral(
            db,
            scene=scene,
            region=region,
            poi_count=0,
            clicked=clicked,
            session_id=session_id,
            user_id=user_id,
            data_source=None,
        )
        return {
            "available": False,
            "enabled": False,
            "items": [],
            "notice": DISPLAY_NOTICE,
            "fallback_guide": CITY_FALLBACK_GUIDE,
            "region": region,
            "reason": "位置能力与 POI 数据源未定稿（D11 / Q-52），当前仅提供城市级急诊指引",
        }
    items = list_poi(db, city, district)
    if not items:
        record_referral(
            db,
            scene=scene,
            region=region,
            poi_count=0,
            clicked=clicked,
            session_id=session_id,
            user_id=user_id,
            data_source=None,
        )
        return {
            "available": False,
            "enabled": True,
            "items": [],
            "notice": DISPLAY_NOTICE,
            "fallback_guide": CITY_FALLBACK_GUIDE,
            "region": region,
            "reason": "附近无已核验的合规机构信息",
        }
    # 距离档排序仅用于展示顺序，不构成「推荐排名」（AC-RQ04-2）
    decorated: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        distance = haversine_km(lat, lng, item.get("lat"), item.get("lng"))
        public = {
            "name": item.get("name"),
            "address": item.get("address"),
            "service_hours": item.get("service_hours"),
            "distance_band": _band(distance),
            "data_source": DATA_SOURCES.get(item.get("data_source", ""), "官方公开信息"),
            "updated_at": item.get("updated_at"),
        }
        decorated.append((distance if distance is not None else 9999.0, public))
    decorated.sort(key=lambda pair: pair[0])
    out = [public for _, public in decorated[:MAX_POI]]
    record_referral(
        db,
        scene=scene,
        region=region,
        poi_count=len(out),
        clicked=clicked,
        session_id=session_id,
        user_id=user_id,
        data_source="official_directory",
    )
    return {
        "available": True,
        "enabled": True,
        "items": out,
        "notice": DISPLAY_NOTICE,
        "fallback_guide": None,
        "region": region,
    }


def record_referral(
    db: Session,
    scene: str,
    region: Dict[str, Optional[str]],
    poi_count: int,
    clicked: bool,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    data_source: Optional[str] = None,
) -> ReferralLog:
    """写转介记录（仅市 / 区级，无经纬度列）。

    Args:
        db: 数据库会话。
        scene: 场景。
        region: {city, district}。
        poi_count: 返回机构数。
        clicked: 是否点击。
        session_id: 会话主键。
        user_id: 用户主键。
        data_source: 数据来源标注。

    Returns:
        新建记录（未 commit）。
    """
    row = ReferralLog(
        session_id=session_id,
        user_id=user_id,
        scene=scene,
        region_city=(region or {}).get("city"),
        region_district=(region or {}).get("district"),
        poi_count=int(poi_count or 0),
        clicked=bool(clicked),
        data_source=data_source,
    )
    db.add(row)
    return row

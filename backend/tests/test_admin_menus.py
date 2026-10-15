# -*- coding: utf-8 -*-
"""菜单键单一事实来源一致性测试（DEF-14 回归守护，不依赖数据库）。

背景：后台侧边栏权限曾因"后端下发缩写键（lex/log/fb/cfg）+ 前端全称键
（lexicon/logs/feedback/config）双份维护"导致超管菜单被误置灰、审计记录
全角色不可达（DEF-14）。现约定：后端 ROLE_MENUS 为唯一枚举源，键集合与
前端 MENU_DEFS 逐字一致，前端不做任何别名/兜底映射（挂载时经 /me 刷新）。

覆盖：
- 各角色菜单清单锁定（行为基线，变更须显式同步本测试与文档）；
- 全角色键 ⊆ 前端菜单键集合（缩写键回潮/拼写漂移/死键即时失败）；
- 超管拥有全部菜单键（全菜单可达基线）；
- 前端 AdminLayout.vue 交叉校验：MENU_DEFS 键集合一致，且不得回潮
  本地角色映射或别名表（双份维护守护）；
- audit 菜单角色 == /admin/audit-logs 接口角色白名单（仅超管，源码内联条件校验）；
- _admin_menus 分发：未知角色返回空列表（fail-closed）。
"""
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.admin_api import ROLE_MENUS, _admin_menus  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
ADMIN_API_PY = BACKEND_DIR / "app" / "api" / "v1" / "admin_api.py"
ADMIN_LAYOUT_VUE = (
    BACKEND_DIR.parent / "frontend" / "src" / "views" / "admin" / "AdminLayout.vue"
)

# 前端侧边栏菜单键（AdminLayout.vue MENU_DEFS；系统监控为模板硬编码展示项，不在权限枚举内）
FRONTEND_MENU_KEYS = {"kb", "lexicon", "logs", "feedback", "risk", "rights", "config", "audit"}

# 角色 → 菜单行为基线（唯一事实来源：admin_api.py::ROLE_MENUS）
# 越权修复：audit（审计记录）为超管专属，operator/support 不再下发该菜单
EXPECTED_ROLE_MENUS = {
    "super_admin": ["kb", "lexicon", "logs", "feedback", "risk", "rights", "config", "audit"],
    "operator": ["kb", "lexicon", "logs", "feedback", "risk", "rights"],
    "support": ["feedback", "rights", "logs"],
    "expert_child": ["kb"],
    "expert_pet": ["kb"],
}

# /admin/audit-logs 接口角色白名单（源码内联条件，见 list_audit_logs）
AUDIT_API_ROLES = {"super_admin"}


def _layout_source() -> str:
    """读取前端后台布局源文件。

    Returns:
        文件全文。

    Raises:
        AssertionError: 文件缺失（测试前置条件不满足）。
    """
    assert ADMIN_LAYOUT_VUE.exists(), f"前端布局文件不存在：{ADMIN_LAYOUT_VUE}"
    return ADMIN_LAYOUT_VUE.read_text(encoding="utf-8")


def _menu_defs_keys(source: str) -> set:
    """从 AdminLayout.vue 的 MENU_DEFS 定义块中提取菜单键。

    Args:
        source: AdminLayout.vue 全文。

    Returns:
        菜单键集合（每项形如 `key: 'xxx'`）。
    """
    start = source.index("const MENU_DEFS")
    end = source.index("function resolveMenuPath", start)
    return set(re.findall(r"key: '([^']+)'", source[start:end]))


def test_role_menus_baseline_locked():
    """各角色菜单清单与行为基线一致（显式变更须修改本测试与文档）。"""
    assert set(ROLE_MENUS) == set(EXPECTED_ROLE_MENUS)
    for role, expected in EXPECTED_ROLE_MENUS.items():
        assert sorted(ROLE_MENUS[role]) == sorted(expected), f"{role} 菜单清单漂移：{ROLE_MENUS[role]}"


def test_role_menus_keys_within_frontend_menu_keys():
    """全角色下发键必须落在前端菜单键集合内（防缩写键回潮/拼写漂移/死键）。"""
    for role, keys in ROLE_MENUS.items():
        unknown = set(keys) - FRONTEND_MENU_KEYS
        assert not unknown, f"{role} 含前端不存在的菜单键：{sorted(unknown)}"


def test_super_admin_granted_all_frontend_menu_keys():
    """超管须拥有全部前端菜单键（全菜单可达基线）。"""
    missing = FRONTEND_MENU_KEYS - set(ROLE_MENUS["super_admin"])
    assert not missing, f"super_admin 缺少菜单键：{sorted(missing)}"


def test_frontend_menu_defs_keys_match_baseline():
    """前端 MENU_DEFS 键集合与行为基线一致（逐字对齐后端枚举）。"""
    assert _menu_defs_keys(_layout_source()) == FRONTEND_MENU_KEYS


def test_frontend_has_no_dual_maintenance_mapping():
    """前端不得回潮本地角色映射/别名表（权限唯一来源为后端下发 menus）。"""
    src = _layout_source()
    assert "MENU_KEY_ALIASES" not in src, "前端别名映射表回潮（DEF-14 类双份维护）"
    assert "const ROLE_MENUS" not in src, "前端本地角色菜单映射回潮（双份维护）"


def test_audit_menu_roles_match_audit_api_whitelist():
    """含 audit 菜单的角色 == /admin/audit-logs 接口角色白名单（仅 super_admin）。"""
    menu_roles = {role for role, keys in ROLE_MENUS.items() if "audit" in keys}
    assert menu_roles == AUDIT_API_ROLES, f"audit 菜单角色漂移：{sorted(menu_roles)}"
    src = ADMIN_API_PY.read_text(encoding="utf-8")
    # 白名单实现为 list_audit_logs 函数体内的内联条件：非超管一律 1103
    fn_start = src.index("def list_audit_logs")
    fn_end = src.index("\n@router", fn_start)
    body = src[fn_start:fn_end]
    assert 'admin.role != "super_admin"' in body, "list_audit_logs 缺少仅超管白名单校验"


def test_admin_menus_helper_fails_closed_for_unknown_role():
    """_admin_menus 按角色分发；未知角色返回空列表（fail-closed）。"""
    for role, expected in EXPECTED_ROLE_MENUS.items():
        assert _admin_menus(SimpleNamespace(role=role)) == expected
    assert _admin_menus(SimpleNamespace(role="ghost")) == []

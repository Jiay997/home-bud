# -*- coding: utf-8 -*-
"""后台权限纯函数单元测试（不依赖数据库）。

用 SimpleNamespace 构造假 admin 对象，直接断言
require_admin_perm / check_domain_scope / require_confirm 三个纯函数的
放行与拦截行为（错误码 1103 / 1603 / 1602）。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 保证以 tests/ 目录单独运行时也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.deps import check_domain_scope, require_admin_perm, require_confirm
from app.core.errors import ApiError


def _admin(role: str, domain_scope: str = None) -> SimpleNamespace:
    """构造仅含权限判定所需字段的后台账号假对象。

    Args:
        role: 角色代码。
        domain_scope: 专家领域绑定（child/pet），非专家为 None。

    Returns:
        SimpleNamespace(role=..., domain_scope=...)。
    """
    return SimpleNamespace(role=role, domain_scope=domain_scope)


# ---------- require_admin_perm：角色 × 页面 × 动作 ----------


def test_super_admin_wildcard_allows_any_perm():
    """超管通配符 "*" 覆盖任意权限（含 cfg:write 这类独占动作）。"""
    require_admin_perm(_admin("super_admin"), "cfg:write")  # 不抛即通过


def test_operator_allowed_kb_publish():
    """operator 具备 kb:publish（矩阵显式授权）。"""
    require_admin_perm(_admin("operator"), "kb:publish")


def test_operator_denied_cfg_write():
    """operator 无 cfg:write（仅超管独占），错误码 1103。"""
    with pytest.raises(ApiError) as excinfo:
        require_admin_perm(_admin("operator"), "cfg:write")
    assert excinfo.value.code == 1103


def test_support_denied_kb_view():
    """support 无 kb:view，错误码 1103。"""
    with pytest.raises(ApiError) as excinfo:
        require_admin_perm(_admin("support"), "kb:view")
    assert excinfo.value.code == 1103


def test_expert_allowed_kb_review():
    """专家具备 kb:review（域外限制由 check_domain_scope 负责）。"""
    require_admin_perm(_admin("expert_child", "child"), "kb:review")


def test_expert_denied_rights_handle():
    """专家无 rights:handle，错误码 1103。"""
    with pytest.raises(ApiError) as excinfo:
        require_admin_perm(_admin("expert_pet", "pet"), "rights:handle")
    assert excinfo.value.code == 1103


def test_unknown_role_denied_everything():
    """未知角色一切动作均拒绝，错误码 1103。"""
    with pytest.raises(ApiError) as excinfo:
        require_admin_perm(_admin("intern"), "kb:view")
    assert excinfo.value.code == 1103


# ---------- check_domain_scope：专家领域绑定 ----------


def test_expert_in_scope_allowed():
    """expert_child 操作 child 领域放行。"""
    check_domain_scope(_admin("expert_child", "child"), "child")


def test_expert_cross_domain_denied():
    """expert_child 操作 pet 领域越权，错误码 1603。"""
    with pytest.raises(ApiError) as excinfo:
        check_domain_scope(_admin("expert_child", "child"), "pet")
    assert excinfo.value.code == 1603


def test_non_expert_cross_domain_allowed():
    """非专家角色（operator）不受域绑定限制。"""
    check_domain_scope(_admin("operator"), "pet")  # 不抛即通过


# ---------- require_confirm：二次确认凭证 ----------


def test_require_confirm_accepted():
    """凭证为约定值 CONFIRMED 时放行。"""
    require_confirm("CONFIRMED", "kb_unpublish")  # 不抛即通过


def test_require_confirm_missing_denied():
    """凭证缺失（None）拒绝，错误码 1602。"""
    with pytest.raises(ApiError) as excinfo:
        require_confirm(None, "kb_unpublish")
    assert excinfo.value.code == 1602


def test_require_confirm_wrong_value_denied():
    """凭证值错误（非 CONFIRMED）拒绝，错误码 1602。"""
    with pytest.raises(ApiError) as excinfo:
        require_confirm("yes", "kb_unpublish")
    assert excinfo.value.code == 1602

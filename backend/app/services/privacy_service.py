# -*- coding: utf-8 -*-
"""隐私承诺服务（RQ-11）：把合规动作做成可感知、可验证的产品资产。

红线（PRD §3.11.1）：**承诺只写已实现的**。写成营销话术即反噬（UV-7）。

因此本模块的每条承诺都携带：

- `implemented`: 是否确实已实现；
- `evidence`: 实现依据（代码 / 数据约束编号）；
- `action`: 可操作的跳转（撤回 / 删除 / 导出 / 查看记录）。

未实现的能力一律不写入承诺列表——由 `_catalog()` 的 `implemented` 字段过滤，
审计时可逐条对照。
"""
from typing import Any, Dict, List

# 承诺条目（每条附可操作跳转，AC-RQ11-1）
PLEDGE_VERSION = "V1"


def _catalog() -> List[Dict[str, Any]]:
    """返回隐私承诺条目目录（含实现状态与依据）。

    Returns:
        承诺条目列表。
    """
    return [
        {
            "id": "minimization",
            "title": "最小化收集",
            "promise": "我们只收集提供分龄养育参考所必需的信息，不要求填写与养育无关的个人资料。",
            "implemented": True,
            "evidence": "数据模型 §3.2 敏感字段加密 + 派生列；PRD §9.5 禁止采集清单",
            "action": {
                "label": "查看档案字段说明",
                "route": "/pages/profiles/index",
            },
        },
        {
            "id": "separate_consent",
            "title": "儿童信息单独同意",
            "promise": "建立孩子档案前需要单独同意儿童信息处理；你可以随时撤回，撤回后相关内容不再生成。",
            "implemented": True,
            "evidence": "F1 1301/1302 服务端门禁 + consent_record 留痕",
            "action": {
                "label": "查看同意记录",
                "route": "/pages/me/index?section=consents",
            },
        },
        {
            "id": "no_training",
            "title": "不用于训练",
            "promise": "本产品不使用你的问答与档案信息训练自有模型。",
            "implemented": True,
            "evidence": "NFR-C9 / DR-13；供应商零训练条款在合同中确认前，文案限定为「自有模型」口径",
            "action": {
                "label": "查看技术说明",
                "route": "/pages/privacy-pledge/index?section=training",
            },
        },
        {
            "id": "delete_export",
            "title": "可删除、可导出",
            "promise": "你可以在个人信息权利中心申请删除或导出你的数据，我们按法定时限处理。",
            "implemented": True,
            "evidence": "F1 权利中心六类请求（rights_request）+ SLA 处理",
            "action": {
                "label": "前往权利中心",
                "route": "/pages/me/index?section=rights",
            },
        },
        {
            "id": "photo_purge",
            "title": "图片用完即删",
            "promise": "图片提问上传的照片仅用于本次解析，服务端 24 小时内删除原图，且不进日志、不进埋点。",
            "implemented": True,
            "evidence": "RQ-05 / DR-27 / NFR-S7；photo_purge 定时任务出删除日志",
            "action": {
                "label": "查看图片处理说明",
                "route": "/pages/qa/index?section=photo",
            },
        },
    ]


def pledge() -> Dict[str, Any]:
    """返回隐私承诺页数据（仅包含已实现的承诺）。

    Returns:
        {version, items[], training_statement, updated_note} 字典。
    """
    items = [item for item in _catalog() if item["implemented"]]
    return {
        "version": PLEDGE_VERSION,
        "items": items,
        "training_statement": (
            "本产品不使用你的信息训练自有模型；第三方模型供应商的零训练数据条款"
            "以已签署合同为准，本次口径不超出合同范围对外承诺。"
        ),
        "honesty_note": "承诺页只列出已经实现的能力；未实现项不会写入承诺。",
        "first_boot_hint": "首启同意完成后可查看一屏式「我们如何保护孩子信息」说明页。",
    }


def audit() -> Dict[str, Any]:
    """返回承诺与实现对照表（法务签字前的自查清单）。

    Returns:
        {version, total, implemented, items[]} 字典。
    """
    catalog = _catalog()
    return {
        "version": PLEDGE_VERSION,
        "total": len(catalog),
        "implemented": sum(1 for item in catalog if item["implemented"]),
        "items": catalog,
    }

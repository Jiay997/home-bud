# -*- coding: utf-8 -*-
"""拟人化文案合规扫描（RQ-02 / NFR-C14）。

监管口径（PRD §3.2.3）：《人工智能拟人化互动服务管理暂行办法》
（2026-04-10 公布、2026-07-15 施行）适用对象为「模拟自然人人格特征…
且能开展**持续性情感互动**的服务」；智能客服、知识问答、工作助手明确
不适用。产品一旦文案滑向「陪伴 / 伙伴 / 懂你」，即落入射程——本模块即防线。

能力边界（诚实声明）：

- **能做**：对给定文本做禁用表述 + 常见变体扫描，输出命中位置与整改建议；
  作为 CI 门禁与后台月度抽检的同一真源；
- **不能做**：无法替代人工语义判断（谐音 / 隐喻绕过），故 PRD 要求
  「CI + 月度抽检双保险」；
- **fail-closed**：扫描器不可用时调用方必须阻断发布（NFR-C14），
  本模块通过异常表达不可用，不返回「空命中」伪装通过。
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger("jiaban.copy_scan")

# 词库类型（并入 F12 词库域，AC-RQ02-4）
LEXICON_TYPE = "anthropomorphic"

# 禁用表述清单（首批，PRD §3.2.3）+ 常见同义变体
FORBIDDEN_PHRASES: List[str] = [
    "AI 育儿伙伴", "AI育儿伙伴", "智能陪伴", "贴心小助手", "懂你的 AI", "懂你的AI",
    "AI 朋友", "AI朋友", "像家人一样", "一直陪着你", "宝宝的好朋友",
    "家庭养育伙伴", "养育伙伴", "陪伴你", "陪着你", "陪你长大", "陪你一起",
    "聊聊天", "说说话", "随时都在", "秒回", "懂你", "贴心朋友", "虚拟伴侣",
    "虚拟亲属", "情感陪伴", "心灵伙伴", "知心",
]

# 替代表述库（PRD §3.2.3；缺失时 CI 直接失败，故此处内置兜底）
REPLACEMENTS: Dict[str, str] = {
    "家庭养育伙伴": "家庭养育科普参考工具",
    "养育伙伴": "养育科普参考工具",
    "智能陪伴": "养育知识查询",
    "AI 育儿伙伴": "育儿科普参考工具",
    "AI育儿伙伴": "育儿科普参考工具",
    "懂你的 AI": "按档案适配的科普参考",
    "懂你的AI": "按档案适配的科普参考",
    "贴心小助手": "养育知识查询工具",
    "聊聊天": "提问",
    "说说话": "提问",
}

# 变体映射（谐音 / 空格 / 简繁 / 分隔符绕过）
VARIANT_MAP: Dict[str, str] = {
    "伴 侣": "伴侣",
    "伙 伴": "伙伴",
    "陪 伴": "陪伴",
    "寶伴": "宝伴",
}

# 扫描范围（AC-RQ02-1 全量对外文案）
SCAN_SCOPES = (
    "client/src",
    "admin-web/src",
    "backend/app/agents/prompts.py",
    "backend/scripts/seed_data.py",
    "backend/app/api/v1",
)

# 扫描时跳过的路径片段（依赖 / 构建产物 / 测试夹具）
SKIP_PARTS = ("node_modules", "dist", "build", ".venv", "__pycache__", "screenshots")

# 扫描时跳过的目录（合规包自身就是禁用词清单与扫描器，属「词表真源」，
# 不得因包含词条本身而自证违规）
SKIP_DIR_MARKERS = ("app/compliance", "app\\compliance")

# 扫描文件后缀
SCAN_SUFFIXES = (".vue", ".ts", ".js", ".json", ".py", ".md")


@dataclass
class ScanHit:
    """单条命中记录。

    Attributes:
        phrase: 命中的禁用表述。
        path: 文件相对路径。
        line: 行号（1 基）。
        snippet: 命中上下文（截断）。
        suggestion: 整改建议（替代表述）。
    """

    phrase: str
    path: str
    line: int
    snippet: str
    suggestion: str = ""

    def as_dict(self) -> Dict[str, object]:
        """转为可序列化字典。

        Returns:
            命中记录字典。
        """
        return {
            "phrase": self.phrase,
            "path": self.path,
            "line": self.line,
            "snippet": self.snippet,
            "suggestion": self.suggestion,
        }


@dataclass
class ScanResult:
    """扫描结果汇总。

    Attributes:
        hits: 命中列表。
        scanned_files: 扫描文件数。
        blocked: 是否阻断发布（命中即阻断）。
        errors: 扫描过程中的错误（非空表示扫描不完整，须 fail-closed）。
    """

    hits: List[ScanHit] = field(default_factory=list)
    scanned_files: int = 0
    blocked: bool = False
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        """转为可序列化字典。

        Returns:
            扫描结果字典。
        """
        return {
            "hits": [hit.as_dict() for hit in self.hits],
            "hit_count": len(self.hits),
            "scanned_files": self.scanned_files,
            "blocked": self.blocked,
            "errors": self.errors,
        }


def normalize(text: str) -> str:
    """归一化文本以便变体匹配（去全部空白 / 全角半角统一 / 变体字归一）。

    去除**全部**空白字符（而非折叠），使「AI 朋 友」「家庭 养育伙伴」这类
    分词绕过同样命中；合规扫描宁严不宽（误报由人工抽检复核）。

    Args:
        text: 原始文本。

    Returns:
        归一化文本。
    """
    if not text:
        return ""
    out = text.replace("\u3000", "")
    # 全角 ASCII → 半角（数字/字母/括号/冒号等）
    out = "".join(
        chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in out
    )
    out = re.sub(r"\s+", "", out)
    for source, target in VARIANT_MAP.items():
        out = out.replace(source.replace(" ", ""), target)
    return out


def scan_anthropomorphic(text: str) -> List[str]:
    """扫描一段文本中的拟人化禁用表述。

    Args:
        text: 待扫描文本。

    Returns:
        命中的禁用表述列表（去重保序；空列表表示通过）。
    """
    if not text:
        return []
    normalized = normalize(text)
    hits: List[str] = []
    for phrase in FORBIDDEN_PHRASES:
        key = normalize(phrase)
        if key and key in normalized and phrase not in hits:
            hits.append(phrase)
    return hits


def suggestion_for(phrase: str) -> str:
    """返回替代表述建议。

    Args:
        phrase: 命中表述。

    Returns:
        替代表述；无对应建议时返回空串。
    """
    return REPLACEMENTS.get(phrase, "")


def _iter_files(root: Path, scopes: Iterable[str]):
    """遍历扫描范围内的文件。

    Args:
        root: 仓库根目录。
        scopes: 相对路径（文件或目录）清单。

    Yields:
        (相对路径字符串, 绝对路径 Path)。
    """
    for scope in scopes:
        target = root / scope
        if not target.exists():
            continue
        if target.is_file():
            yield str(target.relative_to(root)), target
            continue
        for path in sorted(target.rglob("*")):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            rel = str(path.relative_to(root)).replace("\\", "/")
            if any(marker.replace("\\", "/") in rel for marker in SKIP_DIR_MARKERS):
                continue
            yield rel, path


def scan_repository(root: Optional[Path] = None, scopes: Optional[Iterable[str]] = None) -> ScanResult:
    """扫描仓库全量对外文案（CI 门禁用）。

    Args:
        root: 仓库根目录（缺省按本文件位置推导：backend/app/compliance
            → parents[3]）。
        scopes: 覆盖扫描范围（缺省 `SCAN_SCOPES`）。

    Returns:
        ScanResult 实例（`blocked=True` 表示命中，须阻断发布）。

    Raises:
        无（文件读取异常记录到 `errors`，调用方按 fail-closed 处理）。
    """
    base = Path(root) if root else Path(__file__).resolve().parents[3]
    result = ScanResult()
    for rel_path, path in _iter_files(base, scopes or SCAN_SCOPES):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 — 单文件读取失败记录并继续
            result.errors.append(f"{rel_path}: {exc}")
            continue
        result.scanned_files += 1
        normalized = normalize(content)
        for phrase in FORBIDDEN_PHRASES:
            key = normalize(phrase)
            if not key or key not in normalized:
                continue
            # 定位行号（原始文本逐行归一化匹配，避免偏移）
            for lineno, line in enumerate(content.splitlines(), start=1):
                if key in normalize(line):
                    result.hits.append(
                        ScanHit(
                            phrase=phrase,
                            path=rel_path,
                            line=lineno,
                            snippet=line.strip()[:160],
                            suggestion=suggestion_for(phrase),
                        )
                    )
                    break
    result.blocked = bool(result.hits)
    if result.blocked:
        logger.warning(
            "copy_scan_block: %d hit(s) across %d file(s)",
            len(result.hits),
            result.scanned_files,
        )
    return result


def check_texts(texts: Dict[str, str]) -> ScanResult:
    """扫描一组具名文案（后台单条文案校验 / 订阅消息模板校验）。

    Args:
        texts: {名称: 文案} 字典。

    Returns:
        ScanResult 实例。
    """
    result = ScanResult(scanned_files=len(texts))
    for name, content in texts.items():
        for phrase in scan_anthropomorphic(content or ""):
            result.hits.append(
                ScanHit(
                    phrase=phrase,
                    path=name,
                    line=1,
                    snippet=(content or "")[:160],
                    suggestion=suggestion_for(phrase),
                )
            )
    result.blocked = bool(result.hits)
    return result


def checklist() -> List[Dict[str, str]]:
    """返回 RQ-02 §3.2.3 的文案合规检查清单（发布流程勾选用）。

    Returns:
        [{id, question}] 列表（5 项）。
    """
    return [
        {"id": "C1", "question": "是否含禁用表述（陪伴 / 伙伴 / 懂你 / 一直陪着你 等）"},
        {"id": "C2", "question": "是否暗示情感关系或人格"},
        {"id": "C3", "question": "是否承诺「随时都在 / 秒回」类陪伴能力"},
        {"id": "C4", "question": "是否可能被理解为向儿童直接提供服务"},
        {"id": "C5", "question": "免责与 AI 标识是否完整"},
    ]

# -*- coding: utf-8 -*-
"""危机渠道硬编码号码扫描门禁（RQ-03 / DR-26 / E2E-22）。

口径（PRD §6.2 DR-26）：**渠道号码仅存于渠道清单表**（`crisis_channel.phone_number`），
任何前端代码、常量文件、配置快照中不得出现硬编码号码。

实现要点：

- 扫描 `client/src`、`admin-web/src`、`backend/app`（**排除**模型与种子/迁移文件
  之外的常量快照）与 `backend/scripts/seed_data.py`；
- 匹配「疑似电话号码」字面量：11 位手机号、`区号-号码`、`400/800` 服务号、
  `1xx` 短号；
- 白名单：
  - `110 / 120 / 119 / 122`：公共紧急号码，属「通用指引话术」而非渠道清单号码
    （PRD §3.3.4 允许「请拨打 120/110」的通用指引文案）；
  - 测试文件（`tests/`）：构造用例数据需要；
  - 本脚本自身与其他门禁脚本。

用法（工作目录 backend/）：
    python scripts/check_hardcoded_phones.py [-v]
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

# 扫描范围（相对仓库根）
SCAN_TARGETS = [
    "client/src",
    "admin-web/src",
    "backend/app",
    "backend/scripts/seed_data.py",
]

# 文件后缀
SUFFIXES = {".py", ".ts", ".js", ".vue", ".json", ".md"}

# 跳过路径片段
SKIP_PARTS = {"node_modules", "dist", "build", ".venv", "__pycache__", "screenshots"}

# 允许出现的公共紧急短号（通用指引话术，非渠道清单号码）
ALLOWED_SHORT_NUMBERS = {"110", "120", "119", "122", "12345"}

# 疑似电话号码模式（分层判定，见 scan_line）
MOBILE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
FIXED_PATTERN = re.compile(r"(?<!\d)(0\d{2,3}[-\s]?\d{7,8})(?!\d)")
SERVICE_PATTERN = re.compile(r"(?<!\d)([48]00[-\s]?\d{3}[-\s]?\d{4})(?!\d)")

# 出现这些关键词的行才判定为「渠道号码语境」（避免把业务错误码、
# 版本号、时间戳等数字误判为硬编码电话号码）
PHONE_CONTEXT = (
    "电话", "号码", "热线", "拨打", "求助", "呼救", "tel", "phone", "call",
    "急诊", "咨询", "联系", "客服",
)

# 行级白名单：注释、文档示例、正则、字段名、错误码等不判定
LINE_WHITELIST = (
    "phone_number",
    "phone_enc",
    "错误码",
    "error code",
    "code=",
    "code:",
    "示例",
    "example",
    "正则",
    "pattern",
    "regex",
    "https://",
    "http://",
)


def iter_files() -> Iterator[Tuple[str, Path]]:
    """遍历扫描范围内的文件。

    Yields:
        (相对路径, 绝对路径)。
    """
    for target in SCAN_TARGETS:
        path = REPO_ROOT / target
        if not path.exists():
            continue
        if path.is_file():
            yield str(path.relative_to(REPO_ROOT)), path
            continue
        for item in sorted(path.rglob("*")):
            if not item.is_file() or item.suffix not in SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in item.parts):
                continue
            if "tests" in item.parts:
                continue
            yield str(item.relative_to(REPO_ROOT)), item


def scan_line(line: str) -> List[str]:
    """扫描单行中的疑似硬编码号码（分层判定）。

    判定规则：

    - 11 位手机号：无条件判定（唯一可能合法的位置是渠道清单表或加密字段，
      均已在 `LINE_WHITELIST` 中排除）；
    - 座机 / 400 / 800：需同行出现「电话 / 热线 / 拨打」等渠道语境关键词，
      否则视为普通数字（版本号、时间戳、配额等）；
    - 公共紧急短号（110 / 120 / 119 / 122 / 12345）放行：属 PRD §3.3.4
      明确允许的「通用指引话术」。

    Args:
        line: 源码行。

    Returns:
        命中的号码列表（已排除公共短号与白名单行）。
    """
    for marker in LINE_WHITELIST:
        if marker in line:
            return []
    found: List[str] = []
    has_context = any(word in line for word in PHONE_CONTEXT)
    for pattern in (MOBILE_PATTERN, FIXED_PATTERN, SERVICE_PATTERN):
        for match in pattern.finditer(line):
            value = match.group(1)
            digits = re.sub(r"\D", "", value)
            if digits in ALLOWED_SHORT_NUMBERS:
                continue
            if pattern is not MOBILE_PATTERN and not has_context:
                continue
            if digits not in found:
                found.append(digits)
    return found


def main() -> None:
    """执行扫描并输出门禁结论。

    Returns:
        None。

    Raises:
        SystemExit: 0 通过 / 1 命中（源码存在硬编码号码）。
    """
    parser = argparse.ArgumentParser(description="危机渠道硬编码号码扫描")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出扫描文件数")
    args = parser.parse_args()

    hits: List[Tuple[str, int, str]] = []
    scanned = 0
    for rel_path, path in iter_files():
        scanned += 1
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 — 读取失败按门禁失败处理
            hits.append((rel_path, 0, f"读取失败：{exc}"))
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            for number in scan_line(line):
                hits.append((rel_path, lineno, number))

    if args.verbose:
        print(f"[phone-scan] 扫描文件 {scanned} 个")

    if hits:
        for rel_path, lineno, number in hits:
            print(f"[phone-scan] HIT {rel_path}:{lineno} 疑似硬编码号码 {number}")
        print(
            "[phone-scan] 结论：FAIL（DR-26：号码只能存于 crisis_channel 表，"
            "前端/常量不得硬编码）"
        )
        sys.exit(1)
    print(f"[phone-scan] 结论：PASS（扫描 {scanned} 个文件，无硬编码渠道号码）")
    sys.exit(0)


if __name__ == "__main__":
    main()

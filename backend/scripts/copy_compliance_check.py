# -*- coding: utf-8 -*-
"""拟人化文案合规扫描门禁脚本（RQ-02 / NFR-C14 / E2E-21）。

功能：

1. 对全量对外文案（前端源码、System Prompt、种子文案、API 文案）执行
   拟人化禁用表述扫描，**零命中**才放行；
2. 注入一条变体表述，验证扫描器能捕获（fail-closed 验证，E2E-21 口径）；
3. 扫描器自身不可用时**以非零退出码阻断**（不允许「空命中」伪装通过）。

用法（工作目录 backend/）：
    python scripts/copy_compliance_check.py [-v]
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.compliance import copy_scan  # noqa: E402

# 变体注入样本（谐音 / 空格 / 变体字绕过尝试）
INJECTION_SAMPLES = [
    "这是你的 AI 育儿伙伴",
    "家庭养育伙 伴已上线",
    "我们一直陪着你，随时都在",
    "AI 朋 友式问答",
]


def main() -> None:
    """执行扫描并输出门禁结论。

    Returns:
        None。

    Raises:
        SystemExit: 0 通过 / 1 命中或扫描器异常（阻断发布）。
    """
    parser = argparse.ArgumentParser(description="拟人化文案合规扫描门禁")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出命中明细")
    args = parser.parse_args()

    try:
        result = copy_scan.scan_repository()
    except Exception as exc:  # noqa: BLE001 — 扫描器不可用必须 fail-closed
        print(f"[copy-scan] ERROR: 扫描器不可用，阻断发布：{exc}")
        sys.exit(1)

    print(
        f"[copy-scan] 扫描文件 {result.scanned_files} 个，命中 {len(result.hits)} 条，"
        f"读取错误 {len(result.errors)} 个"
    )
    if result.errors:
        for err in result.errors[:10]:
            print(f"[copy-scan] READ-ERROR {err}")

    # 变体注入自检：扫描器必须能捕获变体，否则视为「扫描能力缺失」
    missed = []
    for sample in INJECTION_SAMPLES:
        hits = copy_scan.scan_anthropomorphic(sample)
        if not hits:
            missed.append(sample)
        elif args.verbose:
            print(f"[copy-scan] 注入样本已捕获：{sample!r} -> {hits}")

    failed = False
    if result.hits:
        failed = True
        for hit in result.hits:
            print(
                f"[copy-scan] HIT {hit.path}:{hit.line} 命中「{hit.phrase}」"
                + (f" → 建议改为「{hit.suggestion}」" if hit.suggestion else "")
            )
    if missed:
        failed = True
        for sample in missed:
            print(f"[copy-scan] FAIL: 变体未被捕获，扫描能力不足：{sample!r}")
    if result.errors:
        failed = True

    if failed:
        print("[copy-scan] 结论：FAIL（命中即整改 + 复盘；NFR-Q6 零容忍）")
        sys.exit(1)
    print("[copy-scan] 结论：PASS（合法文案零命中，变体注入全部捕获）")
    sys.exit(0)


if __name__ == "__main__":
    main()

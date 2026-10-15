# -*- coding: utf-8 -*-
"""docs/API.md 与 OpenAPI 规范一致性校验脚本（Task 4.1）。

功能：
- 解析 docs/API.md 中的端点清单行（`## GET /api/v1/...` 格式）；
- 读取 OpenAPI 规范（复用 export_api_doc.load_openapi：优先运行中服务，
  失败则本地导入 app 生成）并提取 paths×methods 端点集合；
- 比对两侧集合差异：文档缺失端点 / 文档多列端点；
- 完全一致时退出码 0，存在差异时退出码 1 并打印明细。

使用方式（在 backend 目录下）：
    python scripts/check_api_doc.py
"""
import os
import re
import sys
from typing import List, Set, Tuple

# 保证可从脚本目录导入同目录的 export_api_doc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_api_doc import DOC_PATH, HTTP_METHODS, load_openapi  # noqa: E402

# API.md 端点标题行正例：## GET /api/v1/health
ENDPOINT_LINE = re.compile(r"^## (GET|POST|PUT|DELETE|PATCH) (\S+)$")


def parse_doc_endpoints(doc_path: str) -> Set[Tuple[str, str]]:
    """解析 API.md 中的端点集合。

    Args:
        doc_path: API.md 文件路径。

    Returns:
        (METHOD, path) 集合。

    Raises:
        FileNotFoundError: 文档不存在时抛出。
    """
    endpoints: Set[Tuple[str, str]] = set()
    with open(doc_path, "r", encoding="utf-8") as fh:
        for line in fh:
            match = ENDPOINT_LINE.match(line.rstrip("\n"))
            if match:
                endpoints.add((match.group(1), match.group(2)))
    return endpoints


def collect_openapi_endpoints(spec: dict) -> Set[Tuple[str, str]]:
    """从 OpenAPI 规范提取端点集合。

    Args:
        spec: OpenAPI 全量字典。

    Returns:
        (METHOD, path) 集合。
    """
    endpoints: Set[Tuple[str, str]] = set()
    for path, methods in (spec.get("paths") or {}).items():
        for method in methods:
            if method in HTTP_METHODS:
                endpoints.add((method.upper(), path))
    return endpoints


def main() -> None:
    """校验入口：比对文档端点集合与 OpenAPI 端点集合。

    一致时打印 OK 并以退出码 0 结束；否则列出差异并以退出码 1 结束。

    Returns:
        None。

    Raises:
        SystemExit: 退出码 0（一致）/ 1（不一致或文档缺失）。
    """
    if not os.path.isfile(DOC_PATH):
        print(f"[check] ERROR: {DOC_PATH} not found（先运行 export_api_doc.py 生成）")
        sys.exit(1)
    doc_set = parse_doc_endpoints(DOC_PATH)
    spec = load_openapi()
    api_set = collect_openapi_endpoints(spec)

    missing_in_doc = sorted(api_set - doc_set)   # OpenAPI 有而文档缺失
    extra_in_doc = sorted(doc_set - api_set)     # 文档有而 OpenAPI 无

    print(f"[check] doc endpoints: {len(doc_set)} | openapi endpoints: {len(api_set)}")
    if not missing_in_doc and not extra_in_doc:
        print("[check] OK: API.md 与 openapi.json 零偏差")
        sys.exit(0)
    for method, path in missing_in_doc:
        print(f"[check] MISSING in doc : {method} {path}")
    for method, path in extra_in_doc:
        print(f"[check] EXTRA in doc   : {method} {path}")
    print(f"[check] FAIL: {len(missing_in_doc)} missing / {len(extra_in_doc)} extra")
    sys.exit(1)


if __name__ == "__main__":
    main()

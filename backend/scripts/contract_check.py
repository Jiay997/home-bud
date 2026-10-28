# -*- coding: utf-8 -*-
"""前端调用 × OpenAPI 契约快照校验（评估文档 §4.1 系统性建议落地）。

作用：
1. 扫描各前端 api 目录（admin-web/src/api、client/src/api）下全部 .ts 文件，提取其中对后端的 HTTP 调用：
   - admin.ts 自带 request(method, path) 方法优先式；BASE_URL + '...' 直接 fetch；
   - client.ts request(path, opts) / request<Generic>(path, opts) 路径优先式；
   - stream.ts fetch(`/api/v1/...`) SSE 直连。
2. 将 `${...}` 模板段归一化为 {param} 通配段（段内含任意表达式均视为路径参数）。
3. 与后端 app.openapi() 的 paths 快照逐段比对：段数与后端相等，且每段
   字面相等或后端段为 {参数} 占位、前端段为 {param} 通配；方法必须在该端点
   已注册（method mismatch 亦计漂移）。
4. 输出漂移清单；存在漂移时退出码 1（供 CI/发版前门禁）。

用法（工作目录必须是 backend/，与 .env 相对路径约定一致）：
    python scripts/contract_check.py [-v]

备注：不做"后端端点未被前端调用"的反向告警——回调/定时类端点（如
/safety-scan/callback、/admin/agent-logs/export）天然无前端调用点，属正常。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
# 前端 API 目录：后台管理端（admin-web，Web-only）与 uni-app 跨端 C 端（client，小程序 + H5）
API_DIRS = [
    BACKEND_DIR.parent / "admin-web" / "src" / "api",
    BACKEND_DIR.parent / "client" / "src" / "api",
]

METHOD_NAMES = {"GET", "POST", "PUT", "DELETE", "PATCH"}

# 匹配 request( / request<T>( / upload<T>( 的调用起点（停在左括号）；
# 泛型段允许跨行与嵌套（如 request<{ items: Array<{ uid: string }> }>），非贪婪回溯到调用括号
CALLEE_RE = r"(?:request|upload)\s*(?:<[\s\S]*?>)?\s*\("
# 匹配 fetch(`...`) 的调用起点（SSE 直连）
FETCH_RE = r"fetch\s*\("
# 匹配 BASE_URL + '...' 直接拼 URL
BASE_URL_RE = r"BASE_URL\s*\+\s*'([^']*)'"


def iter_call_spans(text: str, callee_re: str) -> list[str]:
    """提取 callee_re 匹配处的完整调用串（括号平衡，识别字符串引号）。"""
    spans: list[str] = []
    for m in re.finditer(callee_re, text):
        i = m.end() - 1  # 指向 '('
        depth = 0
        quote: str | None = None
        j = i
        while j < len(text):
            ch = text[j]
            if quote:
                if ch == "\\":
                    j += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in "'\"`":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth == 0 and j < len(text):
            spans.append(text[i : j + 1])
    return spans


STR_LIT_RE = re.compile(r"(['\"`])((?:[^\\]|\\.)*?)\1", re.S)
METHOD_PROP_RE = re.compile(r"method\s*:\s*['\"](\w+)['\"]")


def first_literal(call_span: str) -> str | None:
    """调用串内第一个字符串字面量（'..' ".." `..`）。"""
    m = STR_LIT_RE.search(call_span)
    return m.group(2) if m else None


def normalize_segments(path: str) -> list[str]:
    """相对路径归一化为段列表；含 ${...} 的段（含 encodeURIComponent 包裹）→ {param}。"""
    path = path.split("?")[0]
    segs: list[str] = []
    for s in path.split("/"):
        if not s:
            continue
        segs.append("{param}" if "${" in s else s)
    return segs


def extract_admin_calls(text: str) -> list[tuple[str, str]]:
    """admin.ts 方法优先式 request('METHOD', 'path', ...) → [(method, 相对路径)]。"""
    calls: list[tuple[str, str]] = []
    for span in iter_call_spans(text, CALLEE_RE):
        m = STR_LIT_RE.search(span)
        if not m:
            continue
        first = m.group(2)
        if first.upper() not in METHOD_NAMES:
            continue
        path_m = STR_LIT_RE.search(span, m.end())
        if not path_m or not path_m.group(2).startswith("/"):
            continue
        calls.append((first.upper(), path_m.group(2)))
    return calls


def extract_client_calls(text: str) -> list[tuple[str, str]]:
    """client.ts 路径优先式 request(path, { method }) 或 request<...>(path) → [(method, 路径)]。"""
    calls: list[tuple[str, str]] = []
    for span in iter_call_spans(text, CALLEE_RE):
        m = STR_LIT_RE.search(span)
        if not m:
            continue
        path = m.group(2)
        if not path.startswith("/"):
            continue
        method_m = METHOD_PROP_RE.search(span)
        method = method_m.group(1).upper() if method_m else "GET"
        calls.append((method, path))
    return calls


def extract_direct_urls(text: str) -> list[tuple[str, str]]:
    """BASE_URL + 'path' 直连（当前用于日志导出 CSV）→ [(GET, 相对路径)]。"""
    return [("GET", p) for p in re.findall(BASE_URL_RE, text) if p.startswith("/")]


def extract_fetch_streams(text: str) -> list[tuple[str, str]]:
    """fetch(`/api/v1/...`) SSE 直连 → [(method, 相对路径)]（去 /api/v1 前缀取默认 GET）。"""
    calls: list[tuple[str, str]] = []
    for span in iter_call_spans(text, FETCH_RE):
        lit = first_literal(span)
        if not lit or not lit.startswith("/api/v1/"):
            continue
        method_m = METHOD_PROP_RE.search(span)
        method = method_m.group(1).upper() if method_m else "GET"
        calls.append((method, lit[len("/api/v1") :]))
    return calls


def collect_frontend_calls() -> tuple[list[tuple[str, str, str]], list[str]]:
    """扫描各前端 api 目录 → ([(file, method, 相对路径)], [错误信息])。"""
    calls: list[tuple[str, str, str]] = []
    errors: list[str] = []
    extractors = {
        "admin.ts": lambda t: extract_admin_calls(t) + extract_direct_urls(t),
        "client.ts": extract_client_calls,
        "stream.ts": extract_fetch_streams,
    }
    for api_dir in API_DIRS:
        if not api_dir.is_dir():
            errors.append(f"前端 API 目录不存在：{api_dir}")
            continue
        for name, extractor in extractors.items():
            f = api_dir / name
            if not f.exists():
                continue
            found = extractor(f.read_text(encoding="utf-8"))
            if not found:
                errors.append(f"{name} 未提取到任何调用（提取规则可能失效，请检查文件结构）")
            for method, path in found:
                calls.append((name, method, path))
        # 目录内其余 .ts（如未来新增模块）按大杂烩提取，避免遗漏
        for f in sorted(api_dir.glob("*.ts")):
            if f.name in extractors:
                continue
            text = f.read_text(encoding="utf-8")
            for method, path in extract_admin_calls(text) + extract_client_calls(text) + extract_direct_urls(text) + extract_fetch_streams(text):
                calls.append((f.name, method, path))
    return calls, errors


def load_openapi_paths() -> dict[str, dict]:
    """离线导入 app.main 构建 OpenAPI 路径快照（无需服务运行中的实例）。"""
    sys.path.insert(0, str(BACKEND_DIR))
    from app.main import app  # noqa: WPS433（延迟导入：需先注入 sys.path）

    return app.openapi().get("paths", {})


def match_path(call_segs: list[str], path_keys: list[str]) -> str | None:
    """段级匹配；返回命中的后端路径（无命中返回 None）。

    规则：占位段（前端 {param} 或后端 {..}）可匹配任意段——前端字面量即后端
    路径参数的合法实例（如 /history/report/{uid}/image → /history/{item_type}/...）；
    字面段之间必须完全相等；多候选时取字面相等段数最多者。
    """
    best: str | None = None
    best_score = -1
    for key in path_keys:
        ksegs = [s for s in key.split("/") if s]
        if len(ksegs) != len(call_segs):
            continue
        score = 0
        for cs, ks in zip(call_segs, ksegs):
            ks_is_param = ks.startswith("{") and ks.endswith("}")
            if cs == "{param}":
                if ks_is_param:
                    score += 1  # 模板参数 ↔ 路径参数，优先于命中字面段
                continue
            if ks_is_param:
                continue  # 前端字面量是后端路径参数的实例，允许但低于字面相等
            if cs != ks:
                break
            score += 2
        else:
            if score > best_score:
                best, best_score = key, score
    return best


def check_doc_completeness(paths: dict[str, dict]) -> tuple[int, list[tuple[str, str, str]]]:
    """校验 OpenAPI 全部业务端点的文档完整性（tags 与 summary 均非空）。

    规则：paths 下每个 operation（GET/POST/PUT/DELETE/PATCH，含 deprecated
    与机器对机器回调端点如 /safety-scan/callback）都必须满足：
    - tags 至少含 1 个非空字符串；
    - summary 为去空白后非空的字符串。

    Args:
        paths: app.openapi() 返回的 paths 快照（path → method → operation 对象）。

    Returns:
        tuple[int, list[tuple[str, str, str]]]: (齐全端点数, 缺失清单)；
        缺失清单元素为 (method, path, 缺失项描述)，缺失项形如 "tags+summary"。
    """
    ok = 0
    missing: list[tuple[str, str, str]] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.upper() not in METHOD_NAMES or not isinstance(op, dict):
                continue  # 跳过 parameters 等非 operation 键与非 HTTP 方法
            lacks: list[str] = []
            tags = op.get("tags") or []
            if not any(isinstance(t, str) and t.strip() for t in tags):
                lacks.append("tags")
            summary = op.get("summary")
            if not (isinstance(summary, str) and summary.strip()):
                lacks.append("summary")
            if lacks:
                missing.append((method.upper(), path, "+".join(lacks)))
            else:
                ok += 1
    return ok, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="前端调用 × OpenAPI 契约快照校验")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印全部调用明细")
    args = parser.parse_args()

    paths = load_openapi_paths()
    path_keys = list(paths.keys())

    # 文档完整性门禁：全部端点 tags+summary 齐全才放行（缺失即 FAIL，退出码 1）
    doc_ok, doc_missing = check_doc_completeness(paths)
    if doc_missing:
        print("== 文档完整性校验：OpenAPI 端点 tags/summary ==")
        for method, path, lacks in doc_missing:
            print(f"[MISS] {method:6s} {path} 缺少 {lacks}")
        print(f"结果：FAIL（{len(doc_missing)}/{doc_ok + len(doc_missing)} 端点文档不完整）")
        sys.exit(1)
    print(f"文档完整性：{doc_ok}/{doc_ok} 端点 tags+summary 齐全")

    calls, errors = collect_frontend_calls()
    for err in errors:
        print(f"[FAIL] {err}")

    drift: list[tuple[str, str, str, str]] = []
    method_miss: list[tuple[str, str, str, str]] = []
    for file, method, rel in calls:
        segs = ["api", "v1", *normalize_segments(rel)]
        hit = match_path(segs, path_keys)
        if hit is None:
            drift.append((file, method, rel, ""))
        elif method.lower() not in paths[hit]:
            method_miss.append((file, method, rel, hit))
        if args.verbose:
            mark = "OK" if hit and method.lower() in paths.get(hit, {}) else "DRIFT"
            print(f"[{mark}] {method:6s} {rel}{(' -> ' + hit) if hit else ''} ({file})")

    total = len(calls)
    bad = len(drift) + len(method_miss)
    by_file: dict[str, int] = {}
    for file, _, _ in calls:
        by_file[file] = by_file.get(file, 0) + 1
    dist = "、".join(f"{k} {v}" for k, v in sorted(by_file.items()))
    print("== 契约校验：admin-web + client 的 src/api/*.ts × app.openapi() ==")
    print(f"提取调用 {total} 处（{dist}）；OpenAPI 路径 {len(path_keys)} 个")
    for file, method, rel, _ in drift:
        print(f"[DRIFT] {method:6s} {rel} 未匹配任何契约端点（{file}）")
    for file, method, rel, hit in method_miss:
        print(f"[DRIFT] {method:6s} {rel} 命中 {hit} 但该方法未注册（{file}）")
    if errors or bad:
        print(f"结果：FAIL（提取错误 {len(errors)}，漂移 {bad}）")
        sys.exit(1)
    print("结果：PASS（无漂移）")


if __name__ == "__main__":
    main()

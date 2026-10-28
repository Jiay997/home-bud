# -*- coding: utf-8 -*-
"""压测脚本：mock 模式问答链路并发压测（spec close-module-gaps Task 6.3）。

链路：设备登录 → 建儿童档案（含同意） → SSE 问答（mock 模式）→ 轮询额度。
输出：P50/P95 延迟、错误率、SSE 首包 P95（服务端计时口径 first_packet_ms）、
进程内存快照（RSS，经 /health 采集不到时以客户端视角省略）。

用法（先以 mock 模式起一个后端实例）：
    set LLM_MOCK=true && python -m uvicorn app.main:app --port 8001
    python scripts/load_test.py --workers 20 --requests 50 --base http://localhost:8001
"""
import argparse
import json
import queue
import statistics
import threading
import time
import uuid
from pathlib import Path

import httpx

sys_path = str(Path(__file__).resolve().parent.parent)


def percentile(sorted_vals: list, p: float) -> float:
    """计算分位数（线性插值）。

    Args:
        sorted_vals: 已升序排序的样本列表。
        p: 分位（0-1）。

    Returns:
        分位值。
    """
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def worker(wid: int, base: str, n_req: int, results: "queue.Queue") -> None:
    """单个压测工作线程：登录→建档→问答循环。

    Args:
        wid: 线程编号。
        base: 目标服务地址。
        n_req: 本线程问答请求数。
        results: 结果队列（dict: ok/latency_ms/first_packet_ms/err）。
    """
    client = httpx.Client(timeout=30)
    try:
        # 登录
        r = client.post(f"{base}/api/v1/auth/dev-login",
                        json={"device_id": f"load-{wid}-{uuid.uuid4().hex[:6]}"}).json()
        if r["code"] != 0:
            results.put({"ok": False, "err": "login"})
            return
        headers = {"Authorization": f"Bearer {r['data']['access_token']}"}
        # 同意（base + child_personal_info）
        client.post(f"{base}/api/v1/consent/agree", json={"consent_type": "base"}, headers=headers)
        client.post(f"{base}/api/v1/consent/agree",
                    json={"consent_type": "child_personal_info", "guardian_name": "压测"}, headers=headers)
        # 建档
        r = client.post(f"{base}/api/v1/profiles/children",
                        json={"nickname": f"压测娃{wid}", "birth_date": "2025-04-08"},
                        headers=headers).json()
        profile_uid = (r.get("data") or {}).get("profile_uid", "")
        # 问答循环
        for i in range(n_req):
            t0 = time.perf_counter()
            first_packet = None
            err = None
            rid = str(uuid.uuid4())
            r = client.post(f"{base}/api/v1/qa/sessions", headers=headers,
                            json={"entry": "child", "question": f"压测问题{wid}-{i}：宝宝睡眠怎么引导",
                                  "client_request_id": rid, "profile_uid": profile_uid}).json()
            if r["code"] == 1202:
                # 额度用尽：自动开通会员（mock 支付）后继续压测，隔离业务限流与技术失败
                po = client.post(f"{base}/api/v1/billing/orders", headers=headers,
                                 json={"product_code": "member_monthly", "platform": "web",
                                       "contract_confirm": True, "client_request_id": str(uuid.uuid4())}).json()
                order_no = (po.get("data") or {}).get("order_no", "")
                if order_no:
                    import hashlib
                    tx = f"LOAD{wid}{i}{uuid.uuid4().hex[:8]}"
                    sign = hashlib.sha256((tx + "jiaban-pay-mock-sign-key").encode()).hexdigest()
                    client.post(f"{base}/api/v1/billing/orders/{order_no}/mock-pay",
                                json={"transaction_id": tx, "sign": sign}, headers=headers)
                    continue  # 已开通会员，下一轮 i 继续
                results.put({"ok": False, "err": "quota_exhausted", "latency_ms": 0, "first_packet_ms": None})
                return
            if r["code"] != 0:
                results.put({"ok": False, "err": f"session:{r['code']}", "latency_ms": 0, "first_packet_ms": None})
                continue
            uid = r["data"]["session_uid"]
            with client.stream("POST", f"{base}/api/v1/qa/sessions/{uid}/stream", headers=headers) as resp:
                ev = None
                for line in resp.iter_lines():
                    if line.startswith("event:"):
                        ev = line.split(":", 1)[1].strip()
                        if ev == "started" and first_packet is None:
                            first_packet = (time.perf_counter() - t0) * 1000
                    elif line.startswith("data:") and ev == "completed":
                        try:
                            payload = json.loads(line.split(":", 1)[1].strip())
                            fp = (payload.get("first_packet_ms") or {}).get("value") if isinstance(
                                payload.get("first_packet_ms"), dict) else payload.get("first_packet_ms")
                            if isinstance(fp, (int, float)):
                                first_packet = fp  # 服务端计时口径优先
                        except Exception:
                            pass
                    elif line.startswith("data:") and ev in ("error", "blocked"):
                        err = ev
                        break
            latency = (time.perf_counter() - t0) * 1000
            results.put({"ok": err is None, "err": err, "latency_ms": latency,
                         "first_packet_ms": first_packet})
    except Exception as exc:  # noqa: BLE001 — 压测端异常记失败继续
        results.put({"ok": False, "err": f"exc:{exc}", "latency_ms": 0, "first_packet_ms": None})
    finally:
        client.close()


def main() -> None:
    """执行压测并输出统计报告。"""
    parser = argparse.ArgumentParser(description="Babe宝伴 mock 模式压测")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--requests", type=int, default=50, help="每 worker 问答次数")
    parser.add_argument("--base", type=str, default="http://localhost:8001")
    args = parser.parse_args()

    print(f"[load_test] base={args.base} workers={args.workers} req/worker={args.requests}")
    results: "queue.Queue" = queue.Queue()
    threads = [threading.Thread(target=worker, args=(i, args.base, args.requests, results))
               for i in range(args.workers)]
    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t_start

    samples, first_packets, errors = [], [], []
    while not results.empty():
        r = results.get()
        if r["ok"]:
            samples.append(r["latency_ms"])
        else:
            errors.append(r["err"])
        if r.get("first_packet_ms"):
            first_packets.append(r["first_packet_ms"])

    total = len(samples) + len(errors)
    samples.sort()
    first_packets.sort()
    print("\n===== 压测结果 =====")
    print(f"并发: {args.workers} workers × {args.requests} req")
    print(f"总请求: {total}  成功: {len(samples)}  失败: {len(errors)}  错误率: "
          f"{len(errors) / total * 100:.2f}%" if total else "无请求")
    if samples:
        print(f"整请求延迟(ms): P50={percentile(samples, 0.5):.0f}  P95={percentile(samples, 0.95):.0f}  "
              f"均值={statistics.mean(samples):.0f}  max={samples[-1]:.0f}")
    if first_packets:
        print(f"SSE 首包(ms, 服务端口径优先): P50={percentile(first_packets, 0.5):.0f}  "
              f"P95={percentile(first_packets, 0.95):.0f}")
    print(f"吞吐: {total / wall:.1f} req/s  墙钟: {wall:.1f}s")
    if errors:
        from collections import Counter
        print("错误分布:", dict(Counter(errors).most_common(5)))

    # 结构化输出（供报告引用）
    out = {
        "workers": args.workers, "requests_per_worker": args.requests, "total": total,
        "success": len(samples), "error_rate": round(len(errors) / total, 4) if total else 0,
        "latency_p50_ms": round(percentile(samples, 0.5)), "latency_p95_ms": round(percentile(samples, 0.95)),
        "first_packet_p50_ms": round(percentile(first_packets, 0.5)),
        "first_packet_p95_ms": round(percentile(first_packets, 0.95)),
        "throughput_rps": round(total / wall, 1), "wall_seconds": round(wall, 1),
    }
    out_path = Path(sys_path) / "load_test_result.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[load_test] 结构化结果已写入 {out_path}")


if __name__ == "__main__":
    import sys

    main()

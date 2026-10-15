# -*- coding: utf-8 -*-
"""并发行为测试（spec Task 6.2）。

验证多线程并发下的关键不变量：
- 并发第二条流：qa:active:{user_id} 活跃键占用时再开会话 → 409/1203；
- 并发乐观锁：同 profile 两线程同时 PUT 同 version → 恰一个成功、
  一个 1003（数据不被双写覆盖）；
- 并发支付回调：同订单两线程同时 mock-pay → 两次 HTTP 均成功（幂等
  语义），但 Subscription 仅创建一条、额度用量不变。

实现口径：每线程独立 TestClient(app) 实例 + threading.Barrier 对齐
起跑，结果经队列收集后统一断言。
"""
import json
import queue
import sys
import threading
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import mock_pay_sign  # noqa: E402

import app.main as app_main  # noqa: E402
from app.core.cache import cache  # noqa: E402

API = "/api/v1"
SAFE_QUESTION = "一岁宝宝辅食可以加蛋黄吗"


# ---------------------------------------------------------------------------
# 线程工具
# ---------------------------------------------------------------------------
def _run_in_threads(worker_count, target):
    """并行执行目标函数并收集结果。

    Args:
        worker_count: 线程数。
        target: 回调 (thread_index, barrier, out_queue)；在子线程执行。

    Returns:
        按线程序号排列的结果列表（队列取出顺序整理为 index→result）。

    Raises:
        无（线程内异常经队列回传由断言暴露）。
    """
    barrier = threading.Barrier(worker_count)
    out_queue = queue.Queue()
    threads = [
        threading.Thread(target=target, args=(i, barrier, out_queue))
        for i in range(worker_count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    results = [None] * worker_count
    while not out_queue.empty():
        idx, result = out_queue.get()
        results[idx] = result
    assert all(r is not None for r in results), "some worker crashed before reporting"
    return results


# ---------------------------------------------------------------------------
# 并发第二条流：活跃键占用 → 409/1203
# ---------------------------------------------------------------------------
class TestConcurrentActiveStream:
    """活跃会话并发限制。"""

    def test_second_session_rejected_while_active(self, client, user_token):
        """cache 中存在活跃键时再开会话 → 409/1203。

        Args:
            client: TestClient 夹具。
            user_token: 登录夹具。

        Raises:
            AssertionError: 响应非 409/1203 或 cache 语义不成立。
        """
        headers, user_uid = user_token()
        # 查库拿主键 id，直接操纵进程内 cache 模拟未结束的活跃流
        user_id = sys.modules["conftest"].db_query_user_id(user_uid)
        active_key = f"qa:active:{user_id}"
        cache.set(
            active_key,
            json.dumps({"session_uid": "ghost-session", "cancel_token": "tok"}),
            ttl_seconds=60,
        )
        try:
            assert cache.get(active_key) is not None
            resp = client.post(
                f"{API}/qa/sessions",
                json={
                    "entry": "child",
                    "question": SAFE_QUESTION,
                    "client_request_id": "conc-active-1",
                },
                headers=headers,
            )
            assert resp.status_code == 409, resp.text
            body = resp.json()
            assert body["code"] == 1203
            # retryable 语义：附带建议重试秒数
            assert body.get("error", {}).get("retryable") is True
        finally:
            cache.delete(active_key)


# ---------------------------------------------------------------------------
# 并发乐观锁：同 version 双写 → 恰一个成功
# ---------------------------------------------------------------------------
class TestConcurrentOptimisticLock:
    """档案乐观锁并发一致性。"""

    def test_concurrent_same_version_put_exact_one_success(
        self, client, user_token
    ):
        """两线程同 version 并发 PUT → 恰一个 200、一个 1003，version 最终为 2。

        Args:
            client: TestClient 夹具。
            user_token: 登录夹具。

        Raises:
            AssertionError: 双写成功（丢失更新）或结果组合不符。
        """
        headers, _ = user_token()
        for ctype in ("base", "child_personal_info"):
            client.post(
                f"{API}/consent/agree", json={"consent_type": ctype}, headers=headers
            )
        resp = client.post(
            f"{API}/profiles/children",
            json={"nickname": "并发宝宝", "birth_date": "2025-04-08"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        profile_uid = resp.json()["data"]["profile_uid"]

        results = _run_in_threads(
            2,
            lambda i, barrier, q: self._worker(
                i, barrier, q, profile_uid, headers["Authorization"]
            ),
        )

        codes = [r["code"] for r in results]
        http_codes = [r["http"] for r in results]
        # 恰一个成功一个乐观锁冲突（数据模型口径：1003/http 409）
        assert sorted(codes) == [0, 1003], results
        assert sorted(http_codes) == [200, 409], results

        # 服务端最终状态：version 仅前进一格，昵称为成功方所写
        final = client.get(
            f"{API}/profiles/children",
            headers={"Authorization": results[codes.index(0)]["auth"]},
        )
        assert final.status_code == 200
        children = final.json()["data"]["children"]
        target = [c for c in children if c["profile_uid"] == profile_uid][0]
        assert target["version"] == 2, target
        assert target["nickname"] in ("并发名A", "并发名B")

    @staticmethod
    def _worker(index, barrier, out_queue, profile_uid, bearer):
        """单线程执行并发 PUT。

        Args:
            index: 线程序号。
            barrier: 起跑对齐栅栏。
            out_queue: 结果队列 (index, dict)。
            profile_uid: 档案 UID。
            bearer: Bearer 凭据原文（每个线程独立 TestClient）。

        Returns:
            无（结果经队列回传：{code, http, auth}）。

        Raises:
            Exception: 写入队列前异常时线程终止（由主线程断言暴露）。
        """
        thread_client = TestClient(app_main.app)
        barrier.wait()
        try:
            resp = thread_client.put(
                f"{API}/profiles/children/{profile_uid}",
                json={"version": 1, "nickname": f"并发名{'AB'[index]}"},
                headers={"Authorization": bearer},
            )
            body = resp.json()
            out_queue.put(
                (index, {"code": body.get("code"), "http": resp.status_code,
                         "auth": bearer})
            )
        finally:
            thread_client.close()


# ---------------------------------------------------------------------------
# 并发支付回调：幂等发放恰好一次
# ---------------------------------------------------------------------------
class TestConcurrentMockPay:
    """并发重复回调下的发放幂等性。"""

    def test_concurrent_mock_pay_single_subscription(self, client, user_token):
        """两线程并发 mock-pay 同订单 → 双双 code=0，Subscription 恰一条、额度不变。

        Args:
            client: TestClient 夹具。
            user_token: 登录夹具。

        Raises:
            AssertionError: 重复发放（订阅多于一条）或任一回调失败。
        """
        headers, user_uid = user_token()
        order_no = client.post(
            f"{API}/billing/orders",
            json={
                "product_code": "member_monthly",
                "platform": "web",
                "contract_confirm": True,
                "client_request_id": "conc-pay-1",
            },
            headers=headers,
        ).json()["data"]["order_no"]

        tx = "conc-txn-001"
        sign = mock_pay_sign(tx)
        bearer = headers["Authorization"]
        results = _run_in_threads(
            2, lambda i, barrier, q: self._pay_worker(i, barrier, q, order_no, tx, sign, bearer)
        )

        # 两次回调均为业务成功（幂等：首次发放，重复回调 already_processed）
        assert [r["http"] for r in results] == [200, 200], results
        assert [r["code"] for r in results] == [0, 0], results
        processed = sorted(r["already"] for r in results)
        assert processed == [False, True], results

        # 查库断言：Subscription 恰一条；额度行 used 不变（支付不扣问答额度）
        from sqlalchemy import func, select

        from app.db import get_session_factory
        from app.models import AppUser, QuotaUsage, Subscription

        db = get_session_factory()()
        try:
            sub_count = (
                db.query(func.count(Subscription.id))
                .filter(Subscription.status == "active")
                .scalar()
            )
            assert sub_count == 1, f"expected 1 subscription, got {sub_count}"

            user = db.query(AppUser).filter(AppUser.user_uid == user_uid).first()
            assert user.member_status == "member"
            quota_used = (
                db.execute(
                    select(QuotaUsage.used_count).where(
                        QuotaUsage.user_id == user.id
                    )
                )
                .scalars()
                .all()
            )
            assert all(v == 0 for v in quota_used), quota_used
        finally:
            db.close()

    @staticmethod
    def _pay_worker(index, barrier, out_queue, order_no, tx, sign, bearer):
        """单线程执行并发 mock-pay。

        Args:
            index: 线程序号。
            barrier: 起跑对齐栅栏。
            out_queue: 结果队列 (index, dict)。
            order_no: 订单号。
            tx: 渠道交易号。
            sign: 验签摘要。
            bearer: Bearer 凭据原文。

        Returns:
            无（结果经队列回传：{code, http, already}）。

        Raises:
            Exception: 写入队列前异常时线程终止（由主线程断言暴露）。
        """
        thread_client = TestClient(app_main.app)
        barrier.wait()
        try:
            resp = thread_client.post(
                f"{API}/billing/orders/{order_no}/mock-pay",
                json={"transaction_id": tx, "sign": sign},
                headers={"Authorization": bearer},
            )
            body = resp.json()
            out_queue.put(
                (
                    index,
                    {
                        "code": body.get("code"),
                        "http": resp.status_code,
                        "already": body.get("data", {}).get("already_processed"),
                    },
                )
            )
        finally:
            thread_client.close()

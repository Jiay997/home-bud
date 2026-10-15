# -*- coding: utf-8 -*-
"""可观测性模块：进程内轻量指标聚合（无 Prometheus 依赖）。

职责：
- 聚合 HTTP 请求计数 / 错误计数 / 延迟采样（环形保留最近 1000 条）；
- 聚合 Agent 调用成功/失败、降级、风险拦截、额度用尽等业务计数；
- snapshot() 输出计数器、P50/P95 延迟、关键比率与告警触发项。

告警规则（阈值可通过环境变量配置，缺省按架构告警口径）：
- METRIC_ALERT_AGENT_FAIL_RATE（默认 0.03）：Agent 失败率；
- METRIC_ALERT_TIMEOUT_RATE（默认 0.05）：请求错误率（5xx 视为超时/故障代理指标）；
- METRIC_ALERT_DEGRADED_RATE（默认 0.03）：降级率。

多实例部署时各进程独立聚合，跨实例汇聚留待接入 Prometheus/OTLP 时扩展。
"""
import math
import os
import threading
from collections import deque
from typing import Deque, Dict, List

# 延迟采样环形缓冲上限（只保留最近 1000 条，防内存无界增长）
_LATENCY_SAMPLE_LIMIT = 1000

# 告警规则定义：(告警名, 环境变量名, 缺省阈值)
_ALERT_RULES = (
    ("agent_fail_rate", "METRIC_ALERT_AGENT_FAIL_RATE", 0.03),
    ("timeout_rate", "METRIC_ALERT_TIMEOUT_RATE", 0.05),
    ("degraded_rate", "METRIC_ALERT_DEGRADED_RATE", 0.03),
)


def _percentile(sorted_values: List[float], pct: float) -> float:
    """线性插值法计算分位数。

    Args:
        sorted_values: 已升序排序的样本列表。
        pct: 百分位（50 表示 P50，95 表示 P95）。

    Returns:
        分位数值；空样本返回 0.0。
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    # 线性插值：k 为分位在样本序列中的浮点下标
    k = (len(sorted_values) - 1) * (pct / 100.0)
    floor_idx = math.floor(k)
    ceil_idx = math.ceil(k)
    if floor_idx == ceil_idx:
        return sorted_values[int(k)]
    lower = sorted_values[floor_idx]
    upper = sorted_values[ceil_idx]
    return lower * (ceil_idx - k) + upper * (k - floor_idx)


def _threshold_of(env_name: str, default: float) -> float:
    """读取告警阈值环境变量（非法值回退缺省）。

    Args:
        env_name: 环境变量名。
        default: 缺省阈值。

    Returns:
        阈值浮点数。
    """
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        # 配置非法时不让告警链路失效，回退缺省
        return default


class MetricsRegistry:
    """进程内指标聚合器（线程安全，轻量实现）。

    记录维度：
    - 请求层：request_count / error_count（status>=500 视为错误）/
      latency_samples（最近 1000 条，毫秒）；
    - 业务层：agent_total_count / agent_fail_count / degraded_count /
      blocked_count / quota_exhausted_count。

    多实例部署下为进程内视角；跨实例聚合留待外部监控系统接入（spec D6 降级口径）。
    """

    def __init__(self) -> None:
        """初始化空计数器与延迟采样缓冲。

        Args:
            无。

        Returns:
            None。
        """
        self._lock = threading.Lock()
        # 请求层计数
        self._request_count = 0
        self._error_count = 0
        # 业务层计数
        self._agent_total_count = 0
        self._agent_fail_count = 0
        self._degraded_count = 0
        self._blocked_count = 0
        self._quota_exhausted_count = 0
        # 延迟样本（毫秒），环形截断保留最近 N 条
        self._latency_samples: Deque[float] = deque(maxlen=_LATENCY_SAMPLE_LIMIT)

    # ------------------------------------------------------------------
    # 观测入口
    # ------------------------------------------------------------------
    def observe_request(self, status_code: int, duration_ms: float) -> None:
        """记录一次 HTTP 请求的计数与延迟。

        Args:
            status_code: HTTP 响应状态码（>=500 计入 error_count）。
            duration_ms: 请求耗时（毫秒）。

        Returns:
            None。
        """
        with self._lock:
            self._request_count += 1
            if status_code >= 500:
                self._error_count += 1
            self._latency_samples.append(float(duration_ms))

    def observe_agent(self, ok: bool) -> None:
        """记录一次 Agent（含路由/检索节点）调用结果。

        Args:
            ok: 是否成功（True=ok，False=fail）。

        Returns:
            None。
        """
        with self._lock:
            self._agent_total_count += 1
            if not ok:
                self._agent_fail_count += 1

    def observe_degraded(self) -> None:
        """记录一次降级交付（存在失败分节但整体可用的会话）。

        Args:
            无。

        Returns:
            None。
        """
        with self._lock:
            self._degraded_count += 1

    def observe_blocked(self) -> None:
        """记录一次风险拦截（blocked 帧下发）。

        Args:
            无。

        Returns:
            None。
        """
        with self._lock:
            self._blocked_count += 1

    def observe_quota_exhausted(self) -> None:
        """记录一次免费额度用尽拒绝（1202）。

        Args:
            无。

        Returns:
            None。
        """
        with self._lock:
            self._quota_exhausted_count += 1

    # ------------------------------------------------------------------
    # 快照与告警
    # ------------------------------------------------------------------
    def snapshot(self) -> Dict:
        """输出当前指标快照（含分位延迟、比率与告警触发项）。

        告警规则：agent_fail_rate / timeout_rate / degraded_rate 超过
        环境变量配置阈值（缺省 0.03 / 0.05 / 0.03）时列入 alerts；
        分母为 0（无样本）时不触发，避免冷启动误报。

        Args:
            无。

        Returns:
            {counters, latency:{p50,p95,samples}, rates, alerts} 字典。
        """
        with self._lock:
            counters = {
                "request_count": self._request_count,
                "error_count": self._error_count,
                "agent_total_count": self._agent_total_count,
                "agent_fail_count": self._agent_fail_count,
                "degraded_count": self._degraded_count,
                "blocked_count": self._blocked_count,
                "quota_exhausted_count": self._quota_exhausted_count,
            }
            sorted_latency = sorted(self._latency_samples)
        # 分位数在锁外计算（样本已复制，避免长持锁）
        latency = {
            "p50": round(_percentile(sorted_latency, 50), 2),
            "p95": round(_percentile(sorted_latency, 95), 2),
            "samples": len(sorted_latency),
        }
        # 比率：分母为 0 时置 0（无样本不算异常）
        rates = {
            "agent_fail_rate": (
                counters["agent_fail_count"] / counters["agent_total_count"]
                if counters["agent_total_count"] > 0
                else 0.0
            ),
            "timeout_rate": (
                counters["error_count"] / counters["request_count"]
                if counters["request_count"] > 0
                else 0.0
            ),
            "degraded_rate": (
                counters["degraded_count"] / counters["request_count"]
                if counters["request_count"] > 0
                else 0.0
            ),
        }
        alerts = self._evaluate_alerts(rates)
        return {
            "counters": counters,
            "latency": latency,
            "rates": rates,
            "alerts": alerts,
        }

    def _evaluate_alerts(self, rates: Dict[str, float]) -> List[Dict]:
        """按环境变量阈值评估告警规则。

        Args:
            rates: 当前比率字典（agent_fail_rate/timeout_rate/degraded_rate）。

        Returns:
            触发的告警列表，每项含 metric/value/threshold/message。
        """
        alerts: List[Dict] = []
        for metric, env_name, default_threshold in _ALERT_RULES:
            threshold = _threshold_of(env_name, default_threshold)
            value = rates.get(metric, 0.0)
            # 严格大于阈值才告警（等于阈值视为正常水位）
            if value > threshold:
                alerts.append(
                    {
                        "metric": metric,
                        "value": round(value, 4),
                        "threshold": threshold,
                        "message": f"{metric}={value:.4f} 超过阈值 {threshold}",
                    }
                )
        return alerts


# 进程级单例：中间件与业务埋点共用
metrics = MetricsRegistry()
# -*- coding: utf-8 -*-
"""DeepSeek 模型网关模块。

架构 §2.2：全部模型调用经由本网关单点出口，便于审计、限流与白名单校验。
- 同步 httpx POST OpenAI 兼容 `/chat/completions`；
- purpose 区分用途（intent/semantic/child_agent/pet_agent/safety_agent），
  各用途使用独立 temperature 与超时；
- llm_mock=True 时按 purpose 返回确定性 mock（供开发/联调/测试）；
- 异常/超时统一抛 LlmGatewayError，由调用方决定降级策略
  （语义风险模型异常按命中保守处理；Agent 异常按该域失败降级）。
"""
import json
import time
import zlib
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import get_settings
from .mock_semantic_corpus import match_mock_semantic

# mock 确定性耗时的取值区间（毫秒）：按种子伪随机落在 [MOCK_LATENCY_MIN, MOCK_LATENCY_MAX]
MOCK_LATENCY_MIN = 800
MOCK_LATENCY_MAX = 2000


def mock_latency_ms(seed: str) -> int:
    """生成确定性伪随机耗时（mock 口径填充用）。

    按种子字符串 CRC32 映射到固定区间，同一种子恒得同一值——
    「按节点伪随机但可复现」，供 mock 链路填充 AgentCallLog.latency_ms。

    Args:
        seed: 确定性种子（如节点名/purpose）。

    Returns:
        800-2000ms 区间内的整数耗时。
    """
    span = MOCK_LATENCY_MAX - MOCK_LATENCY_MIN + 1
    return MOCK_LATENCY_MIN + zlib.crc32(seed.encode("utf-8")) % span


def estimate_mock_tokens(text_len: int) -> int:
    """按文本字符长度估算 token 数（mock 口径填充用）。

    确定性估算：中文语料按约 2/3 字符每 token 折算，长度为 0 返回 0，
    非零至少为 1，保证 mock 下 token 字段非空可展示。

    Args:
        text_len: 文本字符长度。

    Returns:
        估算的 token 数（非负整数）。
    """
    if text_len <= 0:
        return 0
    return max(1, (text_len * 2) // 3)

# 各用途的采样温度（意图/风险分类要求稳定，Agent 生成允许少量发散）
PURPOSE_TEMPERATURE: Dict[str, float] = {
    "intent": 0.0,
    "semantic": 0.0,
    "child_agent": 0.5,
    "pet_agent": 0.5,
    "safety_agent": 0.5,
}


class LlmGatewayError(Exception):
    """LLM 网关调用异常。

    网络失败、非 2xx 响应、响应结构缺失、超时均包装为本异常。
    """

    pass


def extract_json(text: str) -> Optional[dict]:
    """从模型输出文本中提取 JSON 对象。

    兼容模型常见的 ```json ... ``` 代码块包裹与前后噪声文字；
    解析失败返回 None（调用方据此走降级路径）。

    Args:
        text: 模型原始输出文本。

    Returns:
        解析成功的 dict；解析失败返回 None。

    Raises:
        无（任何解析异常均吞掉并返回 None）。
    """
    if not text:
        return None
    raw = text.strip()
    # 剥离 ```json ... ``` / ``` ... ``` 包裹
    if raw.startswith("```"):
        # 去掉首行 ```json 与尾部 ```
        lines = raw.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
    # 直接尝试解析
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        pass
    # 容错：截取首个 { 到最后一个 } 之间的片段再试
    start, end = raw.find("{"), raw.rfind("}")
    if 0 <= start < end:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            return None
    return None


class LlmGateway:
    """DeepSeek 模型网关。

    线程安全（httpx 同步客户端按调用创建），可被 LangGraph 并行节点
    与风险引擎共用；mock 开关关闭后所有请求走真实上游。
    """

    def chat(self, messages: List[dict], purpose: str, timeout: float = 12.0) -> dict:
        """调用 chat/completions 并返回归一化结果。

        Args:
            messages: OpenAI 兼容消息列表 [{"role": ..., "content": ...}]。
            purpose: 调用用途（intent/semantic/child_agent/pet_agent/safety_agent），
                决定采样温度与 mock 分支。
            timeout: 上游超时秒数（语义风险用 3s，意图用 1s，Agent 用 12s）。

        Returns:
            归一化结果 {"content": str, "prompt_tokens": int,
            "completion_tokens": int, "latency_ms": int}。

        Raises:
            LlmGatewayError: mock 关闭时网络失败/超时/非 2xx/响应结构缺失。
        """
        settings = get_settings()
        start = time.monotonic()
        # mock 分支：按 purpose 返回确定性内容，保证开发/联调链路可通；
        # 同时按 mock 口径填充确定性耗时与 token 估算（供 AgentCallLog 展示，
        # 真实模式走上游 usage/实测耗时，路径不变）
        if settings.llm_mock:
            content = self._mock_content(messages, purpose)
            joined_len = sum(len(str(m.get("content", ""))) for m in messages)
            return {
                "content": content,
                "prompt_tokens": estimate_mock_tokens(joined_len),
                "completion_tokens": estimate_mock_tokens(len(content)),
                "latency_ms": mock_latency_ms(f"gateway:{purpose}"),
            }
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": PURPOSE_TEMPERATURE.get(purpose, 0.3),
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except Exception as exc:  # 网络异常/超时统一包装
            raise LlmGatewayError(f"llm request failed: {exc}") from exc
        if resp.status_code // 100 != 2:
            raise LlmGatewayError(f"llm upstream status={resp.status_code}")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
        except Exception as exc:  # 响应结构不符合 OpenAI 兼容约定
            raise LlmGatewayError(f"llm response malformed: {exc}") from exc
        return {
            "content": content or "",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": int((time.monotonic() - start) * 1000),
        }

    # ------------------------------------------------------------------
    # mock 分支
    # ------------------------------------------------------------------
    def _mock_content(self, messages: List[dict], purpose: str) -> str:
        """按用途生成确定性 mock 输出。

        Args:
            messages: 消息列表（用于从用户输入中嗅探测试触发词）。
            purpose: 调用用途。

        Returns:
            字符串形式的 mock 内容（intent/semantic 为 JSON 串；
            agent 为 JSON 串，其中 blocks.content 为 Markdown 建议文本）。
        """
        # 拼接全部消息文本用于触发词嗅探
        joined = "\n".join(str(m.get("content", "")) for m in messages)
        if purpose == "intent":
            return json.dumps(
                {"intent": "sleep", "has_child_entity": True, "has_pet_entity": False},
                ensure_ascii=False,
            )
        if purpose == "semantic":
            # mock 回归口径（SIM-25）：预置语义类高风险语句表命中时，
            # 按对应类别与档位分值返回（表内语句为词库外的语义类表述，
            # 仅供 mock 模式回归「一级词库 → 二级语义」完整拦截链路）；
            # 表外输入维持原放行/灰区口径，真实 LLM 模式不读取该表
            corpus_hit = match_mock_semantic(joined)
            if corpus_hit is not None:
                return json.dumps(corpus_hit, ensure_ascii=False)
            # 验收约定：输入含「灰区测试」返回 0.65（拦截+引导区间），否则 0.1（放行）
            score = 0.65 if "灰区测试" in joined else 0.1
            return json.dumps({"score": score, "category": None}, ensure_ascii=False)
        # Agent 类用途：返回结构化 JSON，content 字段为 Markdown 建议文本
        return json.dumps(
            {
                "title": "通用建议",
                "topic_key": "general_care",
                "professional_referral": False,
                "evidence_ref": [],
                "stance": "support",
                "blocks": [
                    {
                        "block_key": "advice",
                        "title": "建议要点",
                        "access_tier": "free",
                        "content": (
                            "## 建议要点\n"
                            "- 这是网关 mock 生成的 Markdown 建议文本；\n"
                            "- 生产环境将由 DeepSeek 按领域提示词生成。"
                        ),
                    },
                    {
                        "block_key": "member_extra",
                        "title": "会员进阶方案",
                        "access_tier": "block",
                        "content": "会员专属：个性化执行方案（mock 内容）。",
                    },
                ],
            },
            ensure_ascii=False,
        )


# 模块级单例（进程内复用，无状态可安全共享）
_gateway: Optional[LlmGateway] = None


def get_gateway() -> LlmGateway:
    """获取全局网关单例。

    Returns:
        LlmGateway 实例（进程内唯一）。
    """
    global _gateway
    if _gateway is None:
        _gateway = LlmGateway()
    return _gateway

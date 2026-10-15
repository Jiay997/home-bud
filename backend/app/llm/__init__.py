# -*- coding: utf-8 -*-
"""LLM 网关包。

提供统一的 DeepSeek（OpenAI 兼容）调用入口与 JSON 提取工具，
全部模型访问必须经由本网关（架构 §2.2 模型网关单点）。
"""
from .gateway import LlmGateway, LlmGatewayError, extract_json, get_gateway

__all__ = ["LlmGateway", "LlmGatewayError", "extract_json", "get_gateway"]

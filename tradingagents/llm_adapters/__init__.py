"""
TradingAgents LLM 适配器模块

提供多种大模型服务的统一适配接口
"""

from .embeddings import (
    OpenAIEmbeddings,
    create_dashscope_embeddings,
    embedding_text,
)

__all__ = [
    "OpenAIEmbeddings",
    "create_dashscope_embeddings",
    "embedding_text",
]

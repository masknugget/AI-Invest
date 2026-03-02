"""
TradingAgents LLM 适配器模块

提供多种大模型服务的统一适配接口
"""

from .embeddings import (
    OpenAIEmbeddings,
    HSBCEmbeddings,
    create_dashscope_embeddings,
    create_hsbc_embeddings,
    embedding_text,
)

__all__ = [
    "OpenAIEmbeddings",
    "HSBCEmbeddings",
    "create_dashscope_embeddings",
    "create_hsbc_embeddings",
    "embedding_text",
]

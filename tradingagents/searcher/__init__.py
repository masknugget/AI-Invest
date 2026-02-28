"""
TradingAgents Searcher 模块
提供基于向量相似性的文档检索功能
"""

from .vector_store import (
    VectorStore,
    SearchResult,
    create_vector_store,
)
from tradingagents.agents.utils.chromadb_config import DEFAULT_CHROMA_PERSIST_DIR

__all__ = [
    "VectorStore",
    "SearchResult", 
    "create_vector_store",
    "DEFAULT_CHROMA_PERSIST_DIR",
]

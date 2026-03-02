"""
TradingAgents Searcher 模块
提供基于向量相似性和 BM25 关键词的文档检索功能
"""

from .vector_store import (
    VectorStore,
    SearchResult,
    create_vector_store,
)
from .bm25_store import (
    BM25Store,
    BM25SearchResult,
    HybridSearcher,
    create_bm25_store,
)
from tradingagents.agents.utils.chromadb_config import DEFAULT_CHROMA_PERSIST_DIR

__all__ = [
    # 向量搜索
    "VectorStore",
    "SearchResult", 
    "create_vector_store",
    # BM25 搜索
    "BM25Store",
    "BM25SearchResult",
    "HybridSearcher",
    "create_bm25_store",
    # 配置
    "DEFAULT_CHROMA_PERSIST_DIR",
]

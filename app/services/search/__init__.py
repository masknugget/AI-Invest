"""
搜索服务模块
提供向量语义搜索和 BM25 关键词搜索功能
"""

# 向量搜索服务
from .search_service import (
    SearchService,
    get_search_service,
    SearchRequest,
    SearchResult,
    DocumentInsert,
    DocumentInsertResponse,
    SearchStats,
)

# BM25 关键词搜索服务
from .bm25_service import (
    BM25SearchService,
    get_bm25_search_service,
    reset_bm25_search_service,
    BM25SearchRequest,
    BM25SearchResultItem,
    BM25DocumentInsert,
    BM25DocumentInsertResponse,
    BM25SearchStats,
)

__all__ = [
    # 向量搜索
    "SearchService",
    "get_search_service",
    "SearchRequest",
    "SearchResult",
    "DocumentInsert",
    "DocumentInsertResponse",
    "SearchStats",
    # BM25 关键词搜索
    "BM25SearchService",
    "get_bm25_search_service",
    "reset_bm25_search_service",
    "BM25SearchRequest",
    "BM25SearchResultItem",
    "BM25DocumentInsert",
    "BM25DocumentInsertResponse",
    "BM25SearchStats",
]

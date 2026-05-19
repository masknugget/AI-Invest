"""
召回层 - 向量检索模块

提供基于 LanceDB 的向量召回能力，支持函数式编程风格。
"""

from recommender.retrieval.vector_retrieval import (
    # 数据模型
    RetrievalResult,
    RetrievalContext,
    
    # 核心函数
    retrieve,
    retrieve_with_filters,
    batch_retrieve,
    
    # 结果处理
    extract_contents,
    extract_metadata,
    merge_contexts,
    
    # 股票/行业召回
    retrieve_for_stock,
    retrieve_for_industry,
    
    # 函数式工具
    create_retrieval_pipeline,
    compose,
    pipe,
    
    # 纯函数工具
    filter_by_score,
    filter_by_metadata,
    sort_by_score,
    limit_results,
    map_results,
)

__all__ = [
    "RetrievalResult",
    "RetrievalContext",
    "retrieve",
    "retrieve_with_filters",
    "batch_retrieve",
    "extract_contents",
    "extract_metadata",
    "merge_contexts",
    "retrieve_for_stock",
    "retrieve_for_industry",
    "create_retrieval_pipeline",
    "compose",
    "pipe",
    "filter_by_score",
    "filter_by_metadata",
    "sort_by_score",
    "limit_results",
    "map_results",
]

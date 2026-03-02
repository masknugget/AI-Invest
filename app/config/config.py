"""
应用配置类
用于集中管理应用配置项
"""

import os


class Config:
    """应用配置类"""
    
    # ==================== BM25 搜索配置 ====================
    
    # BM25 索引持久化目录
    bm25_persist_directory = os.getenv("BM25_PERSIST_DIRECTORY", r"G:\projects\gitdata\AI-Invest\data\bm25")
    
    # BM25 默认集合名称
    bm25_default_collection = os.getenv("BM25_DEFAULT_COLLECTION", "stock_basic")
    
    # BM25 算法参数
    bm25_k1 = float(os.getenv("BM25_K1", "1.5"))  # 词频饱和度参数
    bm25_b = float(os.getenv("BM25_B", "0.75"))   # 文档长度归一化参数
    bm25_delta = float(os.getenv("BM25_DELTA", "0.5"))  # BM25+ delta 参数
    
    # BM25 计算方法: robertson, lucene, atire, bm25l, bm25+
    bm25_method = os.getenv("BM25_METHOD", "lucene")

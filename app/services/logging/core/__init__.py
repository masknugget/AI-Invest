"""
日志核心模块
"""

from .log_storage import (
    LogStorage,
    MongoLogStorage,
    FileLogStorage,
    MemoryLogStorage,
    get_storage_instance
)
from .log_rotator import LogRotationPolicy, LogRotator
from .log_indexer import LogIndexer, IndexManager

__all__ = [
    # 存储
    "LogStorage",
    "MongoLogStorage",
    "FileLogStorage",
    "MemoryLogStorage",
    "get_storage_instance",
    # 轮转
    "LogRotationPolicy",
    "LogRotator",
    # 索引
    "LogIndexer",
    "IndexManager",
]

"""
LanceDB 统一配置模块
提供 LanceDB 数据库连接和客户端配置
"""
import os
import tempfile

import lancedb

# -------------------- 默认配置 --------------------
# LanceDB 默认持久化路径（相对于项目根目录）
DEFAULT_LANCE_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "lancedb"
)


def get_default_lancedb_db():
    """
    获取默认 LanceDB 数据库连接（使用默认持久化路径）
    数据会自动保存到 ./data/lancedb/

    Returns:
        lancedb.DBConnection: LanceDB 数据库连接实例
    """
    os.makedirs(DEFAULT_LANCE_PERSIST_DIR, exist_ok=True)
    return lancedb.connect(DEFAULT_LANCE_PERSIST_DIR)


def get_persistent_lancedb_db(persist_directory: str):
    """
    获取持久化 LanceDB 数据库连接

    Args:
        persist_directory: 数据持久化目录路径

    Returns:
        lancedb.DBConnection: LanceDB 数据库连接实例
    """
    os.makedirs(persist_directory, exist_ok=True)
    return lancedb.connect(persist_directory)


def get_memory_lancedb_db():
    """
    获取内存模式 LanceDB 数据库连接
    LanceDB 没有纯内存模式，使用临时目录模拟

    Returns:
        Tuple[lancedb.DBConnection, str]: (数据库连接实例, 临时目录路径)
    """
    tmp_dir = tempfile.mkdtemp(prefix="lancedb_")
    return lancedb.connect(tmp_dir), tmp_dir


# 导出配置
__all__ = [
    'get_default_lancedb_db',
    'get_persistent_lancedb_db',
    'get_memory_lancedb_db',
    'DEFAULT_LANCE_PERSIST_DIR',
]

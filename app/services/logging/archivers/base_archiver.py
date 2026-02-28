"""
日志归档抽象基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class LogArchiver(ABC):
    """日志归档抽象基类"""
    
    @abstractmethod
    async def archive_batch(self, logs: List[Dict[str, Any]]) -> int:
        """
        归档一批日志
        
        Args:
            logs: 日志列表
            
        Returns:
            成功归档的日志数量
        """
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        log_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        从归档中检索日志
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            log_type: 日志类型
            limit: 限制数量
            
        Returns:
            日志列表
        """
        pass
    
    @abstractmethod
    async def delete_archive(
        self,
        before: Optional[Any] = None,
        log_type: Optional[str] = None
    ) -> int:
        """
        删除归档日志
        
        Args:
            before: 删除此时间之前的日志
            log_type: 日志类型
            
        Returns:
            删除的日志数量
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取归档统计信息"""
        pass

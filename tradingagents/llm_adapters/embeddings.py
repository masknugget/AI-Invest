"""
OpenAI Embeddings 适配器
为 TradingAgents 提供 OpenAI Embeddings 接口支持
"""

import os
import logging
from typing import List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIEmbeddings:
    """
    OpenAI Embeddings 适配器
    支持 OpenAI 官方 API 及兼容 OpenAI 格式的第三方服务（如阿里百炼）
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-v3",
        **kwargs
    ):
        """
        初始化 OpenAI Embeddings 客户端
        
        Args:
            api_key: OpenAI API Key，默认从环境变量读取
            base_url: API 基础 URL
            model: Embedding 模型名称
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        # 初始化 OpenAI 客户端
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        client_kwargs.update(kwargs)
        
        self.client = OpenAI(**client_kwargs)
        logger.info(f"✅ OpenAI Embeddings 初始化: model={model}")
    
    def embed_query(self, text: str) -> List[float]:
        """
        单个文本向量化
        
        Args:
            text: 输入文本
            
        Returns:
            List[float]: 向量
        """
        if not text:
            return []
        
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        
        return response.data[0].embedding
    
    def embed_documents(
        self, 
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        批量文本向量化
        
        注意: DashScope 限制每批最多 10 条，会自动分批处理
        
        Args:
            texts: 文本列表
            batch_size: 每批处理的文本数量，默认 10（DashScope 限制）
            
        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []
        
        # DashScope 限制每批最多 10 条
        if batch_size > 10:
            batch_size = 10
        
        all_embeddings = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # 显示进度
                if total > batch_size:
                    logger.debug(f"向量化进度: {min(i + batch_size, total)}/{total}")
                    
            except Exception as e:
                logger.error(f"批量向量化失败 (batch {i//batch_size + 1}): {e}")
                # 失败时逐个处理
                logger.warning(f"尝试逐条处理本批次 {len(batch)} 条数据...")
                for text in batch:
                    try:
                        embedding = self.embed_query(text)
                        all_embeddings.append(embedding)
                    except Exception as e2:
                        logger.error(f"单条向量化失败: {e2}")
                        # 添加空向量作为占位
                        all_embeddings.append([])
        
        return all_embeddings


def create_dashscope_embeddings(
    api_key: Optional[str] = None,
    model: str = "text-embedding-v3"
) -> OpenAIEmbeddings:
    """
    创建阿里百炼 DashScope Embeddings 实例
    
    Args:
        api_key: DashScope API Key，默认从环境变量 DASHSCOPE_API_KEY 读取
        model: 模型名称
        
    Returns:
        OpenAIEmbeddings: Embeddings 实例
    """
    api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    return OpenAIEmbeddings(
        api_key=api_key,
        base_url=base_url,
        model=model
    )


def embedding_text(input_text: str) -> List[float]:
    """
    简单的文本向量化函数（兼容旧接口）
    
    Args:
        input_text: 输入文本
        
    Returns:
        List[float]: 向量
    """
    embeddings = create_dashscope_embeddings()
    return embeddings.embed_query(input_text)

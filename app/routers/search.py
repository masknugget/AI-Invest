"""
向量搜索 API 路由
提供语义搜索、文档管理等功能
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth_db import get_current_user
from app.services.search import (
    SearchService,
    get_search_service,
    SearchRequest,
    SearchResult,
    DocumentInsert,
    DocumentInsertResponse,
    SearchStats,
)

router = APIRouter(prefix="/search", tags=["向量搜索"])
logger = logging.getLogger("webapi")


# ==================== 搜索接口 ====================

@router.post("/query", response_model=List[SearchResult], summary="语义搜索")
async def search_documents(
    request: SearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    语义搜索
    
    根据文本查询语义相似的文档/股票
    
    Example:
        ```json
        {
            "query": "银行股",
            "top_k": 5,
            "filter_metadata": {"type": "stock"}
        }
        ```
    """
    try:
        service = get_search_service()
        results = service.search(
            query=request.query,
            top_k=request.top_k,
            filter_metadata=request.filter_metadata
        )
        return results
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/query", response_model=List[SearchResult], summary="语义搜索(GET)")
async def search_documents_get(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50, description="返回数量"),
    user: dict = Depends(get_current_user)
):
    """
    语义搜索 (GET 方式)
    
    方便浏览器直接测试
    
    Example:
        GET /api/v1/search/query?q=平安银行&top_k=5
    """
    try:
        service = get_search_service()
        results = service.search(query=q, top_k=top_k)
        return results
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ==================== 文档管理接口 ====================

@router.post("/documents", response_model=DocumentInsertResponse, summary="添加文档")
async def add_document(
    doc: DocumentInsert,
    user: dict = Depends(get_current_user)
):
    """
    添加单条文档到向量库
    
    Example:
        ```json
        {
            "content": "平安银行今日大涨5%",
            "metadata": {"type": "news", "stock": "000001"},
            "doc_id": "news_001"
        }
        ```
    """
    try:
        service = get_search_service()
        
        # 添加用户信息到 metadata
        meta = doc.metadata or {}
        meta["created_by"] = user.get("username", "unknown")
        
        doc_id = service.add_document(
            content=doc.content,
            metadata=meta,
            doc_id=doc.doc_id
        )
        
        return DocumentInsertResponse(
            doc_id=doc_id,
            content_preview=doc.content[:50] + "..." if len(doc.content) > 50 else doc.content,
            status="success"
        )
    except Exception as e:
        logger.error(f"添加文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加文档失败: {str(e)}")


@router.post("/documents/batch", response_model=List[str], summary="批量添加文档")
async def add_documents_batch(
    documents: List[DocumentInsert],
    user: dict = Depends(get_current_user)
):
    """
    批量添加文档到向量库
    
    Example:
        ```json
        [
            {"content": "文档1", "metadata": {"type": "news"}},
            {"content": "文档2", "metadata": {"type": "report"}}
        ]
        ```
    """
    try:
        service = get_search_service()
        
        # 添加用户信息到 metadata
        for doc in documents:
            if doc.metadata is None:
                doc.metadata = {}
            doc.metadata["created_by"] = user.get("username", "unknown")
        
        doc_ids = service.add_documents(documents)
        return doc_ids
    except Exception as e:
        logger.error(f"批量添加文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量添加失败: {str(e)}")


@router.delete("/documents/{doc_id}", summary="删除文档")
async def delete_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    删除指定文档
    
    Args:
        doc_id: 文档ID
    """
    try:
        service = get_search_service()
        result = service.delete_document(doc_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        return {"success": True, "message": f"文档 {doc_id} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/documents/{doc_id}", response_model=SearchResult, summary="获取文档")
async def get_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    获取单个文档详情
    
    Args:
        doc_id: 文档ID
    """
    try:
        service = get_search_service()
        result = service.get_document(doc_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


# ==================== 统计/管理接口 ====================

@router.get("/stats", response_model=SearchStats, summary="获取统计")
async def get_stats(user: dict = Depends(get_current_user)):
    """
    获取向量库统计信息
    
    Returns:
        文档总数、集合名称等
    """
    try:
        service = get_search_service()
        return service.get_stats()
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/documents", response_model=List[SearchResult], summary="列出文档")
async def list_documents(
    limit: int = Query(100, ge=1, le=1000, description="数量限制"),
    user: dict = Depends(get_current_user)
):
    """
    列出所有文档（用于管理）
    
    Args:
        limit: 返回数量限制
    """
    try:
        service = get_search_service()
        return service.list_documents(limit=limit)
    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


@router.post("/init-stocks", summary="初始化股票数据")
async def init_stock_data(
    user: dict = Depends(get_current_user)
):
    """
    从 MongoDB 初始化股票基础数据到向量库
    
    调用 scripts/init_vector_store.py 的逻辑
    """
    try:
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "scripts/init_vector_store.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            logger.error(f"初始化失败: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"初始化失败: {result.stderr}")
        
        return {
            "success": True,
            "message": "股票数据初始化完成",
            "output": result.stdout
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"初始化股票数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")

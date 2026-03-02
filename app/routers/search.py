"""
搜索 API 路由
提供向量语义搜索、BM25 关键词搜索、文档管理等功能
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth_db import get_current_user
from app.services.search import (
    # 向量搜索
    SearchService,
    get_search_service,
    SearchRequest,
    SearchResult,
    DocumentInsert,
    DocumentInsertResponse,
    SearchStats,
    # BM25 关键词搜索
    BM25SearchService,
    get_bm25_search_service,
    BM25SearchRequest,
    BM25SearchResultItem,
    BM25DocumentInsert,
    BM25DocumentInsertResponse,
    BM25SearchStats,
)

router = APIRouter(prefix="/search", tags=["搜索服务"])
logger = logging.getLogger("webapi")


# ==================== 向量搜索接口 ====================

@router.post("/vector/query", response_model=List[SearchResult], summary="向量语义搜索")
async def vector_search_documents(
    request: SearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    向量语义搜索
    
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
        logger.error(f"向量搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/vector/query", response_model=List[SearchResult], summary="向量语义搜索(GET)")
async def vector_search_documents_get(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50, description="返回数量"),
    user: dict = Depends(get_current_user)
):
    """
    向量语义搜索 (GET 方式)
    
    方便浏览器直接测试
    
    Example:
        GET /api/v1/search/vector/query?q=平安银行&top_k=5
    """
    try:
        service = get_search_service()
        results = service.search(query=q, top_k=top_k)
        return results
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ==================== BM25 关键词搜索接口 ====================

@router.post("/bm25/query", response_model=List[BM25SearchResultItem], summary="BM25关键词搜索")
async def bm25_search_documents(
    request: BM25SearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    BM25 关键词搜索
    
    基于关键词匹配的高效检索，适合精确术语搜索
    
    Example:
        ```json
        {
            "query": "平安银行",
            "top_k": 5,
            "filter_metadata": {"source": "stock_daily_basic"}
        }
        ```
    """
    try:
        service = get_bm25_search_service()
        results = service.search(
            query=request.query,
            top_k=request.top_k,
            filter_metadata=request.filter_metadata
        )
        return results
    except Exception as e:
        logger.error(f"BM25 搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/bm25/query", response_model=List[BM25SearchResultItem], summary="BM25关键词搜索(GET)")
async def bm25_search_documents_get(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50, description="返回数量"),
    user: dict = Depends(get_current_user)
):
    """
    BM25 关键词搜索 (GET 方式)
    
    方便浏览器直接测试
    
    Example:
        GET /api/v1/search/bm25/query?q=000001&top_k=5
    """
    try:
        service = get_bm25_search_service()
        results = service.search(query=q, top_k=top_k)
        return results
    except Exception as e:
        logger.error(f"BM25 搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/bm25/stats", response_model=BM25SearchStats, summary="BM25统计信息")
async def get_bm25_stats(user: dict = Depends(get_current_user)):
    """
    获取 BM25 搜索统计信息
    
    Returns:
        文档总数、索引状态等
    """
    try:
        service = get_bm25_search_service()
        return service.get_stats()
    except Exception as e:
        logger.error(f"获取 BM25 统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


# ==================== BM25 文档管理接口 ====================

@router.post("/bm25/documents", response_model=BM25DocumentInsertResponse, summary="BM25添加文档")
async def bm25_add_document(
    doc: BM25DocumentInsert,
    user: dict = Depends(get_current_user)
):
    """
    添加单条文档到 BM25 索引
    
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
        service = get_bm25_search_service()
        
        # 添加用户信息到 metadata
        meta = doc.metadata or {}
        meta["created_by"] = user.get("username", "unknown")
        
        doc_id = service.add_document(
            content=doc.content,
            metadata=meta,
            doc_id=doc.doc_id
        )
        
        return BM25DocumentInsertResponse(
            doc_id=doc_id,
            content_preview=doc.content[:50] + "..." if len(doc.content) > 50 else doc.content,
            status="success"
        )
    except Exception as e:
        logger.error(f"BM25 添加文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加文档失败: {str(e)}")


@router.post("/bm25/documents/batch", response_model=List[str], summary="BM25批量添加文档")
async def bm25_add_documents_batch(
    documents: List[BM25DocumentInsert],
    user: dict = Depends(get_current_user)
):
    """
    批量添加文档到 BM25 索引
    
    Example:
        ```json
        [
            {"content": "文档1", "metadata": {"type": "news"}},
            {"content": "文档2", "metadata": {"type": "report"}}
        ]
        ```
    """
    try:
        service = get_bm25_search_service()
        
        # 添加用户信息到 metadata
        for doc in documents:
            if doc.metadata is None:
                doc.metadata = {}
            doc.metadata["created_by"] = user.get("username", "unknown")
        
        doc_ids = service.add_documents(documents)
        return doc_ids
    except Exception as e:
        logger.error(f"BM25 批量添加文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量添加失败: {str(e)}")


@router.delete("/bm25/documents/{doc_id}", summary="BM25删除文档")
async def bm25_delete_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    删除 BM25 索引中的指定文档
    
    Args:
        doc_id: 文档ID
    """
    try:
        service = get_bm25_search_service()
        result = service.delete_document(doc_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        return {"success": True, "message": f"文档 {doc_id} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BM25 删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/bm25/documents/{doc_id}", response_model=BM25SearchResultItem, summary="BM25获取文档")
async def bm25_get_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    获取 BM25 索引中的单个文档详情
    
    Args:
        doc_id: 文档ID
    """
    try:
        service = get_bm25_search_service()
        result = service.get_document(doc_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BM25 获取文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/bm25/documents", response_model=List[BM25SearchResultItem], summary="BM25列出文档")
async def bm25_list_documents(
    limit: int = Query(100, ge=1, le=1000, description="数量限制"),
    user: dict = Depends(get_current_user)
):
    """
    列出 BM25 索引中的所有文档（用于管理）
    
    Args:
        limit: 返回数量限制
    """
    try:
        service = get_bm25_search_service()
        return service.list_documents(limit=limit)
    except Exception as e:
        logger.error(f"BM25 列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


@router.post("/bm25/save", summary="BM25保存索引")
async def bm25_save_index(user: dict = Depends(get_current_user)):
    """
    手动保存 BM25 索引到磁盘
    """
    try:
        service = get_bm25_search_service()
        result = service.save()
        if result:
            return {"success": True, "message": "索引保存成功"}
        else:
            raise HTTPException(status_code=500, detail="索引保存失败")
    except Exception as e:
        logger.error(f"BM25 保存索引失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


# ==================== 向量搜索文档管理接口 ====================

@router.post("/vector/documents", response_model=DocumentInsertResponse, summary="向量添加文档")
async def vector_add_document(
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


@router.post("/vector/documents/batch", response_model=List[str], summary="向量批量添加文档")
async def vector_add_documents_batch(
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


@router.delete("/vector/documents/{doc_id}", summary="向量删除文档")
async def vector_delete_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    删除向量库中的指定文档
    
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


@router.get("/vector/documents/{doc_id}", response_model=SearchResult, summary="向量获取文档")
async def vector_get_document(
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """
    获取向量库中的单个文档详情
    
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

@router.get("/vector/stats", response_model=SearchStats, summary="向量搜索统计")
async def get_vector_stats(user: dict = Depends(get_current_user)):
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


@router.get("/vector/documents", response_model=List[SearchResult], summary="向量列出文档")
async def vector_list_documents(
    limit: int = Query(100, ge=1, le=1000, description="数量限制"),
    user: dict = Depends(get_current_user)
):
    """
    列出向量库中的所有文档（用于管理）
    
    Args:
        limit: 返回数量限制
    """
    try:
        service = get_search_service()
        return service.list_documents(limit=limit)
    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


# ==================== 初始化接口 ====================

@router.post("/init/vector-stocks", summary="初始化向量股票数据")
async def init_vector_stock_data(
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
            logger.error(f"向量数据初始化失败: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"初始化失败: {result.stderr}")
        
        return {
            "success": True,
            "message": "向量股票数据初始化完成",
            "output": result.stdout
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"初始化向量股票数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


@router.post("/init/bm25-stocks", summary="初始化BM25股票数据")
async def init_bm25_stock_data(
    user: dict = Depends(get_current_user)
):
    """
    从 MongoDB 初始化股票基础数据到 BM25 索引
    
    调用 scripts/init_bm25_store.py 的逻辑
    """
    try:
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "scripts/init_bm25_store.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            logger.error(f"BM25 数据初始化失败: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"初始化失败: {result.stderr}")
        
        return {
            "success": True,
            "message": "BM25 股票数据初始化完成",
            "output": result.stdout
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"初始化 BM25 股票数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


@router.post("/init/all-stocks", summary="初始化所有搜索数据")
async def init_all_stock_data(
    user: dict = Depends(get_current_user)
):
    """
    从 MongoDB 初始化股票基础数据到向量库和 BM25 索引
    
    同时调用 scripts/init_vector_store.py 和 scripts/init_bm25_store.py
    """
    try:
        import subprocess
        import sys
        
        results = {
            "vector": {"success": False, "output": "", "error": ""},
            "bm25": {"success": False, "output": "", "error": ""}
        }
        
        # 初始化向量数据
        try:
            result = subprocess.run(
                [sys.executable, "scripts/init_vector_store.py"],
                capture_output=True,
                text=True,
                timeout=300
            )
            results["vector"]["success"] = result.returncode == 0
            results["vector"]["output"] = result.stdout
            results["vector"]["error"] = result.stderr
        except Exception as e:
            results["vector"]["error"] = str(e)
        
        # 初始化 BM25 数据
        try:
            result = subprocess.run(
                [sys.executable, "scripts/init_bm25_store.py"],
                capture_output=True,
                text=True,
                timeout=300
            )
            results["bm25"]["success"] = result.returncode == 0
            results["bm25"]["output"] = result.stdout
            results["bm25"]["error"] = result.stderr
        except Exception as e:
            results["bm25"]["error"] = str(e)
        
        # 检查是否全部成功
        all_success = results["vector"]["success"] and results["bm25"]["success"]
        
        if all_success:
            return {
                "success": True,
                "message": "所有搜索数据初始化完成",
                "results": results
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail={
                    "message": "部分初始化失败",
                    "results": results
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"初始化所有搜索数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")

"""
对话机器人 - OpenAI兼容流式响应
"""

import json
import time
import uuid
import logging
from collections import defaultdict
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Header, Depends, status, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.services.chatbot.chatbot_service import chat
from app.routers.auth_db import get_current_user
from app.core.db.document import get_chat_history, del_user_conversation, update_conversation_title


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "qwen-plus"
    messages: List[Message]
    stream: Optional[bool] = True
    temperature: Optional[float] = 0.8
    max_tokens: Optional[int] = 256


class ChatHistoryResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    total: int
    message: str = ""


class DeleteConversationRequest(BaseModel):
    conversation_id: str = Field(..., description="要删除的对话会话ID")


class UpdateTitleRequest(BaseModel):
    conversation_id: str = Field(..., description="对话会话ID")
    title: str = Field(..., min_length=1, max_length=200, description="新标题")


class UserInfo(BaseModel):
    username: str


UserID = str


router = APIRouter()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


logger = get_logger('chat_bot')


@router.post("/chat/completions")
async def chat_completions(
        request: ChatCompletionRequest,
        x_conversation_id: Optional[str] = Header(default="", alias="x_conversation_id"),
        # user: dict = Depends(get_current_user)
):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages不能为空")

    user_query = request.messages[-1].content
    if not user_query:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # 处理conversation_id
    conversation_id = x_conversation_id or str(uuid.uuid4())

    # 从user字典中提取user_id
    # user_id = user.get("username", "unknown")
    user_id = '11234'
    logger.debug(f"💬 聊天请求 - user_id: {user_id}, conversation_id: {conversation_id}")

    if request.stream:
        return StreamingResponse(
            stream_response(request_id, user_query, conversation_id, user_id),
            media_type="text/event-stream",
            headers={"x-conversation-id": conversation_id}
        )
    else:
        response_data = await non_stream_response(request_id, user_query, conversation_id, user_id)
        return JSONResponse(
            content=response_data,
            headers={"x-conversation-id": conversation_id}
        )


@router.get("/listChat", response_model=ChatHistoryResponse, status_code=status.HTTP_200_OK)
async def list_chat_completions(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数，最大100"),
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    查询用户的历史聊天记录
    
    该接口用于获取用户的所有对话会话列表，
    按时间降序排列，支持分页
    
    Args:
        page: 页码，从1开始
        page_size: 每页记录数，最大100
        user: 经过JWT认证的用户信息
        
    Returns:
        Dict[str, Any]: 包含对话列表和元数据的标准响应
    """
    try:
        user_id: UserID = user.get("username", "unknown")

        chat_history = get_chat_history(user_id)

        # 按 conversation_id 分组
        grouped = defaultdict(list)
        for item in chat_history:
            key = item['conversation_id']
            grouped[key].append(item)

        result = []
        # 查看结果
        for conv_id, items in grouped.items():
            title = items[0].get("title", "")
            create_datetime = items[0].get("create_datetime", "")
            messages = []
            for item in items:
                messages.extend(item.get("messages", []))

            data_item = {
                "conversation_id": conv_id,
                "create_datetime": create_datetime,
                "title": title,
                "messages": messages,
            }
            result.append(data_item)
        

        total = len(result)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated_messages = result[start_idx:end_idx]
        total_pages = (total + page_size - 1) // page_size

        return {
            "success": True,
            "message": "查询成功",
            "data": {
                "messages": paginated_messages,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages
                }
            },
            "total": total
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询聊天记录失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="查询聊天记录失败，请稍后重试"
        )


@router.post("/deleteConversation", status_code=status.HTTP_200_OK)
async def delete_conversation(
    request: DeleteConversationRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    删除指定用户会话的聊天记录
    
    Args:
        request: 包含要删除的会话ID
        user: 经过JWT认证的用户信息
        
    Returns:
        Dict[str, Any]: 包含删除结果的响应
    """
    try:
        user_id: str = user.get("username", "unknown")
        conversation_id: str = request.conversation_id
        
        if not conversation_id or not conversation_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的会话ID"
            )
        
        logger.info(f"删除会话 - user_id: {user_id}, conversation_id: {conversation_id}")
        
        success = del_user_conversation(user_id, conversation_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该会话或删除失败"
            )
        
        return {
            "success": True,
            "message": "会话删除成功",
            "data": {"conversation_id": conversation_id},
            "total": 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除会话失败，请稍后重试"
        )


@router.put("/updateConversationTitle", status_code=status.HTTP_200_OK)
async def update_conversation_title_endpoint(
    request: UpdateTitleRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    修改指定会话的标题
    
    Args:
        request: 包含会话ID和新标题
        user: 经过JWT认证的用户信息
        
    Returns:
        Dict[str, Any]: 包含更新结果的响应
    """
    try:
        user_id: str = user.get("id", "unknown")
        conversation_id: str = request.conversation_id
        title: str = request.title
        
        if not conversation_id or not conversation_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的会话ID"
            )
        
        if not title or not title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标题不能为空"
            )
        
        logger.info(f"更新会话标题 - user_id: {user_id}, conversation_id: {conversation_id}, title: {title}")
        
        success = update_conversation_title(user_id, conversation_id, title)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该会话或更新失败"
            )
        
        return {
            "success": True,
            "message": "会话标题更新成功",
            "data": {"conversation_id": conversation_id, "title": title},
            "total": 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话标题失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新会话标题失败，请稍后重试"
        )


async def stream_response(request_id: str, user_query: str, conversation_id: str, user_id: str):
    print("-" * 60)
    print(f"request_id: {request_id}, conversation_id: {conversation_id}, user_id: {user_id}")

    for chunk in chat(user_query, user_id=user_id, conversation_id=conversation_id):
        if chunk:
            chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else str(chunk)
            if chunk_str.strip():
                yield f"{chunk_str}\n\n"


async def non_stream_response(request_id: str, user_query: str, conversation_id: str, user_id: str):
    full_content = ""
    for chunk in chat(user_query, user_id=user_id, conversation_id=conversation_id):
        if chunk:
            chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else str(chunk)
            try:
                data = json.loads(chunk_str)
                if 'choices' in data and data['choices']:
                    delta = data['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    full_content += content
            except:
                pass

    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "qwen-plus",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }

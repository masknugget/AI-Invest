"""
对话机器人 - OpenAI兼容流式响应
"""

import json
import time
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.chatbot.chatbot_service import chat
from app.routers.auth_db import get_current_user


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "qwen-plus"
    messages: List[Message]
    stream: Optional[bool] = True
    temperature: Optional[float] = 0.8
    max_tokens: Optional[int] = 256


router = APIRouter()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


logger = get_logger('chat_bot')


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    x_conversation_id: Optional[str] = Header(default="", alias="x-conversation-id"),
    authorization: Optional[str] = Header(default=None),
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
            media_type="text/event-stream"
        )
    else:
        return await non_stream_response(request_id, user_query, conversation_id, user_id)


async def stream_response(request_id: str, user_query: str, conversation_id: str, user_id: str):
    print("-"*60)
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
        },
        "headers": {"x-conversation-id": conversation_id}
    }

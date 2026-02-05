import json
import uuid
from typing import Generator, Dict, Any

from app.core.db.document import log_chat_history
from app.services.chatbot.intent import recognition_intent
from app.services.chatbot.llm_direct_call import post_stream
from app.services.chatbot import tools
from app.services.chatbot.track import ChatTracker


def chat(
        user_query: str,
        user_id: str = "",
        conversation_id: str = ""
) -> Generator[str, None, None]:
    """
    处理用户查询的主函数
    
    Args:
        user_query: 用户输入的查询
        user_id: 用户ID
        conversation_id: 对话ID（用于多轮对话）
        
    Yields:
        流式返回LLM的响应片段
    """
    
    tracker = ChatTracker()
    tracker.user_id = user_id
    tracker.chat_id = str(uuid.uuid4())
    tracker.conversation_id = conversation_id or str(uuid.uuid4())
    tracker.user_query = user_query
    
    model_used = "qwen-plus"
    
    try:
        # Step 1: 识别用户意图
        intent_result = recognition_intent(user_query=user_query)
        print('-'*69)
        print(intent_result)
        
        # 提取股票代码（如果有）
        arguments = intent_result.get("arguments", {})
        if "symbol" in arguments:
            tracker.stock_symbol = arguments["symbol"]
        
        function_name = intent_result.get("function_name", "chat")
        if function_name == "chat":
            # 无需工具，直接对话
            system_content = "You are a helpful assistant."
            
            json_data = {
                "model": model_used,
                "temperature": 0.8,
                "max_tokens": 1024,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_query}
                ]
            }
            yield from post_stream(json_data, tracker)
        elif function_name == "search_stock_information":
            # 调用工具搜索股票信息
            tool_func = getattr(tools, function_name, None)
            if tool_func:
                try:
                    tool_data = tool_func(**arguments)
                    system_content = f"请根据以下股票信息回答用户问题:\n\n{tool_data}"
                    
                    json_data = {
                        "model": model_used,
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "stream": True,
                        "messages": [
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": user_query}
                        ]
                    }
                    yield from post_stream(json_data, tracker)
                except Exception as e:
                    yield f"工具调用出错: {str(e)}"
            else:
                yield f"未找到工具函数: {function_name}"
        elif function_name == "analyze_stock_by_type":
            # 调用工具进行股票分析
            tool_func = getattr(tools, function_name, None)
            if tool_func:
                try:
                    tool_data = tool_func(**arguments)
                    if isinstance(tool_data, dict) and tool_data.get("status") == "success":
                        system_content = tool_data.get("prompt", "")
                    else:
                        system_content = f"数据获取失败: {tool_data.get('error', '未知错误')}"
                    
                    json_data = {
                        "model": model_used,
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "stream": True,
                        "messages": [
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": user_query}
                        ]
                    }
                    yield from post_stream(json_data, tracker)
                except Exception as e:
                    yield f"工具调用出错: {str(e)}"
            else:
                yield f"未找到工具函数: {function_name}"
        else:
            # 未知函数名，默认直接对话
            system_content = "You are a helpful assistant."
            
            json_data = {
                "model": model_used,
                "temperature": 0.8,
                "max_tokens": 1024,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_query}
                ]
            }
            yield from post_stream(json_data, tracker)
    except Exception as e:
        error_message = f"系统处理出错: {str(e)}"
        yield error_message
    finally:
        # 保存对话历史（无论成功或失败）
        try:
            log_chat_history(tracker.to_dict())
        except Exception as log_error:
            print(f"日志记录失败: {str(log_error)}")

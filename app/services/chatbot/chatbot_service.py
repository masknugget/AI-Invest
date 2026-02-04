import json
from typing import Generator, Dict, Any
from app.services.chatbot.intent import recognition_intent
from app.services.chatbot.llm_direct_call import post_stream
from app.services.chatbot import tools


def chat(user_query: str) -> Generator[str, None, None]:
    """
    处理用户查询的主函数
    
    Args:
        user_query: 用户输入的查询
        
    Yields:
        流式返回LLM的响应片段
    """
    try:
        # Step 1: 识别用户意图
        intent_result = recognition_intent(user_query=user_query)
        
        # Step 2: 检查是否需要调用工具
        if intent_result.get("success") and intent_result.get("function_name"):
            # 需要调用工具
            tool_func = getattr(tools, intent_result["function_name"], None)
            
            if tool_func:
                try:
                    # 调用工具并获取数据
                    tool_data = tool_func(**intent_result.get("arguments", {}))
                    
                    # 准备系统提示
                    if isinstance(tool_data, dict) and tool_data.get("status") == "success":
                        system_content = f"你是专业财经分析师。基于以下数据生成分析报告,以markdown格式输出：\n\n{tool_data.get('prompt', '')}"
                    else:
                        system_content = f"数据获取失败: {tool_data.get('error', '未知错误')}"
                    
                    # Step 3: 调用LLM生成最终回复
                    json_data = {
                        "model": "qwen-plus",
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "stream": True,
                        "messages": [
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": user_query}
                        ]
                    }
                    
                    yield from post_stream(json_data)
                    return
                    
                except Exception as e:
                    yield f"工具调用出错: {str(e)}"
                    return
        
        # Step 3: 无需工具或出错，直接对话
        json_data = {
            "model": "qwen-plus",
            "temperature": 0.8,
            "max_tokens": 1024,
            "stream": True,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_query}
            ]
        }
        
        yield from post_stream(json_data)
        
    except Exception as e:
        # 系统异常处理
        yield f"系统处理出错: {str(e)}"
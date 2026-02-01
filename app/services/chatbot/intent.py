import json
import aiohttp
from typing import Dict, List, Optional, Any
from app.services.chatbot.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    MODEL_NAME,
    MAX_TOKENS,
    TEMPERATURE,
)
from app.services.chatbot.tools import get_tools_json
from app.services.chatbot.prompts.p_general import get_intent_system_prompt
from app.services.chatbot.models.schemas import IntentResponse, ToolCall, IntentType


async def recognize_intent(user_query: str) -> IntentResponse:
    """
    识别用户意图
    
    Args:
        user_query: 用户输入的问题
        
    Returns:
        意图识别结果
    """
    tools_json = get_tools_json()
    system_prompt = get_intent_system_prompt()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
        {"role": "system", "content": f"可用工具：\n{tools_json}"},
    ]
    
    request_data = {
        "model": MODEL_NAME,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "messages": messages,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=f"{DASHSCOPE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
            json=request_data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"意图识别失败，状态码：{resp.status}, 错误：{error_text}")
            
            result = await resp.json()
            content = result["choices"][0]["message"]["content"]
            
            try:
                intent_data = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    intent_data = json.loads(json_match.group())
                else:
                    return IntentResponse(
                        intent=IntentType.CHAT,
                        confidence=0.5,
                        tool_calls=None,
                    )
            
            intent_type = intent_data.get("intent", "chat")
            if intent_type not in ["query_stock", "analyze_stock", "analyze_by_type", "chat"]:
                intent_type = "chat"
            
            tool_calls_raw = intent_data.get("tool_calls", [])
            tool_calls = None
            
            if tool_calls_raw:
                tool_calls = [
                    ToolCall(
                        name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                    )
                    for tc in tool_calls_raw
                ]
            
            return IntentResponse(
                intent=IntentType(intent_type),
                confidence=float(intent_data.get("confidence", 0.8)),
                tool_calls=tool_calls,
            )


def execute_tool(tool_call: ToolCall) -> Dict[str, Any]:
    """
    执行工具调用
    
    Args:
        tool_call: 工具调用信息
        
    Returns:
        工具执行结果
    """
    from app.services.chatbot.tools import (
        search_stock_information,
        analyze_stock_information,
        analyze_stock_by_type,
    )
    
    tool_map = {
        "search_stock_information": search_stock_information,
        "analyze_stock_information": analyze_stock_information,
        "analyze_stock_by_type": analyze_stock_by_type,
    }
    
    tool_name = tool_call.name
    if tool_name not in tool_map:
        return {"success": False, "error": f"未知的工具: {tool_name}"}
    
    try:
        tool_func = tool_map[tool_name]
        result = tool_func(**tool_call.arguments)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import asyncio
    
    async def test():
        test_queries = [
            "平安银行今天股价多少？",
            "帮我分析一下贵州茅台",
            "五粮液技术面怎么样？",
            "你好啊",
        ]
        
        for query in test_queries:
            print(f"\n用户查询：{query}")
            try:
                intent = await recognize_intent(query)
                print(f"识别意图：{intent.intent}")
                print(f"置信度：{intent.confidence}")
                if intent.tool_calls:
                    for tc in intent.tool_calls:
                        print(f"工具调用：{tc.name}({tc.arguments})")
            except Exception as e:
                print(f"错误：{e}")
    
    asyncio.run(test())

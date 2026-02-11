from langchain_core.output_parsers import JsonOutputParser

from app.services.chatbot.llm_direct_call import post
from app.services.chatbot.prompts.p_intent import wrap_intent
from app.services.chatbot.tools import get_tools_json
import json


def parse_intent_from_llm_response(llm_response: dict) -> dict:
    """
    从LLM响应中解析意图，提取函数名和参数
    
    Args:
        llm_response: LLM返回的JSON响应数据
        
    Returns:
        包含解析结果的字典:
        - success: 是否解析成功
        - function_name: 函数名
        - arguments: 参数字典
        - error: 错误信息（当success为False时）
        - content: 原始内容（解析失败时返回）
    """
    content = None
    
    try:
        if not llm_response or "choices" not in llm_response:
            return {
                "success": False,
                "error": "无效的LLM响应格式"
            }
        
        content = llm_response["choices"][0]["message"]["content"]

        json_p = JsonOutputParser()

        # function_data = json.loads(content)
        function_data = json_p.parse(content)

        function_name = function_data.get("name")
        arguments = function_data.get("arguments", {})
        
        if not function_name:
            return {
                "success": False,
                "error": "未找到函数名",
                "parsed_data": function_data
            }
        
        return {
            "success": True,
            "function_name": function_name,
            "arguments": arguments
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON解析失败: {str(e)}",
            "content": content
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"解析失败: {str(e)}",
            "llm_response": llm_response
        }



def recognition_intent(
        user_query: str
):



    tools = get_tools_json()
    user_query_intent = wrap_intent(user_query, tools=tools)

    json_data = {
        "model": "qwen-plus",
        "temperature": 0.8,
        "frequency_penalty": 0.5,
        "max_tokens": 256,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": user_query_intent
            }
        ]
    }

    result = post(json_data)
    data_json = result.json()
    parsed_result = parse_intent_from_llm_response(data_json)


    if 'parsed_result' in parsed_result:
        parsed_result = parsed_result['parsed_result']
        if "function_call" in parsed_result:
            parsed_result = parsed_result['function_call']
    return parsed_result


data_json = recognition_intent(user_query="今天气温咋样")
print("=" * 80)
print("LLM 响应:")
print(json.dumps(data_json, indent=2, ensure_ascii=False))

print("\n" + "=" * 80)
print("意图解析结果:")


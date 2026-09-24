import json
import time
from json import JSONDecodeError

from app.core.db.document import log_chat_history
from app.services.chatbot.intent import recognition_intent
from app.services.chatbot.tools import analyze_stock_by_type, search_stock_information, search_breaking_news


def chat(
        user_query: str,
        conversation_id: str = ""
) -> str:
    """
    处理用户查询的主函数

    Args:
        user_query: 用户输入的查询

    str:
        返回不同的内容
    """
    time_s = time.time()
    try:
        print(user_query)
        # Step 1: 识别用户意图

        time_s1 = time.time()
        intent_result = recognition_intent(user_query=user_query)

        print("time >>> 意图识别耗时", time.time() - time_s1)
        print('-' * 69)
        print(intent_result)

        # 提取股票代码（如果有）
        arguments = intent_result.get("arguments", {})

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except JSONDecodeError as e:
                try:
                    import ast
                    arguments = ast.literal_eval(arguments)
                except Exception as e:
                    print(e)
                    pass

        if 'code' in arguments:
            code = arguments.pop('code')
            arguments['stock_code'] = code

        function_name = intent_result.get("function_name", "chat")
        print(function_name)

        if function_name == "chat":
            # 无需工具，直接对话
            system_content = "You are a helpful assistant. 根据用户输入回答问题"

        elif function_name == "search_stock_information":
            # 调用工具搜索股票信息
            tool_func = search_stock_information
            if tool_func:
                try:
                    tool_data, data_dt = search_stock_information(**arguments)
                    system_content = f"请根据以下股票信息回答用户问题：以最新优先、如果最新有数据的话、否则用其他\n\n{tool_data}"
                except Exception as e:
                    return f"工具调用出错: {str(e)}"
            else:
                return f"未找到工具函数: {function_name}"
        elif function_name == "analyze_stock_by_type":
            tool_func = analyze_stock_by_type
            if tool_func:
                start_time = time.time()
                try:
                    # 进行工具调用
                    stock_code = arguments.get('stock_code')
                    analyze_type_list = arguments.get('analyze_type_list')

                    # 进行分析，分析后的数据再里面
                    tool_data = analyze_stock_by_type(stock_code, analyze_type_list)

                    if isinstance(tool_data, dict) and tool_data.get("status") == "success":
                        system_content = tool_data.get("prompt", "")
                    else:
                        system_content = "暂时没有找到相关数据，礼貌回复用户"
                except Exception as e:
                    print("工具调用失败, analyze_stock_by_type", str(e))
                    system_content = "暂时没有找到相关数据，礼貌回复用户"
            else:
                return f"未找到工具函数: {function_name}"
        elif function_name == "search_breaking_news":
            tool_func = search_breaking_news
            system_content = "You are a helpful assistant."
            if tool_func:
                try:
                    market = arguments.get('market', "HK")
                    if market == '':
                        market = 'HK'
                    out_data = search_breaking_news(market)
                    system_content = f"最新新闻如下{out_data}"
                except Exception as e:
                    system_content = "You are a helpful assistant."
            else:
                # 未知函数名，默认直接对话
                system_content = "You are a helpful assistant."

        return system_content
    except Exception as e:
        error_message = f"系统处理出错: {str(e)}"
        return error_message
    finally:
        time_e = time.time()
        print('time >>> 一次chat的时间', time_e - time_s)
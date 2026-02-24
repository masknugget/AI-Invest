import json
import random
from typing import Dict, Optional, Union
from datetime import datetime

from app.core.db.document import get_symbol
from tradingagents.db.document import get_stock_daily_basic, get_stock_information

# 导入prompts模块
from app.services.chatbot.prompts import p_fundamentals_analyst, p_market_analyst, p_news_analyst
from tradingagents.utils.stock_utils import unified_code


def search_stock_information(
        stock_code_name: str,
        date_time: Optional[str] = None,
        indicator_name: Optional[str] = None
) -> str:
    """
    查找股票信息，搜索股票价格和技术指标
    
    Args:
        stock_code: 股票代码或 股票名称
        date_time: 日期（格式：YYYY-MM-DD，默认为今天）
        indicator_name: 指标名称（如：收盘价、开盘价、成交量、涨跌幅等）
        
    Returns:
        股票信息字典，包含代码、名称、价格、指标等
    """
    if str(stock_code_name[0]).isdigit():
        stock_code_name = unified_code(stock_code_name)
    code_result = get_symbol(stock_code_name)
    stock_code = code_result['symbol']
    stock_name = code_result['name']

    result_dt = get_stock_information(stock_code, "2025-01-16", "2025-06-16")
    result_str = f"""
股票名称: {stock_name}
股票代码: {result_dt["symbol"]}
收盘价: {result_dt["close"]}
市盈率: {result_dt["pe"]}
市净率: {result_dt["pb"]}
市销率: {result_dt["ps"]}

"""
    return result_str



def analyze_stock_by_type(stock_code: str, analyze_type: str, language: str = "zh-CN") -> Dict[str, Union[str, float, None]]:
    """
    按指定类型分析股票（基本面、技术面、新闻面）

    Args:
        stock_code: 股票代码或名称
        analyze_type: 分析类型（基本面、技术面、新闻面）
        language: 主要的语言

    Returns:
        专项分析结果，包含生成的prompt
    """

    if str(stock_code[0]).isdigit():
        stock_code = unified_code(stock_code)
    code_result = get_symbol(stock_code)
    stock_code = code_result['symbol']

    try:
        if analyze_type == "基本面":
            prompt = p_fundamentals_analyst.prompt_fundamentals_analyst(stock_code, language)
        elif analyze_type == "技术面":
            prompt = p_market_analyst.prompt_market_analyst(stock_code, language)
        elif analyze_type == "新闻面":
            prompt = p_news_analyst.prompt_news_analyst(stock_code, language)
        else:
            return {
                "prompt": f"不支持的分析类型: {analyze_type}",
                "analysis_type": analyze_type,
                "status": "error"
            }
        
        return {
            "prompt": prompt,
            "analysis_type": analyze_type,
            "status": "success"
        }
    except Exception as e:
        return {
            "prompt": f"生成分析Prompt时出错: {str(e)}",
            "analysis_type": analyze_type,
            "status": "error"
        }


def get_all_tools():
    """获取所有工具函数"""
    return [
        search_stock_information,
        analyze_stock_by_type,
    ]


def get_tools_json():
    """获取工具的JSON描述"""
    tools = get_all_tools()

    tool_schemas = []
    for tool in tools:
        schema = {
            "type": "function",
            "function": {
                "name": tool.__name__,
                "description": tool.__doc__.strip().split("\n")[0] if tool.__doc__ else "",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }

        import inspect
        sig = inspect.signature(tool)
        params = schema["function"]["parameters"]

        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"

            params["properties"][param_name] = {
                "type": param_type,
                "description": f"参数: {param_name}",
            }

            if param.default == inspect.Parameter.empty:
                params["required"].append(param_name)

        tool_schemas.append(schema)

    return json.dumps(tool_schemas, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print(get_tools_json())

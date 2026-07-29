import json
import random
import time
from typing import Dict, Optional, Union, List
from datetime import datetime

from app.core.db.document import get_symbol, search_symbol, get_daily_performance, get_symbol_info
from tradingagents.db.document import get_stock_daily_basic, get_stock_information

# 导入prompts模块
from app.services.chatbot.prompts import p_fundamentals_analyst, p_market_analyst, p_news_analyst
from tradingagents.utils.stock_utils import unified_code


def search_stock_information(
    stock_code: str,
    date_time: Optional[str] = None,
    indicator_name: Optional[str] = None
):
    """
    查找股票信息，搜索股票价格和技术指标

    Args:
        stock_code: 股票代码或 股票名称
        date_time: 日期（格式：YYYY-MM-DD，默认为今天）
        indicator_name: 指标名称（如：收盘价、开盘价、成交量、涨跌幅等）
    """
    time_s1 = time.time()

    code_result = search_symbol(stock_code)
    print('time >>> 获取get_symbol', time.time() - time_s1)

    stock_code = code_result['symbol']
    stock_name = code_result['name']

    time_s1 = time.time()
    result_dt = get_symbol_info(stock_code, "2025-01-16", "2025-06-16")
    print('time >>> 获取get_stock_information', time.time() - time_s1)

    result_str = f"""
    股票名称: {stock_name}
    股票代码: {result_dt["symbol"]}
    收盘价: {result_dt["close"]}
    商业描述: {result_dt["business_desc"]}
    """

    data_dt = {
        "收盘价": result_dt["close"],
        "市盈率": result_dt["pe"],
        "市净率": result_dt["pb"],
        "市销率": result_dt["ps"],
    }

    return result_str, data_dt



def analyze_stock_by_type(
    stock_code: str,
    analyze_type_list: List[str],
    language: str = "zh-CN"
) -> Dict[str, Union[str, float, None, Dict]]:
    """
    按指定类型分析股票（基本面、技术面、新闻面）

    Args:
        stock_code: 股票代码或名称
        analyze_type_list: 分析类型（基本面、技术面、新闻面）
        language: 主要的语言

    Returns:
        专项分析结果，包含生成的prompt
    """

    time_s1 = time.time()

    code_result = search_symbol(stock_code)
    print('time >>> 获取get_symbol', time.time() - time_s1)

    stock_code = code_result['symbol']
    market = code_result.get("market", 'HK')
    code, data_out = get_daily_performance(stock_code, '2025-01-01', '2026-12-31', market=market)
    # code, data_out = get_stock_daily_basic(stock_code, '2025-01-01', '2026-12-31')

    def convert_float(item_data):
        if hasattr(item_data, 'to_decimal'):
            return item_data.to_decimal()
        return item_data

    data_out_price = {
        'date': [str(i)[:10] for i in data_out['trade_date']],
        'price_open': [float(convert_float(i)) for i in data_out['open']],
        'price_high': [float(convert_float(i)) for i in data_out['high']],
        'price_low': [float(convert_float(i)) for i in data_out['low']],
        'price_close': [float(convert_float(i)) for i in data_out['close']],
        'volume': [float(convert_float(i)) for i in data_out['volume']],
    }

    len_data = len(data_out_price.get('date'))

    out_data = {
        "data_out_price": data_out_price,
        "new_list": [],
        "report_data": {}
    }

    if isinstance(analyze_type_list, str):
        import ast
        analyze_type_list = ast.literal_eval(analyze_type_list)
    print(analyze_type_list, type(analyze_type_list))

    prompt_str = ""
    for analyze_type in analyze_type_list:
        try:
            if analyze_type == "基本面":
                prompt, data_report = p_fundamentals_analyst.prompt_fundamentals_analyst(stock_code, language, market=market)
                out_data['report_data'] = data_report
            elif analyze_type == "技术面":
                prompt = p_market_analyst.prompt_market_analyst(stock_code, language, market=market)
            elif analyze_type == "新闻面":
                prompt, new_list = p_news_analyst.prompt_news_analyst(stock_code, language, market=market)
                out_data['new_list'] = new_list
            else:
                # prompt = f"不支持的分析类型: {analyze_type}",
                continue
        except Exception as e:
            print(e)
            prompt = f"不支持的分析类型: {analyze_type}"

        prompt_str += '\n' + prompt

    return {
        "prompt": prompt_str,
        "analysis_type": analyze_type_list,
        "data": out_data,
        "len_data": len_data,
        "status": "success"
    }


def get_tools_json() -> str:
    """
    返回可供意图识别使用的工具列表 JSON 描述。
    """
    tools = [
        {
            "name": "search_stock_information",
            "description": "查找股票信息，搜索股票价格和技术指标",
            "parameters": {
                "stock_code": "股票代码或股票名称",
                "date_time": "日期（格式：YYYY-MM-DD，默认为今天）",
                "indicator_name": "指标名称（如：收盘价、开盘价、成交量、涨跌幅等）",
            },
        },
        {
            "name": "analyze_stock_by_type",
            "description": "按指定类型分析股票（基本面、技术面、新闻面）",
            "parameters": {
                "stock_code": "股票代码或名称",
                "analyze_type_list": "分析类型列表（基本面、技术面、新闻面）",
                "language": "主要语言，默认 zh-CN",
            },
        },
    ]
    return json.dumps(tools, ensure_ascii=False)



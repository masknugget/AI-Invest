from typing import List, Optional, Dict, Any
import time
import json

from app.core.db.document import search_symbol, get_daily_performance
from app.services.chatbot.prompts import p_fundamentals_analyst, p_market_analyst, p_news_analyst


def analyze_stock(
    stock_code: str,
    analyze_type_list: List[str],
    language: str = "zh-CN",
) -> str:
    """
    按指定类型对股票进行深度分析（基本面、技术面、新闻面）。

    该函数由 app.services.mcp.server 通过 mcp.add_tool() 注册为 MCP 工具，
    因此本模块不需要（也不能，避免循环导入）再使用 @mcp.tool() 装饰器。

    Args:
        stock_code: 股票代码或名称（如 "00700" 或 "腾讯控股"）。
        analyze_type_list: 分析类型列表，可选值："基本面"、"技术面"、"新闻面"。
        language: 返回语言，默认 "zh-CN"。

    Returns:
        JSON 字符串，包含分析类型、生成的 prompt、价格数据、新闻列表和财报数据。
    """
    time_s1 = time.time()

    code_result = search_symbol(stock_code)
    print("time >>> 获取search_symbol", time.time() - time_s1)

    if not code_result:
        return json.dumps({
            "status": "error",
            "message": f"未找到股票代码或名称: {stock_code}",
        }, ensure_ascii=False)

    stock_code = code_result.get("symbol", "")
    market = code_result.get("market", "HK")

    if not stock_code:
        return json.dumps({
            "status": "error",
            "message": f"未找到股票代码或名称: {stock_code}",
        }, ensure_ascii=False)

    time_s1 = time.time()
    # get_daily_performance 返回 (content_string, df_data_dict)
    _, data_out = get_daily_performance(stock_code, "2025-01-01", "2026-12-31", market=market)
    print("time >>> 获取get_daily_performance", time.time() - time_s1)

    def convert_float(item_data):
        if hasattr(item_data, "to_decimal"):
            return float(item_data.to_decimal())
        return float(item_data) if item_data is not None else None

    data_out_price = {
        "date": [str(i)[:10] for i in data_out.get("trade_date", [])],
        "price_open": [convert_float(i) for i in data_out.get("open", [])],
        "price_high": [convert_float(i) for i in data_out.get("high", [])],
        "price_low": [convert_float(i) for i in data_out.get("low", [])],
        "price_close": [convert_float(i) for i in data_out.get("close", [])],
        "volume": [convert_float(i) for i in data_out.get("volume", [])],
    }

    len_data = len(data_out_price.get("date", []))

    out_data = {
        "data_out_price": data_out_price,
        "new_list": [],
        "report_data": {},
    }

    # 兼容 MCP 客户端可能把列表传成字符串的情况
    if isinstance(analyze_type_list, str):
        import ast
        try:
            analyze_type_list = ast.literal_eval(analyze_type_list)
        except Exception:
            analyze_type_list = [analyze_type_list]

    prompt_str = ""
    for analyze_type in analyze_type_list:
        try:
            if analyze_type == "基本面":
                prompt, data_report = p_fundamentals_analyst.prompt_fundamentals_analyst(stock_code, language)
                out_data["report_data"] = data_report
            elif analyze_type == "技术面":
                prompt = p_market_analyst.prompt_market_analyst(stock_code, language)
            elif analyze_type == "新闻面":
                prompt, new_list = p_news_analyst.prompt_news_analyst(stock_code, language)
                out_data["new_list"] = new_list
            else:
                prompt = f"不支持的分析类型: {analyze_type}"
        except Exception as e:
            print(e)
            prompt = f"不支持的分析类型: {analyze_type}"

        prompt_str += "\n" + prompt

    result = {
        "prompt": prompt_str,
        "analysis_type": analyze_type_list,
        "data": out_data,
        "len_data": len_data,
        "status": "success",
    }

    return json.dumps(result, ensure_ascii=False, default=str)

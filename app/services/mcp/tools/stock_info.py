from typing import Optional
import time

from app.core.db.document import search_symbol, get_symbol_info


def get_stock_info(
    stock_code: str,
    date_time: Optional[str] = None,
    indicator_name: Optional[str] = None,
) -> str:
    """
    获取股票基础信息，包括收盘价、商业描述以及市盈率/市净率/市销率等关键指标。

    该函数由 app.services.mcp.server 通过 mcp.add_tool() 注册为 MCP 工具，
    因此本模块不需要（也不能，避免循环导入）再使用 @mcp.tool() 装饰器。

    Args:
        stock_code: 股票代码或股票名称（如 "00700" 或 "腾讯控股"）。
        date_time: 日期（格式：YYYY-MM-DD），保留参数用于后续扩展，目前内部使用默认区间。
        indicator_name: 指标名称（如：收盘价、开盘价、成交量、涨跌幅等），保留参数用于后续扩展。

    Returns:
        股票信息文本，包含名称、代码、收盘价、商业描述和指标数据。
    """
    time_s1 = time.time()

    code_result = search_symbol(stock_code)
    print("time >>> 获取search_symbol", time.time() - time_s1)

    if not code_result:
        return f"未找到股票代码或名称: {stock_code}"

    stock_code = code_result.get("symbol", "")
    stock_name = code_result.get("name", "")

    if not stock_code:
        return f"未找到股票代码或名称: {stock_code}"

    time_s1 = time.time()
    # 与原 chatbot.tools.search_stock_information 保持一致，使用固定区间获取最新快照数据
    result_dt = get_symbol_info(stock_code, "2025-01-16", "2025-06-16")
    result_dt = result_dt or {}
    print("time >>> 获取get_symbol_info", time.time() - time_s1)

    result_str = f"""股票名称: {stock_name}
股票代码: {result_dt.get("symbol", stock_code)}
收盘价: {result_dt.get("close", "")}
商业描述: {result_dt.get("business_desc", "")}
"""

    data_dt = {
        "收盘价": result_dt.get("close", ""),
        "市盈率": result_dt.get("pe", ""),
        "市净率": result_dt.get("pb", ""),
        "市销率": result_dt.get("ps", ""),
    }

    return result_str + "\n数据详情:\n" + "\n".join(f"{k}: {v}" for k, v in data_dt.items())

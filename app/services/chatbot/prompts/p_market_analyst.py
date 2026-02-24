from tradingagents.db.document import get_stock_daily_technical, get_company_name


def prompt_market_analyst(
    ticker: str,
    language: str,
    start_date: str = "2025-01-01",
    end_date: str = "2025-10-01"
) -> str:
    """
    生成股票技术分析Prompt
    
    参数:
        ticker (str): 股票代码
        language (str): 语言代码(zh-CN/其他)
        start_date (str): 数据开始日期,格式YYYY-MM-DD
        end_date (str): 数据结束日期,格式YYYY-MM-DD
    
    返回:
        str: LLM分析Prompt
    """
    try:
        result_str, result_data = get_stock_daily_technical(symbol=ticker, start_date=start_date, end_date=end_date)
        if result_data == "数据不可用" or result_data is None:
            result_str = "未获取到有效数据，请检查股票代码和数据源"
            result_data = {}
    except Exception as e:
        result_str = f"技术分析工具调用失败({type(e).__name__}): {e}"
        result_data = {}

    if language == "zh-CN":
        language_name = "中文"
        market_name = 'A股'
        currency_symbol = '元'
        currency_name = '元'
    else:
        language_name = "英文"
        market_name = '港股'
        currency_symbol = '港币'
        currency_name = '港币'

    close_data = result_data.get("close", [])
    data_price = close_data[-1] if isinstance(close_data, list) and len(close_data) > 0 else "数据不可用"
    company_name = get_company_name(ticker)

    analysis_prompt = f"""请基于以下技术数据，简要分析{company_name}（{ticker}）的走势：

**分析期间**: {start_date} 至 {end_date}
**当前价格**: {data_price} {currency_symbol}

{result_str[:3000] if len(result_str) > 3000 else result_str}

请提供以下分析：

## 一、技术面概况
- 主要技术指标状态（MA、MACD、RSI、BOLL等）
- 当前趋势判断（上涨、下跌、震荡）

## 二、支撑与压力
- 关键支撑位
- 关键压力位

## 三、操作建议
- 投资评级：买入、持有、卖出或观望
- 简要理由
- 风险提示

**要求**：
- 基于实际数据，简洁分析
- 使用{language_name}撰写
- Markdown格式输出"""

    return analysis_prompt
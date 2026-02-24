from datetime import datetime, timedelta


# 导入数据库函数
from tradingagents.db.document import get_company_name, get_stock_news


def prompt_news_analyst(
    ticker: str,
    language: str,
    current_date: str | None = None,
    days_back: int = 180
) -> str:
    """
    生成新闻分析Prompt
    
    参数:
        ticker (str): 股票代码
        language (str): 语言代码(zh-CN/其他)
        current_date (str): 结束日期,格式YYYY-MM-DD,默认为今天
        days_back (int): 回溯天数,默认180天
    
    返回:
        str: LLM分析Prompt
    """
    if current_date is None:
        end_date = datetime.now()
    else:
        end_date = datetime.strptime(current_date, "%Y-%m-%d")

    if language == "zh-CN":
        language_name = "中文"
    else:
        language_name = "英文"

    company_name = get_company_name(ticker)

    start_date = end_date - timedelta(days=days_back)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    try:
        symbol = 'code.' + ticker.split('.')[0]
        news_data = get_stock_news(symbol, start_date_str, end_date_str)
        
        if news_data and len(news_data) > 0:
            news_str = f"找到 {len(news_data)} 条关于 {company_name}（{ticker}）的新闻:\n\n"
            for i, news in enumerate(news_data[:10], 1):
                title = news.get('event_type', '无标题')
                date = news.get('trade_date', '')
                source = news.get('source', '未知来源')
                content = news.get('event_detail', '')
                news_str += f"{i}. {title}\n"
                news_str += f"   日期: {date}, 来源: {source}\n"
                if content:
                    news_str += f"   内容: {content[:200]}...\n"
                news_str += "\n"
        else:
            news_str = f"未找到 {company_name}（{ticker}）在最近{days_back}天的新闻数据。"
    except Exception as e:
        news_str = f"获取新闻数据失败({type(e).__name__}): {e}"


    analysis_prompt = f"""请基于以下新闻数据，对 {company_name}（{ticker}）进行简要分析：

**新闻期间**: {start_date_str} 至 {end_date_str}

{news_str[:3000] if len(news_str) > 3000 else news_str}

请提供以下分析：

## 一、主要新闻要点
列出2-3条最重要的新闻，简要说明核心内容。

## 二、市场影响评估
- 整体影响是利好、利空还是中性
- 对股价可能的影响（短期1-3天）
- 对投资者情绪的影响

## 三、投资建议
- 操作建议：买入、持有、卖出或观望
- 主要风险提示

**要求**：
- 基于实际数据，引用关键信息
- 简洁明了，避免过度分析
- 使用{language_name}撰写
- 使用Markdown格式输出"""

    return analysis_prompt

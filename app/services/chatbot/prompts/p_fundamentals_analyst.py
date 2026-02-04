# 强制调用统一基本面分析工具
from tradingagents.db.document import get_stock_daily_basic, get_company_name


def prompt_fundamentals_analyst(
    ticker: str,
    start_date: str = "2025-01-01",
    end_date: str = "2025-10-31"
) -> str:
    """
    生成股票基本面分析Prompt
    
    参数:
        ticker (str): 股票代码
        start_date (str): 数据开始日期,格式YYYY-MM-DD
        end_date (str): 数据结束日期,格式YYYY-MM-DD
    
    返回:
        str: LLM分析Prompt
    """
    try:
        combined_data = get_stock_daily_basic(ticker, start_date, end_date)
        if not combined_data or combined_data == "数据不可用":
            combined_data = "未获取到有效数据，请检查股票代码和数据源"
    except Exception as e:
        combined_data = f"统一基本面分析工具调用失败({type(e).__name__}): {e}"

    company_name = get_company_name(ticker)
    language_name = "中文"
    currency_info = "元"

    analysis_prompt = f"""请基于以下财务数据，简要分析{company_name}（{ticker}）的基本面：

**数据期间**: {start_date} 至 {end_date}
**当前价格单位**: {currency_info}

{combined_data}

请提供以下分析：

## 一、公司概况
- 主营业务与行业地位
- 核心竞争优势

## 二、财务状况
- 盈利能力（营收、净利润、毛利率等）
- 估值水平（PE、PB等）
- 财务健康度（资产负债情况）

## 三、投资建议
- 投资评级：买入、持有或卖出
- 主要理由
- 风险提示

**要求**：
- 基于实际数据，简洁分析
- 引用关键财务指标
- 使用{language_name}撰写
- Markdown格式输出"""


    return analysis_prompt
from datetime import datetime, timedelta
import traceback

from langchain_core.messages import HumanMessage, AIMessage

# 导入统一日志系统和分析模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module

# 导入数据库函数
from tradingagents.db.document import get_company_name, get_stock_news

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入股票代码统一处理函数
from tradingagents.utils.stock_utils import unified_code


def create_news_analyst(llm, toolkit):
    llm = llm.get_llm()
    def news_analyst_node(state):
        logger.debug(f"📈 [DEBUG] ===== 新闻分析师节点开始 =====")

        # 🔧 工具调用计数器 - 防止无限循环
        tool_call_count = state.get("news_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"🔧 [死循环修复] 当前工具调用次数: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        ticker = unified_code(ticker)
        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📈 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")

        # 获取公司名称
        company_name = get_company_name(ticker)
        logger.debug(f"📈 [DEBUG] 公司名称: {ticker} -> {company_name}")

        # 计算日期范围（获取最近30天的新闻）
        end_date = datetime.strptime(current_date, "%Y-%m-%d")
        start_date = end_date - timedelta(days=30)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # 从数据库获取新闻数据
        logger.debug(f"📈 [DEBUG] 获取新闻数据: {ticker}, {start_date_str} to {end_date_str}")
        news_data = get_stock_news(ticker, start_date_str, end_date_str)
        logger.debug(f"📈 [DEBUG] 获取到 {len(news_data)} 条新闻")

        # 将新闻数据格式化为字符串
        if news_data:
            news_str = f"找到 {len(news_data)} 条关于 {company_name}（{ticker}）的新闻:\n\n"
            for i, news in enumerate(news_data[:10], 1):
                title = news.get('title', '无标题')
                date = news.get('date', '')
                source = news.get('source', '未知来源')
                content = news.get('content', '')
                news_str += f"{i}. {title}\n"
                news_str += f"   日期: {date}, 来源: {source}\n"
                if content:
                    news_str += f"   内容: {content[:200]}...\n"
                news_str += "\n"
        else:
            news_str = f"未找到 {company_name}（{ticker}）在最近30天的新闻数据。"

        logger.debug(f"📈 [DEBUG] 新闻数据字符串长度: {len(news_str)}")

        # 构建分析提示词
        analysis_prompt = f"""请基于以下获取的新闻数据，对 {company_name}（{ticker}）进行详细的新闻分析：

=== 新闻数据 ===
{news_str[:4000]}

=== 分析要求 ===

您是一位专业的财经新闻分析师，负责分析最新的市场新闻和事件对股票价格的潜在影响。

您的主要职责包括：
1. 获取和分析最新的实时新闻（优先15-30分钟内的新闻）
2. 评估新闻事件的紧急程度和市场影响
3. 识别可能影响股价的关键信息
4. 分析新闻的时效性和可靠性
5. 提供基于新闻的交易建议和价格影响评估

重点关注的新闻类型：
- 财报发布和业绩指导
- 重大合作和并购消息
- 政策变化和监管动态
- 突发事件和危机管理
- 行业趋势和技术突破
- 管理层变动和战略调整

分析要点：
- 新闻的时效性（发布时间距离现在多久）
- 新闻的可信度（来源权威性）
- 市场影响程度（对股价的潜在影响）
- 投资者情绪变化（正面/负面/中性）
- 与历史类似事件的对比

新闻影响分析要求：
- 评估新闻对股价的短期影响（1-3天）和市场情绪变化
- 分析新闻的利好/利空程度和可能的市场反应
- 评估新闻对公司基本面和长期投资价值的影响
- 识别新闻中的关键信息点和潜在风险
- 对比历史类似事件的市场反应
- 不允许回复'无法评估影响'或'需要更多信息'

请特别注意：
⚠️ 如果新闻数据存在滞后（超过2小时），请在分析中明确说明时效性限制
✅ 优先分析最新的、高相关性的新闻事件
📊 提供新闻对市场情绪和投资者信心的影响评估
💰 必须包含基于新闻的市场反应预期和投资建议
🎯 聚焦新闻内容本身的解读，不涉及技术指标分析

输出格式要求：
1. 必须包含详细的中文分析报告
2. 报告末尾附上Markdown表格总结关键发现
3. 报告长度不少于800字
4. 提供明确的投资建议和风险提示
5. 使用标准的Markdown标题格式（#、##、###）
"""

        # 构建完整的消息序列
        messages = state["messages"] + [HumanMessage(content=analysis_prompt[:8000])]

        # 生成最终分析报告
        logger.debug(f"📈 [DEBUG] 开始调用LLM生成新闻分析")
        final_result = llm.invoke(messages)
        report = final_result.content

        logger.info(f"📊 [新闻分析师] 生成完整分析报告，长度: {len(report)}")

        # 返回包含最终分析的完整消息序列
        # 🔧 更新工具调用计数器
        return {
            "messages": [final_result],
            "news_report": report,
            "news_tool_call_count": tool_call_count + 1
        }

    return news_analyst_node

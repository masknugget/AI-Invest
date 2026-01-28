from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
import traceback

from tradingagents.db.document import get_company_name, get_stock_daily_technical
from tradingagents.utils.stock_utils import unified_code
# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler



def create_market_analyst(llm_model, toolkit):

    def market_analyst_node(state):
        logger.debug(f"📈 [DEBUG] ===== 市场分析师节点开始 =====")
        llm = llm_model.get_llm()
        # 🔧 工具调用计数器 - 防止无限循环
        tool_call_count = state.get("market_tool_call_count", 0)
        max_tool_calls = 3  # 最大工具调用次数
        logger.info(f"🔧 [死循环修复] 当前工具调用次数: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        ticker = unified_code(ticker)
        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📈 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📈 [DEBUG] 现有市场报告: {state.get('market_report', 'None')}")

        # 根据股票代码格式选择数据源
        from tradingagents.utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(ticker)

        logger.debug(f"📈 [DEBUG] 股票类型检查: {ticker} -> {market_info['market_name']} ({market_info['currency_name']})")

        # 获取公司名称
        company_name = get_company_name(ticker)
        logger.debug(f"📈 [DEBUG] 公司名称: {ticker} -> {company_name}")

        result_str, result_data = get_stock_daily_technical(symbol=ticker, start_date='2025-01-01', end_date='2025-10-01')

        data_price = result_data.get("close")[-1]

        language = state.get("language", "en-US")

        if language == "zh-CN":
            language = "中文"
        else:
            language = "英文"

        # try:
        # 基于工具结果生成完整分析报告
        # 🔥 重要：这里必须包含公司名称和输出格式要求，确保LLM生成正确的报告标题
        analysis_prompt = f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。
        **分析对象：**
        - 公司名称：{company_name}
        - 股票代码：{ticker}
        - 所属市场：{market_info['market_name']}
        - 计价货币：{market_info['currency_name']}（{market_info['currency_symbol']}）
        
        **输出格式要求（必须严格遵守）：**
        
        请按照以下专业格式输出报告，不要使用emoji符号（如📊📈📉💭等），使用纯文本标题：
        
        # **{company_name}（{ticker}）技术分析报告**
        **分析日期：[当前日期]**
        
        ---
        
        ## 一、股票基本信息
        
        - **公司名称**：{company_name}
        - **股票代码**：{ticker}
        - **所属市场**：{market_info['market_name']}
        - **当前价格**：{data_price} {market_info['currency_symbol']}        
        ---
        
        ## 二、技术指标分析
        参考技术指标数据
        
        ### 1. 移动平均线（MA）分析
        
        [分析MA5、MA10、MA20、MA60等均线系统，包括：]
        - 当前各均线数值
        - 均线排列形态（多头/空头）
        - 价格与均线的位置关系
        - 均线交叉信号
        
        ### 2. MACD指标分析
        
        [分析MACD指标，包括：]
        - DIF、DEA、MACD柱状图当前数值
        - 金叉/死叉信号
        - 背离现象
        - 趋势强度判断
        
        ### 3. RSI相对强弱指标
        
        [分析RSI指标，包括：]
        - RSI当前数值
        - 超买/超卖区域判断
        - 背离信号
        - 趋势确认
        
        ### 4. 布林带（BOLL）分析
        
        [分析布林带指标，包括：]
        - 上轨、中轨、下轨数值
        - 价格在布林带中的位置
        - 带宽变化趋势
        - 突破信号
        
        ---
        
        ## 三、价格趋势分析
        
        ### 1. 短期趋势（5-10个交易日）
        
        [分析短期价格走势，包括支撑位、压力位、关键价格区间]
        
        ### 2. 中期趋势（20-60个交易日）
        
        [分析中期价格走势，结合均线系统判断趋势方向]
        
        ### 3. 成交量分析
        
        [分析成交量变化，量价配合情况]
        
        ---
        
        ## 四、投资建议
        
        ### 1. 综合评估
        
        [基于上述技术指标，给出综合评估]
        
        ### 2. 操作建议
        
        - **投资评级**：买入/持有/卖出
        - **目标价位**：[给出具体价格区间] {market_info['currency_symbol']}
        - **止损位**：[给出止损价格] {market_info['currency_symbol']}
        - **风险提示**：[列出主要风险因素]
        
        ### 3. 关键价格区间
        
        - **支撑位**：[具体价格]
        - **压力位**：[具体价格]
        - **突破买入价**：[具体价格]
        - **跌破卖出价**：[具体价格]
        
        ---
        
        **重要提醒：**
        - 必须严格按照上述格式输出，使用标准的Markdown标题（#、##、###）
        - 不要使用emoji符号（📊📈📉💭等）
        - 所有价格数据使用{market_info['currency_name']}（{market_info['currency_symbol']}）表示
        - 确保在分析中正确使用公司名称"{company_name}"和股票代码"{ticker}"
        - 报告标题必须是：# **{company_name}（{ticker}）技术分析报告**
        - 报告必须基于工具返回的真实数据进行分析
        - 包含具体的技术指标数值和专业分析
        - 提供明确的投资建议和风险提示
        - 报告长度不少于800字
        - 使用{language}撰写,全部使用{language}
        - 使用表格展示数据时，确保格式规范"""


        # 构建完整的消息序列
        messages = state["messages"] + [HumanMessage(content=result_str[:5000])] + [HumanMessage(content=analysis_prompt)]


        # 生成最终分析报告
        final_result = llm.invoke(messages)
        report = final_result.content

        logger.info(f"📊 [市场分析师] 生成完整分析报告，长度: {len(report)}")

        # 返回包含工具调用和最终分析的完整消息序列
        # 🔧 更新工具调用计数器
        return {
            "messages": [final_result],
            "market_report": report,
            "market_tool_call_count": tool_call_count + 1
        }

        # except Exception as e:
        #     logger.error(f"❌ [市场分析师] 工具执行或分析生成失败: {e}")
        #     traceback.print_exc()
        #
        #
        #     # 🔧 更新工具调用计数器
        #     return {
        #         "messages": [result],
        #         "market_report": report,
        #         "market_tool_call_count": tool_call_count + 1
        #     }

    return market_analyst_node

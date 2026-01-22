"""
基本面分析师 - 统一工具架构版本
使用统一工具自动识别股票类型并调用相应数据源
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.db.document import get_company_name, get_stock_daily_basic
from tradingagents.utils.stock_utils import unified_code
# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler



def create_fundamentals_analyst(llm, toolkit):
    @log_analyst_module("fundamentals")
    def fundamentals_analyst_node(state):
        logger.debug(f"📊 [DEBUG] ===== 基本面分析师节点开始 =====")

        # 🔧 工具调用计数器 - 防止无限循环
        # 检查消息历史中是否有 ToolMessage，如果有则说明工具已执行过
        messages = state.get("messages", [])
        tool_message_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        ticker = unified_code(ticker)
        # 🔧 基本面分析数据范围：固定获取10天数据（处理周末/节假日/数据延迟）
        # 参考文档：docs/ANALYST_DATA_CONFIGURATION.md
        # 基本面分析主要依赖财务数据（PE、PB、ROE等），只需要当前股价
        # 获取10天数据是为了保证能拿到数据，但实际分析只使用最近2天
        from datetime import datetime, timedelta
        try:
            end_date_dt = datetime.strptime(current_date, "%Y-%m-%d")
            start_date_dt = end_date_dt - timedelta(days=10)
            start_date = start_date_dt.strftime("%Y-%m-%d")
            logger.info(f"📅 [基本面分析师] 数据范围: {start_date} 至 {current_date} (固定10天)")
        except Exception as e:
            # 如果日期解析失败，使用默认10天前
            logger.warning(f"⚠️ [基本面分析师] 日期解析失败，使用默认范围: {e}")
            start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

        logger.debug(f"📊 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📊 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📊 [DEBUG] 现有基本面报告: {state.get('fundamentals_report', 'None')}")

        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        logger.info(f"📊 [基本面分析师] 正在分析股票: {ticker}")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] 基本面分析师接收到的原始股票代码: '{ticker}' (类型: {type(ticker)})")

        market_info = StockUtils.get_market_info(ticker)
        logger.info(f"🔍 [股票代码追踪] StockUtils.get_market_info 返回的市场信息: {market_info}")

        # 获取公司名称
        company_name = get_company_name(ticker)
        logger.debug(f"📊 [DEBUG] 公司名称: {ticker} -> {company_name}")

        # 统一使用 get_stock_fundamentals_unified 工具
        # 该工具内部会自动识别股票类型（A股/港股/美股）并调用相应的数据源
        # 对于A股，它会自动获取价格数据和基本面数据，无需LLM调用多个工具
        logger.info(f"📊 [基本面分析师] 使用统一基本面分析工具，自动识别股票类型")

        # 检测阿里百炼模型并创建新实例
        if hasattr(llm, '__class__') and 'DashScope' in llm.__class__.__name__:
            logger.debug(f"📊 [DEBUG] 检测到阿里百炼模型，创建新实例以避免工具缓存")
            from tradingagents.llm_adapters import ChatDashScopeOpenAI

            # 获取原始 LLM 的 base_url 和 api_key
            original_base_url = getattr(llm, 'openai_api_base', None)
            original_api_key = getattr(llm, 'openai_api_key', None)

            fresh_llm = ChatDashScopeOpenAI(
                model=llm.model_name,
                api_key=original_api_key,  # 🔥 传递原始 LLM 的 API Key
                base_url=original_base_url if original_base_url else None,  # 传递 base_url
                temperature=llm.temperature,
                max_tokens=getattr(llm, 'max_tokens', 2000)
            )

            if original_base_url:
                logger.debug(f"📊 [DEBUG] 新实例使用原始 base_url: {original_base_url}")
            if original_api_key:
                logger.debug(f"📊 [DEBUG] 新实例使用原始 API Key（来自数据库配置）")
        else:
            fresh_llm = llm

        # 添加详细日志
        logger.info(f"📊 [基本面分析师] LLM类型: {fresh_llm.__class__.__name__}")
        logger.info(f"📊 [基本面分析师] LLM模型: {getattr(fresh_llm, 'model_name', 'unknown')}")
        logger.info(f"📊 [基本面分析师] 消息历史数量: {len(state['messages'])}")


        # 2. 打印完整的提示模板
        logger.info("📋 [提示词调试] 2️⃣ 完整提示模板 (Prompt Template):")
        logger.info("-" * 80)
        logger.info(f"当前日期: {current_date}")
        logger.info(f"股票代码: {ticker}")
        logger.info(f"公司名称: {company_name}")
        logger.info("-" * 80)

        # 没有工具调用，检查是否需要强制调用工具
        logger.info(f"📊 [基本面分析师] ===== 强制工具调用检查开始 =====")
        logger.debug(f"📊 [DEBUG] 检测到模型未调用工具，检查是否需要强制调用")

        # 方案1：检查消息历史中是否已经有工具返回的数据
        messages = state.get("messages", [])
        logger.info(f"🔍 [消息历史] 当前消息总数: {len(messages)}")

        # 统计各类消息数量
        ai_message_count = sum(1 for msg in messages if isinstance(msg, AIMessage))
        tool_message_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))
        logger.info(f"🔍 [消息历史] AIMessage数量: {ai_message_count}, ToolMessage数量: {tool_message_count}")

        # 记录最近几条消息的类型
        recent_messages = messages[-5:] if len(messages) >= 5 else messages
        logger.info(
            f"🔍 [消息历史] 最近{len(recent_messages)}条消息类型: {[type(msg).__name__ for msg in recent_messages]}")

        has_tool_result = any(isinstance(msg, ToolMessage) for msg in messages)
        logger.info(f"🔍 [检查结果] 是否有工具返回结果: {has_tool_result}")

        # 强制调用统一基本面分析工具
        try:
            logger.debug(f"📊 [DEBUG] 强制调用 get_stock_fundamentals_unified...")
            combined_data = get_stock_daily_basic(ticker, "2025-07-01", "2025-10-31")
        except Exception as e:
            combined_data = f"统一基本面分析工具调用失败: {e}"
            logger.debug(f"📊 [DEBUG] 统一工具调用异常: {e}")

        currency_info = f"{market_info['currency_name']}（{market_info['currency_symbol']}）"

        # 生成基于真实数据的分析报告
        analysis_prompt = f"""基于以下真实数据，对{company_name}（股票代码：{ticker}）进行详细的基本面分析：
        
        {combined_data}
        
        请提供：
        1. 公司基本信息分析（{company_name}，股票代码：{ticker}）
        2. 财务状况评估
        3. 盈利能力分析
        4. 估值分析（使用{currency_info}）
        5. 投资建议（买入/持有/卖出）
        
        要求：
        - 基于提供的真实数据进行分析
        - 正确使用公司名称"{company_name}"和股票代码"{ticker}"
        - 价格使用{currency_info}
        - 投资建议使用中文
        - 分析要详细且专业"""

        try:
            # 创建简单的分析链
            analysis_prompt_template = ChatPromptTemplate.from_messages([
                ("system", "你是专业的股票基本面分析师，基于提供的真实数据进行分析。"),
                ("human", "{analysis_request}")
            ])

            analysis_chain = analysis_prompt_template | fresh_llm
            analysis_result = analysis_chain.invoke({"analysis_request": analysis_prompt})

            if hasattr(analysis_result, 'content'):
                report = analysis_result.content
            else:
                report = str(analysis_result)

            logger.info(f"📊 [基本面分析师] 强制工具调用完成，报告长度: {len(report)}")

        except Exception as e:
            logger.error(f"❌ [DEBUG] 强制工具调用分析失败: {e}")
            report = f"基本面分析失败：{str(e)}"

        # 🔧 保持工具调用计数器不变（已在开始时根据ToolMessage更新）
        return {
            "fundamentals_report": report,
            "fundamentals_tool_call_count": 0
        }

    return fundamentals_analyst_node

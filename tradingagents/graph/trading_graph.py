# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional
import time

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI


from langgraph.prebuilt import ToolNode

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import FinancialSituationMemory

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
from ..llm_adapters.internal_adapter import InternalLLM

logger = get_logger('agents')
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.interface import set_config

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs
        # 🔧 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
        quick_config = self.config.get("quick_model_config", {})
        deep_config = self.config.get("deep_model_config", {})

        # 读取快速模型参数
        quick_max_tokens = quick_config.get("max_tokens", 4000)
        quick_temperature = quick_config.get("temperature", 0.7)
        quick_timeout = quick_config.get("timeout", 180)

        # 读取深度模型参数
        deep_max_tokens = deep_config.get("max_tokens", 4000)
        deep_temperature = deep_config.get("temperature", 0.7)
        deep_timeout = deep_config.get("timeout", 180)

        # 🔧 检查是否为混合模式（快速模型和深度模型来自不同厂家）
        quick_provider = self.config.get("quick_provider")
        deep_provider = self.config.get("deep_provider")
        quick_backend_url = self.config.get("quick_backend_url")
        deep_backend_url = self.config.get("deep_backend_url")

        # 使用统一的函数创建 LLM 实例
        self.quick_thinking_llm = InternalLLM()

        self.deep_thinking_llm = InternalLLM()
        
        self.toolkit = Toolkit(config=self.config)

        # Initialize memories (如果启用)
        memory_enabled = self.config.get("memory_enabled", True)
        if memory_enabled:
            # 使用单例ChromaDB管理器，避免并发创建冲突
            self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
            self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
            self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
            self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
            self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)
        else:
            # 创建空的内存对象
            self.bull_memory = None
            self.bear_memory = None
            self.trader_memory = None
            self.invest_judge_memory = None
            self.risk_manager_memory = None

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        # 🔥 [修复] 从配置中读取辩论轮次参数
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1)
        )
        logger.info(f"🔧 [ConditionalLogic] 初始化完成:")
        logger.info(f"   - max_debate_rounds: {self.conditional_logic.max_debate_rounds}")
        logger.info(f"   - max_risk_discuss_rounds: {self.conditional_logic.max_risk_discuss_rounds}")

        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.toolkit,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
            self.config,
            getattr(self, 'react_llm', None),
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources.

        注意：ToolNode 包含所有可能的工具，但 LLM 只会调用它绑定的工具。
        ToolNode 的作用是执行 LLM 生成的 tool_calls，而不是限制 LLM 可以调用哪些工具。
        """
        return {
            "market": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_market_data_unified,
                ]
            ),
            "social": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_sentiment_unified,

                ]
            ),
            "news": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_news_unified,

                ]
            ),
            "fundamentals": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_fundamentals_unified,
                ]
            ),
        }

    def propagate(self, company_name, trade_date, language="zh-CN", progress_callback=None, task_id=None):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name: Company name or stock symbol
            trade_date: Date for analysis
            progress_callback: Optional callback function for progress updates
            language: Optional callback function for progress updates
            task_id: Optional task ID for tracking performance data
        """

        # 添加详细的接收日志
        self.ticker = company_name
        logger.debug(f"🔍 [GRAPH DEBUG] 设置self.ticker: '{self.ticker}'")

        # Initialize state
        logger.debug(f"🔍 [GRAPH DEBUG] 创建初始状态，传递参数: company_name='{company_name}', trade_date='{trade_date}'")
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, language
        )
        logger.debug(f"🔍 [GRAPH DEBUG] 初始状态中的company_of_interest: '{init_agent_state.get('company_of_interest', 'NOT_FOUND')}'")
        logger.debug(f"🔍 [GRAPH DEBUG] 初始状态中的trade_date: '{init_agent_state.get('trade_date', 'NOT_FOUND')}'")

        # 初始化计时器
        node_timings = {}  # 记录每个节点的执行时间
        total_start_time = time.time()  # 总体开始时间
        current_node_start = None  # 当前节点开始时间
        current_node_name = None  # 当前节点名称

        # 保存task_id用于后续保存性能数据
        self._current_task_id = task_id

        # 根据是否有进度回调选择不同的stream_mode
        args = self.propagator.get_graph_args(use_progress_callback=bool(progress_callback))


        # Standard mode without tracing but with progress updates
        if progress_callback:
            # 使用 updates 模式以便获取节点级别的进度
            trace = []
            final_state = None
            for chunk in self.graph.stream(init_agent_state, **args):
                # 记录节点计时
                for node_name in chunk.keys():
                    if not node_name.startswith('__'):
                        # 如果有上一个节点，记录其结束时间
                        if current_node_name and current_node_start:
                            elapsed = time.time() - current_node_start
                            node_timings[current_node_name] = elapsed
                            logger.info(f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒")
                            logger.info(f"🔍 [TIMING] 节点切换: {current_node_name} → {node_name}")

                        # 开始新节点计时
                        current_node_name = node_name
                        current_node_start = time.time()
                        logger.info(f"🔍 [TIMING] 开始计时: {node_name}")
                        break

                self._send_progress_update(chunk, progress_callback)
                # 累积状态更新
                if final_state is None:
                    final_state = init_agent_state.copy()
                for node_name, node_update in chunk.items():
                    if not node_name.startswith('__'):
                        final_state.update(node_update)
        else:
            # 原有的invoke模式（也需要计时）
            logger.info("⏱️ 使用 invoke 模式执行分析（无进度回调）")
            # 使用stream模式以便计时，但不发送进度更新
            trace = []
            final_state = None
            for chunk in self.graph.stream(init_agent_state, **args):
                # 记录节点计时
                for node_name in chunk.keys():
                    if not node_name.startswith('__'):
                        # 如果有上一个节点，记录其结束时间
                        if current_node_name and current_node_start:
                            elapsed = time.time() - current_node_start
                            node_timings[current_node_name] = elapsed
                            logger.info(f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒")

                        # 开始新节点计时
                        current_node_name = node_name
                        current_node_start = time.time()
                        break

                # 累积状态更新
                if final_state is None:
                    final_state = init_agent_state.copy()
                for node_name, node_update in chunk.items():
                    if not node_name.startswith('__'):
                        final_state.update({node_name: node_update})

        # 记录最后一个节点的时间
        if current_node_name and current_node_start:
            elapsed = time.time() - current_node_start
            node_timings[current_node_name] = elapsed
            logger.info(f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒")

        # 计算总时间
        # total_elapsed = time.time() - total_start_time
        #
        # # 调试日志
        # logger.info(f"🔍 [TIMING DEBUG] 节点计时数量: {len(node_timings)}")
        # logger.info(f"🔍 [TIMING DEBUG] 总耗时: {total_elapsed:.2f}秒")
        # logger.info(f"🔍 [TIMING DEBUG] 节点列表: {list(node_timings.keys())}")
        #
        # # 打印详细的时间统计
        # logger.info("🔍 [TIMING DEBUG] 准备调用 _print_timing_summary")
        # self._print_timing_summary(node_timings, total_elapsed)
        # logger.info("🔍 [TIMING DEBUG] _print_timing_summary 调用完成")
        #
        # # 构建性能数据
        # performance_data = self._build_performance_data(node_timings, total_elapsed)
        #
        # # 将性能数据添加到状态中
        # final_state['performance_metrics'] = performance_data
        #
        # # Store current state for reflection
        # self.curr_state = final_state
        #
        # # Log state
        # # self._log_state(trade_date, final_state)
        #
        # # 获取模型信息
        # model_info = ""
        # try:
        #     if hasattr(self.deep_thinking_llm, 'model_name'):
        #         model_info = f"{self.deep_thinking_llm.__class__.__name__}:{self.deep_thinking_llm.model_name}"
        #     else:
        #         model_info = self.deep_thinking_llm.__class__.__name__
        # except Exception:
        #     model_info = "Unknown"
        #
        # # 处理决策并添加模型信息
        decision = self.process_signal(final_state["final_trade_decision"], company_name, language)
        # decision['model_info'] = model_info

        # Return decision and processed signal
        # return final_state, decision
        if isinstance(final_state, dict):
            if 'investment_debate_state' in final_state:
                del final_state['investment_debate_state']
            if 'risk_debate_state' in final_state:
                del final_state['risk_debate_state']
        return final_state, decision

    def _send_progress_update(self, chunk, progress_callback):
        """发送进度更新到回调函数

        LangGraph stream 返回的 chunk 格式：{node_name: {...}}
        节点名称示例：
        - "Market Analyst", "Fundamentals Analyst", "News Analyst", "Social Analyst"
        - "tools_market", "tools_fundamentals", "tools_news", "tools_social"
        - "Msg Clear Market", "Msg Clear Fundamentals", etc.
        - "Bull Researcher", "Bear Researcher", "Research Manager"
        - "Trader"
        - "Risky Analyst", "Safe Analyst", "Neutral Analyst", "Risk Judge"
        """
        try:
            # 从chunk中提取当前执行的节点信息
            if not isinstance(chunk, dict):
                return

            # 获取第一个非特殊键作为节点名
            node_name = None
            for key in chunk.keys():
                if not key.startswith('__'):
                    node_name = key
                    break

            if not node_name:
                return

            logger.info(f"🔍 [Progress] 节点名称: {node_name}")

            # 检查是否为结束节点
            if '__end__' in chunk:
                logger.info(f"📊 [Progress] 检测到__end__节点")
                progress_callback("📊 生成报告")
                return

            # 节点名称映射表（匹配 LangGraph 实际节点名）
            node_mapping = {
                # 分析师节点
                'Market Analyst': "📊 市场分析师",
                'Fundamentals Analyst': "💼 基本面分析师",
                'News Analyst': "📰 新闻分析师",
                'Social Analyst': "💬 社交媒体分析师",
                # 工具节点（不发送进度更新，避免重复）
                'tools_market': None,
                'tools_fundamentals': None,
                'tools_news': None,
                'tools_social': None,
                # 消息清理节点（不发送进度更新）
                'Msg Clear Market': None,
                'Msg Clear Fundamentals': None,
                'Msg Clear News': None,
                'Msg Clear Social': None,
                # 研究员节点
                'Bull Researcher': "🐂 看涨研究员",
                'Bear Researcher': "🐻 看跌研究员",
                'Research Manager': "👔 研究经理",
                # 交易员节点
                'Trader': "💼 交易员决策",
                # 风险评估节点
                'Risky Analyst': "🔥 激进风险评估",
                'Safe Analyst': "🛡️ 保守风险评估",
                'Neutral Analyst': "⚖️ 中性风险评估",
                'Risk Judge': "🎯 风险经理",
            }

            # 查找映射的消息
            message = node_mapping.get(node_name)

            if message is None:
                # None 表示跳过（工具节点、消息清理节点）
                logger.debug(f"⏭️ [Progress] 跳过节点: {node_name}")
                return

            if message:
                # 发送进度更新
                logger.info(f"📤 [Progress] 发送进度更新: {message}")
                progress_callback(message)
            else:
                # 未知节点，使用节点名称
                logger.warning(f"⚠️ [Progress] 未知节点: {node_name}")
                progress_callback(f"🔍 {node_name}")

        except Exception as e:
            logger.error(f"❌ 进度更新失败: {e}", exc_info=True)

    def _build_performance_data(self, node_timings: Dict[str, float], total_elapsed: float) -> Dict[str, Any]:
        """构建性能数据结构

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间

        Returns:
            性能数据字典
        """
        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = {}
        tool_nodes = {}
        msg_clear_nodes = {}
        research_nodes = {}
        trader_nodes = {}
        risk_nodes = {}
        other_nodes = {}

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if 'Risky' in node_name or 'Safe' in node_name or 'Neutral' in node_name or 'Risk Judge' in node_name:
                risk_nodes[node_name] = elapsed
            # 然后匹配分析师团队
            elif 'Analyst' in node_name:
                analyst_nodes[node_name] = elapsed
            # 工具节点
            elif node_name.startswith('tools_'):
                tool_nodes[node_name] = elapsed
            # 消息清理节点
            elif node_name.startswith('Msg Clear'):
                msg_clear_nodes[node_name] = elapsed
            # 研究团队
            elif 'Researcher' in node_name or 'Research Manager' in node_name:
                research_nodes[node_name] = elapsed
            # 交易团队
            elif 'Trader' in node_name:
                trader_nodes[node_name] = elapsed
            # 其他节点
            else:
                other_nodes[node_name] = elapsed

        # 计算统计数据
        slowest_node = max(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        fastest_node = min(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        avg_time = sum(node_timings.values()) / len(node_timings) if node_timings else 0

        return {
            "total_time": round(total_elapsed, 2),
            "total_time_minutes": round(total_elapsed / 60, 2),
            "node_count": len(node_timings),
            "average_node_time": round(avg_time, 2),
            "slowest_node": {
                "name": slowest_node[0],
                "time": round(slowest_node[1], 2)
            } if slowest_node[0] else None,
            "fastest_node": {
                "name": fastest_node[0],
                "time": round(fastest_node[1], 2)
            } if fastest_node[0] else None,
            "node_timings": {k: round(v, 2) for k, v in node_timings.items()},
            "category_timings": {
                "analyst_team": {
                    "nodes": {k: round(v, 2) for k, v in analyst_nodes.items()},
                    "total": round(sum(analyst_nodes.values()), 2),
                    "percentage": round(sum(analyst_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "tool_calls": {
                    "nodes": {k: round(v, 2) for k, v in tool_nodes.items()},
                    "total": round(sum(tool_nodes.values()), 2),
                    "percentage": round(sum(tool_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "message_clearing": {
                    "nodes": {k: round(v, 2) for k, v in msg_clear_nodes.items()},
                    "total": round(sum(msg_clear_nodes.values()), 2),
                    "percentage": round(sum(msg_clear_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "research_team": {
                    "nodes": {k: round(v, 2) for k, v in research_nodes.items()},
                    "total": round(sum(research_nodes.values()), 2),
                    "percentage": round(sum(research_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "trader_team": {
                    "nodes": {k: round(v, 2) for k, v in trader_nodes.items()},
                    "total": round(sum(trader_nodes.values()), 2),
                    "percentage": round(sum(trader_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "risk_management_team": {
                    "nodes": {k: round(v, 2) for k, v in risk_nodes.items()},
                    "total": round(sum(risk_nodes.values()), 2),
                    "percentage": round(sum(risk_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                },
                "other": {
                    "nodes": {k: round(v, 2) for k, v in other_nodes.items()},
                    "total": round(sum(other_nodes.values()), 2),
                    "percentage": round(sum(other_nodes.values()) / total_elapsed * 100, 1) if total_elapsed > 0 else 0
                }
            },
            "llm_config": {
                "provider": self.config.get('llm_provider', 'unknown'),
                "deep_think_model": self.config.get('deep_think_llm', 'unknown'),
                "quick_think_model": self.config.get('quick_think_llm', 'unknown')
            }
        }

    def _print_timing_summary(self, node_timings: Dict[str, float], total_elapsed: float):
        """打印详细的时间统计报告

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间
        """
        logger.info("🔍 [_print_timing_summary] 方法被调用")
        logger.info("🔍 [_print_timing_summary] node_timings 数量: " + str(len(node_timings)))
        logger.info("🔍 [_print_timing_summary] total_elapsed: " + str(total_elapsed))

        logger.info("=" * 80)
        logger.info("⏱️  分析性能统计报告")
        logger.info("=" * 80)

        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = []
        tool_nodes = []
        msg_clear_nodes = []
        research_nodes = []
        trader_nodes = []
        risk_nodes = []
        other_nodes = []

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if 'Risky' in node_name or 'Safe' in node_name or 'Neutral' in node_name or 'Risk Judge' in node_name:
                risk_nodes.append((node_name, elapsed))
            # 然后匹配分析师团队
            elif 'Analyst' in node_name:
                analyst_nodes.append((node_name, elapsed))
            # 工具节点
            elif node_name.startswith('tools_'):
                tool_nodes.append((node_name, elapsed))
            # 消息清理节点
            elif node_name.startswith('Msg Clear'):
                msg_clear_nodes.append((node_name, elapsed))
            # 研究团队
            elif 'Researcher' in node_name or 'Research Manager' in node_name:
                research_nodes.append((node_name, elapsed))
            # 交易团队
            elif 'Trader' in node_name:
                trader_nodes.append((node_name, elapsed))
            # 其他节点
            else:
                other_nodes.append((node_name, elapsed))

        # 打印分类统计
        def print_category(title: str, nodes: List[Tuple[str, float]]):
            if not nodes:
                return
            logger.info(f"\n📊 {title}")
            logger.info("-" * 80)
            total_category_time = sum(t for _, t in nodes)
            for node_name, elapsed in sorted(nodes, key=lambda x: x[1], reverse=True):
                percentage = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
                logger.info(f"  • {node_name:40s} {elapsed:8.2f}秒  ({percentage:5.1f}%)")
            logger.info(f"  {'小计':40s} {total_category_time:8.2f}秒  ({total_category_time/total_elapsed*100:5.1f}%)")

        print_category("分析师团队", analyst_nodes)
        print_category("工具调用", tool_nodes)
        print_category("消息清理", msg_clear_nodes)
        print_category("研究团队", research_nodes)
        print_category("交易团队", trader_nodes)
        print_category("风险管理团队", risk_nodes)
        print_category("其他节点", other_nodes)

        # 打印总体统计
        logger.info("\n" + "=" * 80)
        logger.info(f"🎯 总执行时间: {total_elapsed:.2f}秒 ({total_elapsed/60:.2f}分钟)")
        logger.info(f"📈 节点总数: {len(node_timings)}")
        if node_timings:
            avg_time = sum(node_timings.values()) / len(node_timings)
            logger.info(f"⏱️  平均节点耗时: {avg_time:.2f}秒")
            slowest_node = max(node_timings.items(), key=lambda x: x[1])
            logger.info(f"🐌 最慢节点: {slowest_node[0]} ({slowest_node[1]:.2f}秒)")
            fastest_node = min(node_timings.items(), key=lambda x: x[1])
            logger.info(f"⚡ 最快节点: {fastest_node[0]} ({fastest_node[1]:.2f}秒)")

        # 打印LLM配置信息
        logger.info(f"\n🤖 LLM配置:")
        logger.info(f"  • 提供商: {self.config.get('llm_provider', 'unknown')}")
        logger.info(f"  • 深度思考模型: {self.config.get('deep_think_llm', 'unknown')}")
        logger.info(f"  • 快速思考模型: {self.config.get('quick_think_llm', 'unknown')}")
        logger.info("=" * 80)

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log.json",
            "w",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, self.risk_manager_memory
        )

    def process_signal(self, full_signal, stock_symbol=None, language='en-US'):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal, stock_symbol, language)

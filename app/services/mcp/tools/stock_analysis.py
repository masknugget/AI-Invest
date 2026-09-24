from typing import List

from app.services.chatbot.tools import analyze_stock_by_type


def analyze_stock(
        stock_code: str,
        analyze_type_list: List[str],
        language: str = "zh-CN"
) -> str:
    """
    MCP 工具封装：按指定维度生成股票分析用的 Prompt（基本面 / 技术面 / 新闻面）。

    设计目的
    --------
    - `analyze_stock_by_type` 的产出是一个 dict（含 status、prompt、数据等）。
    - MCP/Agent 通常更需要"一段可直接喂给模型的分析指令/上下文"（prompt 文本）。
    - 本函数负责：调用底层分析工具 -> 校验结果 -> 提取 prompt -> 以字符串形式返回。

    参数
    ----
    stock_code : str
        股票代码或股票名称（例如: '0700'、'腾讯控股'、'AAPL' 等）。
        底层会通过 `search_symbol` 等逻辑识别并映射为标准代码。

    analyze_type_list : List[str]
        分析类型列表。推荐取值（与底层实现一致）:
        - "基本面": 生成基本面分析所需的 prompt（通常会包含公司概况/财务指标等上下文）
        - "技术面": 生成技术面分析所需的 prompt（通常会引用价格/成交量等序列数据）
        - "新闻面": 生成新闻面分析所需的 prompt（通常会引用最近新闻列表/快讯）
        说明: 若传入不支持的类型，底层可能跳过或返回"不支持的分析类型"。

    language : str, default "zh-CN"
        输出 prompt 的主要语言。用于控制底层 prompt 的语言风格（例如中文/英文）。

    返回
    ----
    str
        - 成功: 返回底层生成的 prompt 文本（system_content），可直接用于 LLM 分析与回答。
        - 失败/无数据: 返回降级提示文案"暂时没有找到相关数据，礼貌回复用户"。

    依赖
    ----
    analyze_stock_by_type(stock_code, analyze_type_list, language) -> Dict
        预期返回结构示例（简化）:
        {
            "status": "success",
            "prompt": "...可给模型的分析提示词...",
            "analysis_type": ["基本面", "新闻面"],
            "data": {...},
            "len_data": 123
        }

    MCP/Agent 使用建议
    ------------------
    - 本工具返回的是"分析 prompt/上下文"，不直接给出结论；结论由上层模型结合用户问题生成。
    - 回答时建议明确：使用了哪些维度（基本面/技术面/新闻面），并提示数据时点与局限性。
    """
    tool_data = analyze_stock_by_type(stock_code, analyze_type_list, language)

    # 成功：取出底层生成的 prompt，作为给模型的 system_content
    if isinstance(tool_data, dict) and tool_data.get("status") == "success":
        system_content = tool_data.get("prompt", "")
    else:
        # 失败降级：避免 MCP 链路抛错，改为礼貌提示
        system_content = "暂时没有找到相关数据，礼貌回复用户"

    return system_content
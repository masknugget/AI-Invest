from app.services.chatbot.tools import search_stock_information


def get_stock_info(stock_code: str) -> str:
    """
    MCP 工具封装：获取股票信息，并将结果整理成适合大模型直接阅读的 system 提示词文本。

    设计目的
    --------
    - 对下游 MCP/Agent 来说，工具的价值在于"取数 + 结构化/格式化输出"。
    - 该函数负责调用底层数据工具 `search_stock_information`，并把返回的股票信息拼接为
      一段可直接注入到 LLM system / tool 结果中的文本，指导模型"优先使用最新数据回答"。

    参数
    ----
    stock_code : str
        股票代码或股票名称（例如: '0700'、'腾讯控股'、'AAPL' 等）。
        具体支持的格式由 `search_stock_information` 内部的 `search_symbol` 决定。

    返回
    ----
    str
        - 成功: 返回 system_content 文本，包含固定引导语 + tool_data（股票信息全文）。
          调用方可将该字符串作为 tool 输出 / system prompt 的一部分，供模型回答用户问题。
        - 失败: 返回以"工具调用出错:"开头的错误文本，保证调用链不抛异常、可降级展示。

    依赖
    ----
    search_stock_information(stock_code)
        返回值形如: (tool_data: str, data_dt: dict)
        - tool_data: 已格式化的股票信息文本（含名称/代码/收盘价/描述/日期/最新价格/新闻等）
        - data_dt: 结构化指标字典（目前本函数未使用，但可用于后续结构化推理/计算）

    注意事项（给 MCP/Agent 的使用约束）
    --------------------------------
    - 回答用户问题时：优先使用 tool_data 中"最新价格-实时"的信息；
      若实时为空或缺失，再使用"收盘价/日期"等历史字段。
    - 本函数只做信息拼装，不做投资建议或结论判断；分析应交给上层 Agent/LLM。
    """
    try:
        # 调用底层取数工具：
        # tool_data 为可读文本；data_dt 为结构化字典（预留给后续增强使用）
        tool_data, data_dt = search_stock_information(stock_code)

        # 给大模型的指令：强调"最新优先"，避免模型用过期收盘价回答实时问题
        system_content = (
            "请根据以下股票信息回答用户问题：以最新优先，如果最新有数据的话，否则用其他\n\n"
            f"{tool_data}"
        )
        return system_content

    except Exception as e:
        # MCP 友好：不抛异常，统一返回可展示的错误信息，便于上层降级处理
        return f"工具调用出错: {str(e)}"
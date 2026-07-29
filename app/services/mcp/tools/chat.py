from typing import Optional

from app.services.chatbot.chatbot_service import chat as _chat


def chat(
    user_query: str,
    conversation_id: str = "",
) -> str:
    """
    与 AI-Invest 投资助手进行对话，支持股票信息查询、股票分析和一般问答。

    该函数由 app.services.mcp.server 通过 mcp.add_tool() 注册为 MCP 工具，
    因此本模块不需要（也不能，避免循环导入）再使用 @mcp.tool() 装饰器。

    Args:
        user_query: 用户输入的问题或指令（如 "分析一下腾讯控股"、"00001 最近收盘价多少"）。
        user_id: 用户ID，可选，用于会话追踪。
        conversation_id: 对话ID，可选，用于多轮对话上下文保持。

    Returns:
        助手完整回复文本。
    """
    user_id = 'user'
    try:
        # 原 chat 函数返回生成器，需收集所有流式片段并拼接为完整回复
        chunks = list(
            _chat(
                user_query=user_query,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        )
        return "".join(str(chunk) for chunk in chunks)
    except Exception as e:
        return f"对话处理出错: {str(e)}"

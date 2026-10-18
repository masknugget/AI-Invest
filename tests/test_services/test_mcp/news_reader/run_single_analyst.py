"""
让【单个分析师】分析【单条新闻】的最小调用示例（连 LLM）。

回答：只想调用某一个分析师（不走路由、不跑全流程）该怎么做？两步即可——
    1) extract_news_meta(content)     先拿结构化 meta（分析师工具的必需入参）
    2) <analyst>.fn(content, meta)    调用指定分析师，得到该分析师的报告

meta 是分析师的必需输入（内部据此定位实体 / 分类 / 事件）；若你已持有 meta，
可跳过步骤 1、直接执行步骤 2。

真实调用依赖有效 LLM key；key 失效时抛异常，本示例捕获打印、不中断。

运行： G:\\git_data\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_single_analyst.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, parse
from app.services.mcp.tools.news_reader import analysts, pipeline

# ↓↓↓ 改这里：想调用哪个分析师 + 分析哪条新闻 ↓↓↓
# 可选工具名（12 个）：macro_analyst / industry_analyst / micro_analyst /
#   event_analyst / valuation_analyst / technical_analyst / technical_hl_analyst /
#   sentiment_analyst / dividend_analyst / fundamental_analyst /
#   portfolio_analyst / risk_analyst
AGENT_TOOL = "macro_analyst"
CONTENT = "央行宣布降准 0.5 个百分点，释放长期资金约 1 万亿元，利好银行与地产板块。"
# ↑↑↑ 改这里 ↑↑↑


def main():
    banner("步骤 0：取出目标分析师工具")
    tools = {t.name: t for t in analysts.build_analyst_tools()}
    if AGENT_TOOL not in tools:
        print(f"❌ 未知分析师工具 '{AGENT_TOOL}'，可选：{', '.join(tools)}")
        return False
    tool = tools[AGENT_TOOL]
    print(f"目标分析师: {tool.name} —— {tool.title}")

    banner("步骤 1：extract_news_meta 获取 meta（分析师必需入参，真实 LLM）")
    meta_resp = parse(pipeline.extract_news_meta(CONTENT))
    if meta_resp["status"] != "success":
        print("⚠️ 提取失败（多为 LLM key 未配置/失效），分析师调用跳过。")
        print("error:", meta_resp.get("error"))
        return False
    meta = meta_resp["data"]
    print("meta keys:", list(meta.keys()))

    banner(f"步骤 2：调用 {tool.name}(content, meta) 单独分析（真实 LLM）")
    resp = parse(tool.fn(CONTENT, meta))
    print("status:", resp.get("status"), "| tool:", resp.get("tool"))
    if resp["status"] != "success":
        print("❌ 分析师调用失败:", resp.get("error"))
        return False

    data = resp["data"]
    print("agent_name:", data.get("agent_name"))
    print("报告:\n" + "-" * 60)
    print(data.get("report"))
    print("-" * 60)

    print("\n✅ 单分析师分析示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

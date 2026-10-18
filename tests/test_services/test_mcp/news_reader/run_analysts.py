"""
analysts.py 分析师工具工厂真实调用示例（连 LLM）。

演示：
    build_analyst_tools()   按 factory 生成全部分析师 MCP 工具，打印工具名清单
    单个分析师工具真实调用   extract_news_meta 获取 meta → macro_analyst(content, meta)

真实调用依赖有效 LLM key（同 run_pipeline）；key 失效时工具返回 status=error 的
JSON（401 等），本示例捕获并打印，不抛出。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_analysts.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, parse
from app.services.mcp.tools.news_reader import analysts, pipeline

CONTENT = "某头部新能源车企宣布完成 50 亿元定向增发，募集资金用于固态电池研发。"


def main():
    banner("步骤 1：build_analyst_tools —— 生成的分析师工具清单")
    tools = {t.name: t for t in analysts.build_analyst_tools()}
    print(f"共 {len(tools)} 个分析师工具:")
    for name, tool in tools.items():
        print(f"  - {name:<22} {tool.title}")

    banner("步骤 2：extract_news_meta 获取 meta（真实 LLM）")
    meta_resp = parse(pipeline.extract_news_meta(CONTENT))
    print(json.dumps(meta_resp, ensure_ascii=False, indent=2))
    if meta_resp["status"] != "success":
        print("\n⚠️ 提取失败（多为 LLM key 未配置/失效），分析师调用跳过。")
        return False

    banner("步骤 3：真实调用 macro_analyst(content, meta)")
    macro = tools.get("macro_analyst") or next(iter(tools.values()))
    report_resp = parse(macro.fn(CONTENT, meta_resp["data"]))
    print("tool:", report_resp.get("tool"))
    print("status:", report_resp.get("status"))
    data = report_resp.get("data") or {}
    print("agent_name:", data.get("agent_name"))
    print("report:\n", data.get("report") or report_resp.get("error"))

    ok = report_resp["status"] == "success"
    print("\n✅ analysts 真实调用示例执行完毕" if ok else "\n❌ 分析师调用返回错误")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

"""
insights.py 存储/发现查询工具真实调用示例（连 MongoDB 只读，零 LLM）。

演示：
    list_news_analysts()        查询可用分析师清单（零 LLM，毫秒级，始终可运行）
    search_news_insights(...)   检索 insight_agg 历史分析（只读 MongoDB，需已连库）

search 需要 MongoDB 可连接；若连接失败会返回 status=error 的 JSON，本示例捕获并
打印，不抛出。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_insights.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, close_db, init_db, parse, run
from app.services.mcp.tools.news_reader import insights


def main():
    banner("示例 1：list_news_analysts（零 LLM）")
    listed = parse(run(insights.list_news_analysts()))
    print("count:", listed["data"]["count"])
    for a in listed["data"]["analysts"]:
        print(f"  - {a['tool_name']:<22} {a['agent_name']}")

    banner("示例 2：search_news_insights（只读 MongoDB）")
    ok = listed["status"] == "success"
    try:
        run(init_db())
    except Exception as e:
        print(f"⚠️ MongoDB 连接初始化失败，跳过检索示例: {e}")
        return ok

    try:
        searched = parse(run(insights.search_news_insights(query="", limit=3)))
        print("status:", searched["status"])
        if searched["status"] == "success":
            print("count:", searched["data"]["count"])
            print(json.dumps(searched["data"]["items"], ensure_ascii=False, indent=2)[:800])
        else:
            print("error:", searched["error"])
        ok = ok and searched["status"] == "success"
    finally:
        run(close_db())

    print("\n✅ insights 真实调用示例执行完毕" if ok else "\n❌ 存在失败示例")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

"""
router.py 路由工具真实调用示例（连 LLM）。

演示拆分工具模式的路由环节（阶段1 提取 → 阶段2 路由）：
    extract_news_meta(content)          结构化提取，返回 meta
    route_news_analysts(content, meta)  服务端 LLM 路由，推荐应调用的分析师 + 工具名

真实调用依赖有效 LLM key（同 run_pipeline）；key 失效时提取/路由会抛异常，
本示例捕获并打印，不抛出。

运行： G:\\git_data\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_router.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, parse
from app.services.mcp.tools.news_reader import pipeline, router

CONTENT = "央行宣布降准 0.5 个百分点，释放长期资金约 1 万亿元，利好银行与地产板块。"


def main():
    banner("步骤 1：extract_news_meta 获取 meta（真实 LLM）")
    meta_resp = parse(pipeline.extract_news_meta(CONTENT))
    if meta_resp["status"] != "success":
        print("⚠️ 提取失败（多为 LLM key 未配置/失效），路由跳过。")
        print("error:", meta_resp.get("error"))
        return False
    meta = meta_resp["data"]
    print("meta keys:", list(meta.keys()))

    banner("步骤 2：route_news_analysts 路由决策（真实 LLM）")
    route_resp = parse(
        router.route_news_analysts(CONTENT, json.dumps(meta, ensure_ascii=False))
    )
    print("status:", route_resp.get("status"), "| tool:", route_resp.get("tool"))
    if route_resp["status"] != "success":
        print("❌ 路由失败:", route_resp.get("error"))
        return False

    data = route_resp["data"]
    print(f"count={data['count']}  agent_names={data['agent_names']}")
    print(f"可直接调用的工具 tools={data['tools']}")
    print("reasoning:", data.get("reasoning"))
    print("routing_plan:", json.dumps(data.get("routing_plan"), ensure_ascii=False, indent=2))

    print("\n✅ router 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

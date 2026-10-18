"""
analysts.py 全部 12 个分析师工具逐个真实调用示例（连 LLM）。

与 run_analysts.py（仅演示单个 macro_analyst）不同，本示例遍历 factory 生成的
每一个分析师工具，用同一条新闻 + 同一份 meta 逐个真实调用并打印报告预览，
用于快速验证 12 个分析师工具是否都能正常产出。

真实调用依赖有效 LLM key；key 失效时工具返回 status=error 的 JSON，本示例
捕获并打印、不中断，最后汇总成功 / 失败数。

运行： G:\\git_data\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_analysts_one.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, parse
from app.services.mcp.tools.news_reader import analysts, pipeline

CONTENT = (
    "某头部新能源车企宣布完成 50 亿元定向增发，募集资金用于固态电池研发，"
    "机构关注其估值水平与行业竞争格局变化。"
)

# 每份报告仅预览前若干字符，避免 12 个工具刷屏
PREVIEW_CHARS = 160


def main():
    banner("步骤 1：build_analyst_tools —— 生成的分析师工具清单")
    tools = {t.name: t for t in analysts.build_analyst_tools()}
    print(f"共 {len(tools)} 个分析师工具:")
    for name, tool in tools.items():
        print(f"  - {name:<22} {tool.title}")

    banner("步骤 2：extract_news_meta 获取 meta（真实 LLM，一次，供全部分析师复用）")
    meta_resp = parse(pipeline.extract_news_meta(CONTENT))
    if meta_resp["status"] != "success":
        print("⚠️ 提取失败（多为 LLM key 未配置/失效），分析师调用跳过。")
        print("error:", meta_resp.get("error"))
        return False
    meta = meta_resp["data"]
    print("meta keys:", list(meta.keys()))

    banner("步骤 3：逐个真实调用全部分析师工具")
    total = len(tools)
    ok_count = 0
    failed = []
    for i, (name, tool) in enumerate(tools.items(), 1):
        print(f"\n[{i}/{total}] {name} —— {tool.title}")
        resp = parse(tool.fn(CONTENT, meta))
        data = resp.get("data") or {}
        if resp.get("status") == "success":
            ok_count += 1
            report = data.get("report") or ""
            preview = report[:PREVIEW_CHARS].replace("\n", " ").strip()
            print(f"  ✅ status=success  agent={data.get('agent_name')}  报告长度={len(report)}")
            print(f"     预览: {preview}...")
        else:
            failed.append(name)
            print(f"  ❌ status=error  error={resp.get('error')}")

    banner("汇总")
    print(f"成功 {ok_count}/{total}")
    if failed:
        print("失败:", ", ".join(failed))

    all_ok = ok_count == total
    print("\n✅ 全部分析师工具调用成功" if all_ok else "\n⚠️ 存在失败的分析师工具（见上方汇总）")
    return all_ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

"""
report_prompt.py 报告 Prompt 构建工具真实调用示例（连 LLM）。

演示「步骤1/2 真实 LLM + 步骤3 仅拼装 Prompt」的端到端流程，并把每一步的
完整结果原样打印出来（不做断言校验）：
    build_report_prompts(content)
      步骤1  extract_news_meta(content)          结构化提取 NER/标签/事件（真实 LLM）
      步骤2  route_news_analysts(content, meta)  服务端 LLM 路由，得到推荐分析师（真实 LLM）
      步骤3  取路由前两个分析师，各自 Prompt 与 content/ner/label/event 拼成报告 Prompt
             （不调用分析师 LLM，只返回 Prompt 字符串）

真实调用依赖有效 LLM key（环境变量 NEWS_READER_API_KEY > DASHSCOPE_API_KEY >
OPENAI_API_KEY，或根目录 .env）；若 key 失效，build_report_prompts 内部会抛异常，
本示例捕获并打印，不向外抛出。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_report_prompt.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner
from app.services.mcp.tools.news_reader import report_prompt

CONTENT = "央行宣布降准 0.5 个百分点，释放长期资金约 1 万亿元，利好银行与地产板块。"


def main():
    banner("输入：新闻正文 content")
    print(CONTENT)

    banner("build_report_prompts（步骤1/2 真实 LLM，步骤3 拼装报告 Prompt）")
    try:
        result = report_prompt.build_report_prompts(CONTENT)
    except Exception as e:  # LLM key 失效 / 网络异常等
        print("⚠️ 构建失败（多为 LLM key 未配置/失效）:", e)
        return False

    banner("步骤 1 结果：结构化提取 meta（data_ner / data_label / data_event）")
    print(json.dumps(result["meta"], ensure_ascii=False, indent=2))

    banner("步骤 2 结果：路由推荐名单 agent_names")
    print(json.dumps(result["agent_names"], ensure_ascii=False, indent=2))

    banner("步骤 3 结果：取用的前两个分析师 selected")
    print(json.dumps(result["selected"], ensure_ascii=False, indent=2))

    banner("步骤 3 结果：完整报告 Prompt（prompts）")
    for name, prompt in result["prompts"].items():
        print("\n" + "#" * 70)
        print(f"# 分析师: {name}    prompt 长度={len(prompt)}")
        print("#" * 70)
        print(prompt)

    # ------------------------------------------------------------------
    # 合并演示：build_merged_report_prompt 把前两个分析师合并为一份综合报告 Prompt
    # （步骤1/2 会再走一次真实 LLM；extract 命中 Redis 缓存时零 LLM 调用）
    # ------------------------------------------------------------------
    banner("build_merged_report_prompt（多视角合并为单一综合报告 Prompt）")
    try:
        merged = report_prompt.build_merged_report_prompt(CONTENT)
    except Exception as e:  # LLM key 失效 / 网络异常等
        print("⚠️ 合并构建失败（多为 LLM key 未配置/失效）:", e)
        return False

    banner("合并结果：纳入综合的分析师 selected")
    print(json.dumps(merged["selected"], ensure_ascii=False, indent=2))

    banner("合并结果：完整合并 Prompt（merged_prompt）")
    print(f"prompt 长度={len(merged['merged_prompt'])}")
    print("\n" + "#" * 70)
    print(merged["merged_prompt"])
    print("#" * 70)

    print("\n✅ report_prompt 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

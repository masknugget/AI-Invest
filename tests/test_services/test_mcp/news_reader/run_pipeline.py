"""
pipeline.py 流水线工具真实调用示例（连 LLM）。

演示拆分工具模式的核心两步，直接调用真实服务并打印返回：
    extract_news_meta(content)            阶段1：NER / 标签 / 事件 三路并行提取
    finalize_news_analysis(..., save=False) 阶段5：结构化对齐（不落库）

真实调用依赖有效 LLM key（环境变量 NEWS_READER_API_KEY > DASHSCOPE_API_KEY >
OPENAI_API_KEY，或根目录 .env）；若 key 失效会返回 401，本示例会捕获并打印错误
响应（工具契约层把异常包成 status=error 的 JSON，不抛出）。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_pipeline.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner, parse, run
from app.services.mcp.tools.news_reader import pipeline

CONTENT = "央行宣布降准 0.5 个百分点，释放长期资金约 1 万亿元，利好银行与地产板块。"


def main():
    banner("步骤 1：extract_news_meta（结构化提取，真实 LLM）")
    meta_resp = parse(run(pipeline.extract_news_meta(CONTENT)))
    print(json.dumps(meta_resp, ensure_ascii=False, indent=2))
    if meta_resp["status"] != "success":
        print("\n⚠️ 提取失败（多为 LLM key 未配置/失效），后续步骤跳过。")
        return False

    meta = meta_resp["data"]

    banner("步骤 2：finalize_news_analysis（结构化对齐，save=False 不落库）")
    # 真实场景这里喂入各分析师报告；为控制成本，示例仅手工放一条占位分析
    analyses = {"MicroAgent": "## 微观影响\n降准降低资金成本，利好银行净息差预期。"}
    final_resp = parse(
        run(
            pipeline.finalize_news_analysis(
                CONTENT,
                json.dumps(meta, ensure_ascii=False),
                json.dumps(analyses, ensure_ascii=False),
                save=False,
            )
        )
    )
    print(json.dumps(final_resp, ensure_ascii=False, indent=2))

    ok = final_resp["status"] == "success"
    print("\n✅ pipeline 真实调用示例执行完毕" if ok else "\n❌ finalize 返回错误")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

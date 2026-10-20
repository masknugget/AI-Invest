"""
prompt_portfilo.py HTML 报告 Prompt 构建 + 真实 LLM 生成示例。

`build_portfolio_html_report_prompt` 内部会调用 portfolio_full_report /
portfolio_rebalance_suggestion 拿到结构化 JSON，再拼装成一段完整的
「HTML 报告生成 Prompt」。本示例做两件事：

    1. 调用 build_portfolio_html_report_prompt 打印拼装出的 prompt（含数据段）
    2. 把该 prompt 送入真实 LLM（复用 recommender.news_reader.llms.chat_once），
       打印返回的 HTML 前若干字符，并把完整 HTML 保存到 tmp/portfolio_report.html
       以便直接在浏览器中打开查看效果

依赖：
    - MongoDB 已入库 sz.000001 / sz.000002 相关行情与 p_advisor_cal_dimensions 分数
    - LLM key 有效（NEWS_READER_API_KEY > DASHSCOPE_API_KEY > OPENAI_API_KEY，
      或 llms.py 中的 DEFAULT_API）；key 失效时脚本会捕获异常并提示，不向外抛出

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_prompt_portfilo.py
"""
import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32":
    import ctypes

    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice.prompt_portfilo import (  # noqa: E402
    build_portfolio_html_report_prompt,
)

CODES = ["sz.000001", "sz.000002"]
WEIGHTS = [0.5, 0.5]
OUTPUT_HTML = PROJECT_ROOT / "tmp" / "portfolio_report.html"
HTML_PREVIEW_CHARS = 1500


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_build_prompt() -> str:
    """构建 prompt 并打印（不调用 LLM）。"""
    banner(f"步骤 1：build_portfolio_html_report_prompt({CODES}, {WEIGHTS})")
    try:
        prompt = build_portfolio_html_report_prompt(
            codes=CODES,
            weights=WEIGHTS,
            include_rebalance=True,
            rebalance_objective="composite_score",
        )
    except Exception as e:
        print(f"⚠️ 构建 prompt 失败（多为 MongoDB 未连 / 行情缺失）: {e}")
        return ""

    print(f"prompt 总长度 = {len(prompt)} 字符")
    print("-" * 70)
    print(prompt)
    print("-" * 70)
    return prompt


def demo_call_llm(prompt: str) -> None:
    """把 prompt 送入真实 LLM，打印 HTML 结果并落盘。"""
    if not prompt:
        print("⚠️ 跳过 LLM 调用（prompt 为空）")
        return

    banner("步骤 2：调用真实 LLM 生成 HTML 报告")
    try:
        from recommender.news_reader.llms import chat_once
    except Exception as e:
        print(f"⚠️ 导入 chat_once 失败: {e}")
        return

    try:
        html = chat_once(prompt)
    except Exception as e:
        print(f"⚠️ LLM 调用失败（多为 key 未配置/失效或网络异常）: {e}")
        return

    print(f"HTML 返回长度 = {len(html)} 字符")
    banner(f"HTML 预览（前 {HTML_PREVIEW_CHARS} 字符）")
    print(html[:HTML_PREVIEW_CHARS])
    if len(html) > HTML_PREVIEW_CHARS:
        print(f"\n... [已截断，剩余 {len(html) - HTML_PREVIEW_CHARS} 字符见文件]")

    try:
        OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_HTML.write_text(html, encoding="utf-8")
        banner(f"✅ HTML 已保存到 {OUTPUT_HTML}")
    except Exception as e:
        print(f"⚠️ 保存 HTML 到文件失败: {e}")


def main():
    prompt = demo_build_prompt()
    demo_call_llm(prompt)
    print("\n✅ prompt_portfilo 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

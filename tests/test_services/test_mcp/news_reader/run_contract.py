"""
contract.py 契约层用法示例（纯函数，无 I/O，离线即可运行）。

演示 MCP 边界层的三类能力，直接调用并打印结果：
- 统一响应封装 make_response / error_response
- 平台回传参数的宽容解析 parse_meta / parse_analyses（裸数据 or 完整响应封装皆可）
- 参数校验 validate_content / validate_limit

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/news_reader/run_contract.py
"""
import json
import sys
from pathlib import Path

# 保证无论从何处运行都能找到本目录下的 _bootstrap（仅用于环境引导与辅助函数）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: F401  触发路径设置 + recommender 命名空间注册 + .env 加载
from _bootstrap import banner
from app.services.mcp.tools.news_reader import contract

META = {"data_ner": {"entities": []}, "data_label": {"impact_level": "MACRO"}, "data_event": {}}


def demo_response_envelope():
    banner("示例 1：统一响应封装")
    ok = contract.make_response("extract_news_meta", META)
    err = contract.error_response("extract_news_meta", "content 不能为空")
    print("成功响应:", json.dumps(json.loads(ok), ensure_ascii=False, indent=2))
    print("错误响应:", err)


def demo_parse_meta():
    banner("示例 2：meta 宽容解析")
    # 2a 裸 meta
    print("裸 meta    ->", contract.parse_meta(dict(META)))
    # 2b JSON 字符串
    print("JSON 字符串 ->", contract.parse_meta(json.dumps(META, ensure_ascii=False)))
    # 2c 完整响应封装（平台常把上一步工具返回原样回传，自动剥 data）
    envelope = contract.make_response("extract_news_meta", dict(META))
    print("响应封装    ->", contract.parse_meta(json.loads(envelope)))


def demo_parse_analyses():
    banner("示例 3：analyses 归一")
    # 单报告形态 {"agent_name", "report"} 自动归一为 {agent: report}
    single = {"agent_name": "MicroAgent", "report": "## 利好"}
    print("单报告归一 ->", contract.parse_analyses(single))
    # 多分析师 + 平台自撰综合解读
    multi = {"MicroAgent": "r1", "SentimentAgent": "r2", "综合解读": "平台文案"}
    print("多报告回传 ->", contract.parse_analyses(json.dumps(multi, ensure_ascii=False)))


def demo_validation():
    banner("示例 4：参数校验")
    print("validate_content('一条新闻') ->", repr(contract.validate_content("一条新闻")))
    for bad in ("", "   "):
        try:
            contract.validate_content(bad)
        except ValueError as e:
            print(f"validate_content({bad!r}) 拦截 -> {e}")
    print("validate_limit(5)  ->", contract.validate_limit(5))
    for bad in (0, 101, "10"):
        try:
            contract.validate_limit(bad)
        except ValueError as e:
            print(f"validate_limit({bad!r}) 拦截 -> {e}")


def main():
    demo_response_envelope()
    demo_parse_meta()
    demo_parse_analyses()
    demo_validation()
    print("\n✅ contract 契约层示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

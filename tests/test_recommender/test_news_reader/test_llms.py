# -*- coding: utf-8 -*-
"""
news_reader.llms 真实连通性测试 —— 实际调用大模型并把返回结果打印出来。

目的：验证「模型到底能不能调通」（真实网络调用，无任何 mock）。
说明：本文件只负责端到端连通性验证，且只测试同步入口 chat_once。
     achat_once 以及重试、空响应、messages 构造等逻辑单测已由
     tests/test_services/test_mcp/test_news_reader_mcp.py（全 mock）覆盖。

前置条件：提供 API key（三选一，优先级从高到低），可用任意方式注入环境变量：
    $env:NEWS_READER_API_KEY = "sk-..."     # 最高优先级
    $env:DASHSCOPE_API_KEY   = "sk-..."
    $env:OPENAI_API_KEY      = "sk-..."
可选（不设则用默认值）：
    $env:NEWS_READER_BASE_URL       默认 https://dashscope.aliyuncs.com/compatible-mode/v1
    $env:NEWS_READER_MODEL          默认模型（提取/轻量阶段）
    $env:NEWS_READER_ANALYST_MODEL  分析 Agent 模型

若项目根存在 .env，会自动加载到环境变量（python-dotenv）。

运行方式：
    python tests/test_recommender/test_news_reader/test_llms.py
"""
import sys
import time
import traceback
from pathlib import Path


import recommender.news_reader.llms as llms


def _mask(secret: str) -> str:
    """遮蔽密钥，仅保留首尾各 4 位。"""
    if not secret:
        return "(未设置)"
    if len(secret) <= 8:
        return secret[:2] + "****"
    return f"{secret[:4]}****{secret[-4:]}"


def _show_config():
    print("=" * 70)
    print("当前 LLM 配置")
    print("-" * 70)
    try:
        key = llms.get_api_key()
        print(f"  API key       : {_mask(key)}")
    except RuntimeError as e:
        print(f"  API key       : ❌ {e}")
        return False
    print(f"  base_url        : {llms.get_base_url()}")
    print(f"  默认模型         : {llms.get_default_model()}")
    print(f"  分析 Agent 模型  : {llms.get_analyst_model()}")
    print("=" * 70)
    return True


def test_sync_call():
    """同步 chat_once：发一句简单指令，打印模型原始返回。"""
    print("\n=== 真实调用：chat_once（同步）===")
    prompt = "用一句话解释什么是量化宽松（QE）。"
    print(f"  请求 prompt: {prompt}")
    t0 = time.perf_counter()
    resp = llms.chat_once(prompt)
    dt = time.perf_counter() - t0
    print(f"  耗时: {dt:.2f}s")
    print(f"  模型返回:\n{resp}")
    assert resp and resp.strip(), "模型返回为空"
    print("✅ chat_once 连通")


def main():
    if not _show_config():
        print("\n❌ 未检测到 API key，无法进行真实调用。请先设置环境变量后重试：")
        print(r'    $env:NEWS_READER_API_KEY = "sk-..."   # 或 DASHSCOPE_API_KEY / OPENAI_API_KEY')
        return False

    tests = [
        ("chat_once_sync", test_sync_call),
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {name} 失败: {e}")
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"=== 大模型连通性测试: {passed} passed, {failed} failed ===")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

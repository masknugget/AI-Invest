"""
data_source.py 数据源用法示例（真实 MongoDB / 行情源，零 LLM）。

演示：
    detect_code_market            代码市场探测
    industry_lookup               行业查询（MongoDB stock_db）
    build_industry_distribution   行业分布聚合
    fetch_quote_df                单只行情（本地 stock_daily_quotes 优先，其次线上）

行情依赖本地已入库数据；未入库代码 fetch_quote_df 会抛 ValueError，示例捕获打印。

运行： F:\\project_work\\hf\\AI-Invest\\.venv\\Scripts\\python.exe \
      tests/test_services/test_mcp/portfolio/run_data_source.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.services.mcp.tools.portfolio_advice import data_source


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def demo_detect_market():
    banner("示例 1：detect_code_market")
    for code in ("sz.000001", "sh.600000", "hk.00700", "us.AAPL"):
        try:
            print(f"  {code:<12} -> {data_source.detect_code_market(code)}")
        except Exception as e:
            print(f"  {code:<12} -> 错误: {e}")


def demo_industry():
    banner("示例 2：industry_lookup / build_industry_distribution")
    try:
        print("industry_lookup(sz.000001) ->", data_source.industry_lookup("sz.000001"))
        print("industry_lookup(sh.600000) ->", data_source.industry_lookup("sh.600000"))
    except Exception as e:
        print("行业查询失败 ->", e)

    try:
        dist = data_source.build_industry_distribution(
            ["sz.000001", "sz.000002"], [0.5, 0.5]
        )
        print("行业分布 ->", dist, "合计=", sum(dist.values()))
    except Exception as e:
        print("行业分布失败 ->", e)


def demo_fetch_quote():
    banner("示例 3：fetch_quote_df（行情）")
    for code in ("sz.000001", "sh.600000"):
        try:
            df = data_source.fetch_quote_df(code)
            print(f"  {code} rows={len(df)} cols={list(df.columns)}")
            if len(df):
                print(f"  head:\n{df.head(2)}")
        except Exception as e:
            print(f"  {code} 无行情 -> {e}")


def main():
    demo_detect_market()
    demo_industry()
    demo_fetch_quote()
    print("\n✅ data_source 真实调用示例执行完毕")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

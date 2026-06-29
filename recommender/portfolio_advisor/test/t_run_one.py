"""
run_one.py 单只股票五维诊断的简单使用示例与基础校验。

运行方式：
    python research/portfolio_advisor/test/t_run_one.py

需要在项目根目录下执行，或保证 sys.path 包含项目根目录。
"""

import math

from research.portfolio_advisor.dimension.run_one import (
    PortfolioDimensions,
    compute_stock_dimensions,
    load_random_stock,
)


def _fmt(value: float) -> str:
    """格式化浮点数输出，兼容 nan / inf。"""
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    if isinstance(value, float) and math.isinf(value):
        return str(value)
    if value is None:
        return "None"
    return f"{value:.4f}"


def run_simple_tests() -> int:
    """运行基础断言测试，返回失败数量。"""
    failures = 0

    def _record_error(msg: str) -> None:
        nonlocal failures
        failures += 1
        print(f"  [FAIL] {msg}")

    print("=" * 70)
    print("基础校验")
    print("=" * 70)

    # 1. 权重长度错误
    try:
        df = load_random_stock()
        compute_stock_dimensions(df, [0.5, 0.5])
        _record_error("权重长度不为 1 时未抛出异常")
    except ValueError:
        print("  [PASS] 权重长度不为 1 时正确抛出 ValueError")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"权重长度校验异常类型错误: {exc}")

    # 2. 权重值错误
    try:
        df = load_random_stock()
        compute_stock_dimensions(df, [0.5])
        _record_error("权重不为 1.0 时未抛出异常")
    except ValueError:
        print("  [PASS] 权重不为 1.0 时正确抛出 ValueError")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"权重值校验异常类型错误: {exc}")

    # 3. dfs 类型错误
    try:
        compute_stock_dimensions("not_a_dataframe", [1.0])
        _record_error("dfs 类型错误时未抛出异常")
    except TypeError:
        print("  [PASS] dfs 类型错误时正确抛出 TypeError")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"dfs 类型校验异常类型错误: {exc}")

    # 4. 正常计算并检查字段与范围
    try:
        df = load_random_stock()
        result = compute_stock_dimensions(df, [1.0])

        assert isinstance(result, PortfolioDimensions), "返回值类型错误"

        scores = result.to_score_dict()
        assert set(scores.keys()) == {
            "drawdown_control",
            "portfolio_diversification",
            "position_efficiency",
            "return_stability",
            "style_balance",
        }, "五维评分字典 keys 不完整"

        for dim, score in scores.items():
            assert 0.0 <= score <= 100.0, f"{dim} 得分越界: {score}"

        assert 0.0 <= result.composite_score <= 100.0, "综合健康分越界"
        assert 0.0 <= result.geometric_composite_score <= 100.0, "几何加权综合分越界"

        # 单只股票的风格均衡退化为完全集中
        assert result.style_balance.style_hhi == 1.0
        assert result.style_balance.effective_style_num == 1.0
        assert result.style_balance.score == 0.0

        print("  [PASS] 单只股票维度计算结果格式与范围正确")
    except Exception as exc:  # noqa: BLE001
        _record_error(f"单只股票维度计算异常: {exc}")

    return failures


def _print_result(result: PortfolioDimensions, code: str) -> None:
    """打印 PortfolioDimensions 的完整结果。"""
    print("\n" + "=" * 70)
    print(f"标的代码: {code}")
    print("=" * 70)

    print("【抗回撤能力】")
    print(f"  最大回撤 MDD       : {_fmt(result.drawdown_control.mdd)}")
    print(f"  控制得分 (0-100)   : {_fmt(result.drawdown_control.score)}")

    print("\n【资产分散度】")
    print(f"  ENB (weight-based) : {_fmt(result.portfolio_diversification.enb_weight_based)}")
    print(f"  ENB (risk-based)   : {_fmt(result.portfolio_diversification.enb_risk_based)}")
    print(f"  分散得分 (0-100)   : {_fmt(result.portfolio_diversification.score)}")

    print("\n【持仓性价比】")
    print(f"  夏普比率           : {_fmt(result.position_efficiency.sharpe_ratio)}")
    print(f"  性价比得分 (0-100) : {_fmt(result.position_efficiency.score)}")

    print("\n【收益稳定性】")
    print(f"  年化波动率         : {_fmt(result.return_stability.annualized_volatility)}")
    print(f"  稳定得分 (0-100)   : {_fmt(result.return_stability.score)}")

    print("\n【风格均衡】")
    print(f"  风格 HHI           : {_fmt(result.style_balance.style_hhi)}")
    print(f"  有效风格数         : {_fmt(result.style_balance.effective_style_num)}")
    print(f"  均衡得分 (0-100)   : {_fmt(result.style_balance.score)}")

    print("\n" + "=" * 70)
    print(f"综合健康分 (0-100)   : {_fmt(result.composite_score)}")
    print(f"几何加权综合分 (0-100): {_fmt(result.geometric_composite_score)}")
    print(f"维度权重             : {dict(result.dimension_weights)}")
    print("=" * 70)


if __name__ == "__main__":
    test_failures = run_simple_tests()

    print("\n" + "=" * 70)
    print("使用示例：随机抽取 1 只股票并计算五维诊断")
    print("=" * 70)

    df = load_random_stock()
    code = str(df["code"].iloc[0])
    result = compute_stock_dimensions(df)
    _print_result(result, code)

    print("\n" + "=" * 70)
    if test_failures == 0:
        print("所有基础校验通过")
    else:
        print(f"基础校验失败数量: {test_failures}")
    print("=" * 70)

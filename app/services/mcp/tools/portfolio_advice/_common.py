"""
Portfolio Advisor MCP 工具公共层。

职责：
- 统一响应封装（status / tool / data / warnings / error）
- 参数校验（股票代码、权重）
- 预计算分数文件检查
- 引擎模块安全导入（data_read 存在硬编码路径与模块级 IO，做注入兜底）

数据获取（行情多源冗余 / 行业查询 / 代码格式探测）已拆至同包 data_source.py，
本模块仅做重导出以保持向后兼容。

所有工具均为同步纯计算函数，docstring 即 MCP tool 描述。
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 数据获取层重导出（历史引用点兼容；新代码请直接从 data_source 导入）
from app.services.mcp.tools.portfolio_advice.data_source import (  # noqa: E402
    QUOTE_LOOKBACK_YEARS,
    _symbol_candidates,
    build_industry_distribution,
    detect_code_market,
    fetch_quote_df,
    fetch_quotes,
    industry_lookup,
)

# 预计算五维得分文件（调仓引擎依赖）
SCORES_PATH = (
    PROJECT_ROOT / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)

# 分数文件过期阈值（天）
SCORES_MAX_AGE_DAYS = 7

MAX_PORTFOLIO_SIZE = 20


# ============================================================================
# 引擎模块安全导入
# ============================================================================

def _ensure_engine_importable() -> None:
    """
    recommender.portfolio_advisor.data_read 存在硬编码 F:\\ 路径与模块级 parquet IO，
    导入失败会导致 dimension.run / rebalance.scoring 等整条链不可用。
    这里先探测导入，失败则注入仅提供 load_all 占位实现的 stub 模块，
    使计算引擎（不依赖 load_all 的部分）可以正常导入。
    """
    try:
        import recommender.portfolio_advisor.data_read  # noqa: F401
        return
    except Exception:
        stub = types.ModuleType("recommender.portfolio_advisor.data_read")

        def _unavailable(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("data_read 本地 fixture 不可用（部署环境无 parquet 数据）")

        stub.load_all = _unavailable  # type: ignore[attr-defined]
        sys.modules["recommender.portfolio_advisor.data_read"] = stub


_ensure_engine_importable()


def get_dimension_run():
    """惰性导入五维评分引擎入口。"""
    from recommender.portfolio_advisor.dimension import run as dimension_run

    return dimension_run


def get_format_advisor():
    from recommender.portfolio_advisor.format_adapt import format_advisor

    return format_advisor


# ============================================================================
# 统一响应封装
# ============================================================================

def make_response(
    tool: str,
    data: Any = None,
    status: str = "success",
    warnings: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> str:
    """构造统一 JSON 字符串响应，与现有 MCP 工具（返回 str）保持一致。"""
    payload = {
        "status": status,
        "tool": tool,
        "data": data,
        "warnings": warnings or [],
        "error": error,
    }
    return json.dumps(_to_jsonable(payload), ensure_ascii=False)


def error_response(tool: str, message: str) -> str:
    return make_response(tool, status="error", error=message)


def _to_jsonable(obj: Any) -> Any:
    """将 numpy / pandas / dataclass / datetime 等转换为 JSON 可序列化类型。"""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else str(obj)  # NaN/inf
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    # numpy 标量
    if hasattr(obj, "item"):
        try:
            return _to_jsonable(obj.item())
        except Exception:
            pass
    if isinstance(obj, (datetime,)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return _to_jsonable(asdict(obj))
    return str(obj)


# ============================================================================
# 参数校验
# ============================================================================

def validate_portfolio(codes: List[str], weights: List[float]) -> Tuple[List[str], List[float]]:
    """
    校验并归一化组合参数。

    - codes: 非空、去空白、无重复、数量不超过 MAX_PORTFOLIO_SIZE
    - weights: 长度与 codes 一致、全部非负、至少一个为正；总和允许 != 1，内部归一化

    返回 (codes, normalized_weights)；非法时抛 ValueError（中文信息）。
    """
    if not codes:
        raise ValueError("股票代码列表不能为空")
    if not weights:
        raise ValueError("权重列表不能为空")
    if len(codes) != len(weights):
        raise ValueError(
            f"股票代码数量({len(codes)})与权重数量({len(weights)})不一致"
        )
    if len(codes) > MAX_PORTFOLIO_SIZE:
        raise ValueError(f"组合标的数量过多（{len(codes)}），上限为 {MAX_PORTFOLIO_SIZE}")

    clean_codes = [str(c).strip() for c in codes]
    if any(not c for c in clean_codes):
        raise ValueError("存在空白股票代码")
    dup = [c for c in set(clean_codes) if clean_codes.count(c) > 1]
    if dup:
        raise ValueError(f"存在重复股票代码: {dup}")

    try:
        clean_weights = [float(w) for w in weights]
    except (TypeError, ValueError):
        raise ValueError("权重必须为数值")
    if any(w < 0 for w in clean_weights):
        raise ValueError("权重不能为负数")
    total = sum(clean_weights)
    if total <= 0:
        raise ValueError("权重总和必须为正数")

    return clean_codes, [w / total for w in clean_weights]


def build_portfolio_arg(codes: List[str], weights: List[float]) -> List[Dict[str, Any]]:
    """构造压力测试引擎所需的 portfolio 参数。"""
    return [{"code": c, "weight": w} for c, w in zip(codes, weights)]


# ============================================================================
# 预计算分数文件检查
# ============================================================================

def check_scores_file(max_age_days: int = SCORES_MAX_AGE_DAYS) -> Tuple[Path, List[str]]:
    """
    检查 stock_dimension_scores.jsonl 存在性与时效。

    返回 (path, warnings)；文件缺失抛 ValueError。
    """
    if not SCORES_PATH.exists():
        raise ValueError(
            f"预计算分数文件不存在: {SCORES_PATH}，"
            "请先运行候选池离线打分（compute_stock_dimensions）生成 stock_dimension_scores.jsonl"
        )
    warnings: List[str] = []
    mtime = datetime.fromtimestamp(SCORES_PATH.stat().st_mtime)
    age_days = (datetime.now() - mtime).days
    if age_days > max_age_days:
        warnings.append(
            f"预计算分数文件已 {age_days} 天未更新（阈值 {max_age_days} 天），调仓建议时效性可能不足"
        )
    return SCORES_PATH, warnings


def scores_file_meta() -> Dict[str, Any]:
    """返回分数文件元信息（路径/更新时间/大小）。"""
    try:
        path, _ = check_scores_file()
        stat = path.stat()
        return {
            "path": str(path),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": stat.st_size,
        }
    except ValueError as e:
        return {"path": str(SCORES_PATH), "error": str(e)}

"""
压力测试模块 —— 情景常量与场景工厂

仅包含：
1. 历史极端事件场景库
2. 板块（行业桶）Beta 映射与行业映射
3. 板块压力测试默认参数
4. StressScenario 数据类与工厂函数
5. 预定义场景集合

注意：
- 风险等级、调仓阈值等不属于“情景”的常量，已迁移到使用它们的模块内部，
  避免 const.py 变成大杂烩。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

# ============================================================================
# 历史极端事件场景
# ============================================================================
EXTREME_SCENARIOS = {
    "2008年金融危机": {
        "start_date": "2007-10-16",
        "end_date": "2008-11-04",
        "benchmark_drawdown": -0.724,  # 沪深300同期回撤
    },
    "2015年A股异常波动": {
        "start_date": "2015-06-12",
        "end_date": "2016-01-27",
        "benchmark_drawdown": -0.478,
    },
    "2020年疫情冲击": {
        "start_date": "2020-01-14",
        "end_date": "2020-03-19",
        "benchmark_drawdown": -0.156,
    },
}


# ============================================================================
# 板块压力测试默认参数
# ============================================================================
DEFAULT_SECTOR_CALLBACK_PCT = 0.20  # 默认板块回调幅度 20%

# 板块桶 -> 行业内 Beta（简化版，实际可用回归计算）
SECTOR_BETAS = {
    "科技": 1.15,
    "医药": 0.95,
    "金融": 0.85,
    "消费": 0.90,
    "周期": 1.05,
}

# 申万一级行业 -> 板块桶映射
SW_INDUSTRY_TO_SECTOR = {
    # 科技
    "电子": "科技",
    "计算机": "科技",
    "通信": "科技",
    "传媒": "科技",
    # 医药
    "医药生物": "医药",
    # 金融
    "银行": "金融",
    "非银金融": "金融",
    # 消费
    "食品饮料": "消费",
    "家用电器": "消费",
    "纺织服装": "消费",
    "轻工制造": "消费",
    "商业贸易": "消费",
    "休闲服务": "消费",
    "农林牧渔": "消费",
    # 周期 / 其他
    "化工": "周期",
    "钢铁": "周期",
    "有色金属": "周期",
    "建筑材料": "周期",
    "建筑装饰": "周期",
    "采掘": "周期",
    "机械设备": "周期",
    "汽车": "周期",
    "电气设备": "周期",
    "国防军工": "周期",
    "公用事业": "周期",
    "交通运输": "周期",
    "房地产": "周期",
    "综合": "周期",
}

# 可配置的板块场景模板
DEFAULT_SECTOR_SCENARIOS = {
    "科技板块回调20%": {
        "sector": "科技",
        "callback_pct": 0.20,
    },
}


# ============================================================================
# 场景数据类与预定义实例
# ============================================================================
@dataclass(frozen=True)
class StressScenario:
    """压力测试场景定义。"""

    id: str
    name: str
    type: Literal["historical", "sector"]
    params: Dict = field(default_factory=dict)
    description: str = ""


HISTORICAL_SCENARIOS: List[StressScenario] = [
    StressScenario(
        id=name,
        name=name,
        type="historical",
        params=params,
        description=f"历史场景：{name}（{params['start_date']} ~ {params['end_date']}）",
    )
    for name, params in EXTREME_SCENARIOS.items()
]

SECTOR_SCENARIOS: List[StressScenario] = [
    StressScenario(
        id=name,
        name=name,
        type="sector",
        params=params,
        description=f"板块场景：{params['sector']}板块回调 {params['callback_pct'] * 100:.0f}%",
    )
    for name, params in DEFAULT_SECTOR_SCENARIOS.items()
]

# 预定义场景 id -> 场景对象的映射
ALL_SCENARIO_MAP: Dict[str, StressScenario] = {
    s.id: s for s in (HISTORICAL_SCENARIOS + SECTOR_SCENARIOS)
}


# ============================================================================
# 场景工厂函数
# ============================================================================
def list_available_scenarios() -> List[Dict]:
    """返回前端可用的场景列表。"""
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "description": s.description,
            "params": s.params,
        }
        for s in (HISTORICAL_SCENARIOS + SECTOR_SCENARIOS)
    ]


def build_scenarios(selection: Optional[List[str]] = None) -> List[StressScenario]:
    """
    根据用户选择的场景 id 列表构造场景对象列表。

    参数
    ----------
    selection : List[str], optional
        场景 id 列表。为空时返回空列表；为 None 时返回全部预定义场景。

    返回
    -------
    List[StressScenario]
    """
    if selection is None:
        return HISTORICAL_SCENARIOS + SECTOR_SCENARIOS

    scenarios = []
    for sid in selection:
        scenario = ALL_SCENARIO_MAP.get(sid)
        if scenario is not None:
            scenarios.append(scenario)
    return scenarios


def make_sector_scenario(
    sector: str = "科技",
    callback_pct: float = DEFAULT_SECTOR_CALLBACK_PCT,
) -> StressScenario:
    """
    动态构造板块压力场景。

    参数
    ----------
    sector : str
        板块桶名，需在 SECTOR_BETAS 中存在。
    callback_pct : float
        回调幅度，例如 0.20 表示 20%。

    返回
    -------
    StressScenario
    """
    if sector not in SECTOR_BETAS:
        raise ValueError(
            f"未知板块桶：{sector}。支持的板块：{list(SECTOR_BETAS.keys())}"
        )

    name = f"{sector}板块回调{callback_pct * 100:.0f}%"
    return StressScenario(
        id=name,
        name=name,
        type="sector",
        params={"sector": sector, "callback_pct": callback_pct},
        description=f"板块场景：{sector}板块回调 {callback_pct * 100:.0f}%",
    )

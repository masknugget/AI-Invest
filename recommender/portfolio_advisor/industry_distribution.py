import logging
from decimal import Decimal
from typing import Dict, List

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def merge_and_sum_decimal(dict_list: List[Dict[str, float]]) -> Dict[str, float]:
    """
    合并多个行业/字典数据，对相同 key 的数值以 Decimal 精度累加后返回 float 结果。

    Args:
        dict_list: 由多个 {key: value} 字典组成的列表。

    Returns:
        Dict[str, float]: 合并并累加后的字典。
    """
    result: Dict[str, Decimal] = {}

    for d in dict_list:
        for key, value in d.items():
            # 统一转为 Decimal 累加，避免浮点精度误差
            v = Decimal(str(value))
            result[key] = result.get(key, Decimal(0)) + v

    logger.info("merge_and_sum_decimal: merged %d dicts into %d keys", len(dict_list), len(result))

    # 返回时转回 float，便于后续展示与序列化
    return {k: float(v) for k, v in result.items()}

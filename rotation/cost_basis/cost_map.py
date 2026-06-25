"""
rotation/cost_basis/cost_map.py — 成本密度映射 + 三类区域定义
"""
from typing import Dict

def classify_cost_zones(profile: Dict, concentration: Dict) -> Dict:
    """
    将成本结构映射为三类区域
    
    Returns:
        {
            "cost_dense": {...},       # 筹码密集区
            "support_zone": {...},     # 支撑区
            "resistance_zone": {...},  # 压力区
        }
    """
    cd = concentration.get("cost_dense_zone", {})
    support = concentration.get("support", {})
    resistance = concentration.get("resistance", {})
    current = profile.get("current_price", 0)
    vwap = profile.get("weighted_avg_cost", 0)
    
    zones = {
        "cost_dense": {
            "range": [cd.get("low", 0), cd.get("high", 0)],
            "total_density": cd.get("total_density", 0),
            "label": "筹码密集区",
        },
        "support_zone": {
            "price": support.get("mid_price", support.get("price_low", 0)) if support else None,
            "label": "支撑区" if support else "无显著支撑",
        },
        "resistance_zone": {
            "price": resistance.get("mid_price", resistance.get("price_low", 0)) if resistance else None,
            "label": "压力区" if resistance else "无显著压力",
        },
        "vwap": vwap,
        "position_status": _classify_position(current, vwap, cd),
    }
    
    return zones


def _classify_position(current_price: float, vwap: float, cost_dense: Dict) -> str:
    """判断当前价 vs 成本区的位置"""
    if not cost_dense or not cost_dense.get("low"):
        return "unknown"
    
    low = cost_dense["low"]
    high = cost_dense["high"]
    
    if current_price < low:
        return "below_cost"       # 在成本下方 — 潜在反弹
    elif low <= current_price <= high:
        return "in_cost_zone"     # 在密集区 — 震荡
    else:
        return "above_cost"       # 在成本上方 — 趋势运行

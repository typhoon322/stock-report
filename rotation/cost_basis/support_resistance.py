"""
rotation/cost_basis/support_resistance.py — 支撑/阻力识别

support = 当前价下方高成交量区
resistance = 当前价上方高成交量区
"""
from typing import Dict, List, Optional


def identify_sr_levels(profile: Dict) -> Dict:
    """
    从 Volume Profile 识别关键支撑阻力位
    
    返回: {"support_levels": [...], "resistance_levels": [...], "key_sr"}
    """
    bins = profile.get("bins", [])
    current_price = profile.get("current_price", 0)
    avg_density = sum(b["density"] for b in bins) / max(len(bins), 1)
    
    supports = []
    resistances = []
    
    for b in bins:
        mid = b["mid_price"]
        # 显著高成交量 (>1.2倍均值) + 有一定密度
        if b["density"] > avg_density * 1.2 and b["density"] > 0.02:
            if mid < current_price:
                supports.append({
                    "price": mid,
                    "density": b["density"],
                    "volume": b["volume"],
                    "strength": round(b["density"] / avg_density, 2),
                })
            elif mid > current_price:
                resistances.append({
                    "price": mid,
                    "density": b["density"],
                    "volume": b["volume"], 
                    "strength": round(b["density"] / avg_density, 2),
                })
    
    # 排序: 支撑由近到远, 阻力由近到远
    supports.sort(key=lambda x: x["price"], reverse=True)
    resistances.sort(key=lambda x: x["price"])
    
    # 关键SR
    key_support = supports[0] if supports else None
    key_resistance = resistances[0] if resistances else None
    
    return {
        "support_levels": supports[:3],
        "resistance_levels": resistances[:3],
        "key_support": key_support,
        "key_resistance": key_resistance,
        "sr_ratio": round(
            (key_resistance["price"] - current_price) / max(current_price - key_support["price"], 0.01), 2
        ) if key_support and key_resistance else None,
    }

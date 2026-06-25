"""
rotation/cost_basis/position_estimator.py — 持仓区推断

判断当前价在成本结构中的位置: below_cost / in_cost_zone / above_cost
"""
from typing import Dict


def estimate_position(profile: Dict, concentration: Dict) -> Dict:
    """
    推断当前价格位置
    
    Returns:
        {
            "status": "above_cost",
            "interpretation": str,
            "trade_bias": str,
            "risk": str,
        }
    """
    current = profile.get("current_price", 0)
    vwap = profile.get("weighted_avg_cost", 0)
    cost_dense = concentration.get("cost_dense_zone", {})
    support = concentration.get("support", {})
    resistance = concentration.get("resistance", {})
    
    low = cost_dense.get("low", vwap * 0.95)
    high = cost_dense.get("high", vwap * 1.05)
    
    # 位置判断
    if current < low:
        gap_pct = (low - current) / current * 100 if current > 0 else 0
        return {
            "status": "below_cost",
            "gap_pct": round(gap_pct, 1),
            "interpretation": f"价格在筹码密集区下方{gap_pct:.1f}%，潜在反弹机会",
            "trade_bias": "bullish_reversal" if support else "neutral",
            "risk": "low — 下方空间有限",
            "vwap_position": "below" if current < vwap else "above",
        }
    
    elif low <= current <= high:
        return {
            "status": "in_cost_zone",
            "interpretation": "价格在筹码密集区内，大概率震荡",
            "trade_bias": "range_trading",
            "risk": "medium — 方向不明确",
            "vwap_position": "at_vicinity",
        }
    
    else:
        gap_pct = (current - high) / high * 100 if high > 0 else 0
        has_resistance = resistance is not None
        return {
            "status": "above_cost",
            "gap_pct": round(gap_pct, 1),
            "interpretation": f"价格在筹码密集区上方{gap_pct:.1f}%，趋势运行中" + 
                ("，注意上方压力" if has_resistance else "，压力较轻"),
            "trade_bias": "bullish_continuation" if not has_resistance else "cautious_long",
            "risk": "low" if not has_resistance else "medium — 存在上方套牢盘",
            "vwap_position": "above",
        }


def estimate_float_status(profile: Dict) -> Dict:
    """估算筹码浮动状态"""
    current = profile.get("current_price", 0)
    vwap = profile.get("weighted_avg_cost", 0)
    
    if vwap == 0:
        return {"status": "unknown"}
    
    gain_pct = (current - vwap) / vwap * 100
    
    if gain_pct > 15:
        status = "highly_profitable — 大量浮盈，获利盘压力"
    elif gain_pct > 5:
        status = "moderate_profit — 有一定浮盈"
    elif gain_pct > -5:
        status = "near_breakeven — 筹码集中，方向待选"
    elif gain_pct > -15:
        status = "underwater — 深套，割肉盘压力小"
    else:
        status = "deep_underwater — 极度深套，几乎无卖压"
    
    return {
        "status": status,
        "gain_pct": round(gain_pct, 1),
        "vwap": vwap,
        "current": current,
    }

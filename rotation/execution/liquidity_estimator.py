"""
rotation/execution/liquidity_estimator.py — 流动性估计

liquidity_score = volume × turnover ÷ volatility
"""
from typing import Dict


def estimate_liquidity(
    daily_volume: float,       # 日成交额 (亿)
    turnover_rate: float = 3.0, # 换手率 (%)
    volatility: float = 0.02,   # 波动率
    market_cap: float = 100,    # 市值 (亿)
) -> Dict:
    """
    估计市场流动性
    
    Returns: liquidity_score (0-1) + classification
    """
    # 基础流动分 (0-1)
    vol_score = min(daily_volume / 20, 1.0)  # 20亿以上 → 满分
    turnover_score = min(turnover_rate / 5, 1.0)
    
    # 波动率惩罚
    vol_penalty = min(volatility * 20, 0.6)
    
    raw_score = vol_score * 0.4 + turnover_score * 0.3 + max(0, 1 - vol_penalty) * 0.3
    
    # 市值加权
    cap_bonus = min(market_cap / 500, 0.2)
    raw_score += cap_bonus
    
    score = min(raw_score, 1.0)
    
    if score > 0.7:
        classification = "high"
        method = "market_order"
        max_single_pct = 0.30
    elif score > 0.4:
        classification = "medium"
        method = "TWAP"
        max_single_pct = 0.15
    else:
        classification = "low"
        method = "VWAP_limits"
        max_single_pct = 0.05
    
    return {
        "liquidity_score": round(score, 3),
        "classification": classification,
        "recommended_method": method,
        "max_single_order_pct": max_single_pct,
        "components": {
            "volume_score": round(vol_score, 3),
            "turnover_score": round(turnover_score, 3),
            "volatility_penalty": round(vol_penalty, 3),
            "cap_bonus": round(cap_bonus, 3),
        },
    }

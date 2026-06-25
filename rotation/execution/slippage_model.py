"""
rotation/execution/slippage_model.py — 滑点模型

slippage = volatility × order_size_ratio ÷ liquidity
"""
from typing import Dict


def estimate_slippage(
    volatility: float,           # 波动率 (0.02 = 2%)
    position_size: float,        # 仓位比例 (0-1)
    liquidity_score: float,      # 流动性评分 (0-1)
    order_type: str = "market",  # market / TWAP / limit
    spread_pct: float = 0.001,   # bid-ask spread
) -> Dict:
    """
    估计执行滑点
    
    Returns: estimated_slippage (百分比) + components
    """
    # 基础滑点: 波动率 × 仓位 / 流动性
    if liquidity_score > 0.01:
        base_slippage = volatility * position_size / liquidity_score * 100
    else:
        base_slippage = volatility * position_size * 100
    
    # 订单类型调整
    type_multiplier = {
        "market": 1.0,
        "TWAP": 0.6,
        "VWAP_limits": 0.3,
        "limit": 0.2,
    }
    mult = type_multiplier.get(order_type, 1.0)
    
    # spread 加成
    spread_impact = spread_pct * 50  # ~0.05%
    
    total_slippage = base_slippage * mult + spread_impact
    
    # 冲击成本: 仓位越大，冲击越大
    impact = position_size ** 1.5 * volatility * 100 / max(liquidity_score, 0.1)
    impact *= type_multiplier.get("market", 1.0) * 0.3
    
    total_slippage += impact
    
    return {
        "estimated_slippage_pct": round(total_slippage, 3),
        "base_slippage": round(base_slippage, 3),
        "impact_cost": round(impact, 3),
        "spread_cost": round(spread_impact, 3),
        "order_type_multiplier": mult,
        "severity": "high" if total_slippage > 0.5 else ("medium" if total_slippage > 0.15 else "low"),
    }

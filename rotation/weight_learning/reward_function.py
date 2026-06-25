"""
rotation/weight_learning/reward_function.py — 收益归因

reward = signal_contribution_to_pnl
"""
from typing import Dict, List
import math


def compute_reward(pnl: float, transaction_cost: float = 0.002) -> float:
    """净收益 = PnL - 交易成本"""
    return round(pnl - transaction_cost, 4)


def attribute_contribution(
    signals: Dict[str, float],
    weights: Dict[str, float],
    pnl: float,
) -> Dict[str, float]:
    """
    将PnL归因到各模块
    
    contribution_i = weight_i × signal_i × pnl / Σ(weight × signal)
    """
    total = sum(signals.get(k, 0) * weights.get(k, 0.1) for k in weights)
    if total == 0:
        return {k: 0.0 for k in weights}
    
    contributions = {}
    for k in weights:
        sig = signals.get(k, 0)
        w = weights.get(k, 0.1)
        contributions[k] = round(w * max(sig, 0) * pnl / total * 100, 4)  # bps
    
    return contributions

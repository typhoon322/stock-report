"""
rotation/position/portfolio_guard.py — 风控限制

硬约束: 最大仓位/breakout风险/flow反向/单策略集中度
"""
from typing import Dict


def apply_guards(
    position_size: float,
    meta_score: float,
    flow_direction: float,
    breakout_classification: str,
    regime: str,
) -> Dict:
    """
    应用风控硬约束
    
    Returns: adjusted_position + guard_log
    """
    original = position_size
    guards = []
    
    # Guard 1: regime 最大仓位
    regime_caps = {
        "risk_off": 0.20,
        "distribution": 0.30,
        "choppy": 0.60,
        "rotation": 0.80,
        "trend_up": 1.00,
        "inflow_strong": 1.00,
    }
    cap = regime_caps.get(regime, 0.80)
    if position_size > cap:
        guards.append({"guard": "regime_cap", "cap": cap, "action": f"降至 {cap:.0%}"})
        position_size = min(position_size, cap)
    
    # Guard 2: Breakout 风险
    if breakout_classification == "liquidity_trap":
        guards.append({"guard": "liquidity_trap", "action": "仓位×0.3"})
        position_size *= 0.3
    elif breakout_classification == "failed_breakout":
        guards.append({"guard": "failed_breakout", "action": "仓位×0.5"})
        position_size *= 0.5
    
    # Guard 3: Flow 反向保护
    if flow_direction < -0.3 and meta_score > 0:
        guards.append({"guard": "flow_reversal", "action": "仓位≤30%"})
        position_size = min(position_size, 0.30)
    
    # Guard 4: 极端信号保护
    if position_size > 0.95:
        guards.append({"guard": "max_cap", "action": "仓位上限95%"})
        position_size = 0.95
    
    adjusted = round(max(0.0, position_size), 3)
    
    return {
        "original_size": round(original, 3),
        "adjusted_size": adjusted,
        "guards_applied": len(guards),
        "guard_log": guards,
    }

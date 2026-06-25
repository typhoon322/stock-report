"""
rotation/meta/signal_hub.py — 信号汇总中心

收拢所有子系统的信号，统一输出标准化字典
"""
from typing import Dict


def collect_signals(
    rti_signal: int = 0,
    rti_confidence: float = 0.5,
    flow_direction: float = 0.0,
    flow_regime: str = "neutral",
    smart_money_behavior: str = "neutral",
    smart_money_score: float = 0.0,
    cost_position: str = "mid",
    cost_absorption: float = 0.0,
    breakout_classification: str = "none",
    breakout_score: float = 0.0,
    mtf_score: int = 0,
    mtf_status: str = "divergent",
    phase: str = "",
) -> Dict:
    """
    收集所有子系统信号 → 标准化字典
    
    所有信号归一化到 -1~+1:
      +1 = 强烈看多
       0 = 中性
      -1 = 强烈看空
    """
    signals = {
        "rti": 0.0,
        "flow": 0.0,
        "smart_money": 0.0,
        "cost_basis": 0.0,
        "breakout": 0.0,
        "mtf": 0.0,
    }
    
    # 1. RTI → -1~+1
    if rti_signal > 0:
        signals["rti"] = min(rti_confidence, 1.0)
    elif rti_signal < 0:
        signals["rti"] = -min(rti_confidence, 1.0)
    
    # 2. Flow → -1~+1
    signals["flow"] = max(-1.0, min(flow_direction, 1.0))
    
    # 3. Smart Money → -1~+1
    sm_map = {
        "markup": 1.0,
        "accumulation": 0.5,
        "accumulation_bias": 0.3,
        "neutral": 0.0,
        "distribution_bias": -0.3,
        "distribution": -0.8,
        "manipulation": -0.2,
    }
    signals["smart_money"] = sm_map.get(smart_money_behavior, 0.0)
    if smart_money_score > 0.7 and smart_money_behavior == "markup":
        signals["smart_money"] = 1.0
    elif smart_money_score > 0.7 and smart_money_behavior == "distribution":
        signals["smart_money"] = -1.0
    
    # 4. Cost Basis → -1~+1
    cb_map = {"above_cost": 0.5, "in_cost_zone": 0.0, "below_cost": -0.3}
    signals["cost_basis"] = cb_map.get(cost_position, 0.0)
    if cost_absorption > 0.5:
        signals["cost_basis"] += 0.3
    elif cost_absorption < -0.5:
        signals["cost_basis"] -= 0.3
    signals["cost_basis"] = max(-1.0, min(signals["cost_basis"], 1.0))
    
    # 5. Breakout → -1~+1
    brk_map = {
        "genuine_breakout": 1.0,
        "suspicious_breakout": 0.3,
        "failed_breakout": -0.5,
        "liquidity_trap": -1.0,
        "none": 0.0,
    }
    signals["breakout"] = brk_map.get(breakout_classification, 0.0)
    
    # 6. MTF → -1~+1
    signals["mtf"] = mtf_score / 3.0  # Normalize -3~+3 to -1~+1
    
    # Metadata
    meta = {
        "flow_regime": flow_regime,
        "smart_money_behavior": smart_money_behavior,
        "phase": phase,
        "mtf_status": mtf_status,
    }
    
    return {"signals": signals, "meta": meta}

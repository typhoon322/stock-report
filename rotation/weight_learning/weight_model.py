"""
rotation/weight_learning/weight_model.py — 权重学习模型

weight_i ∝ correlation(signal_i, future_return)
"""
from typing import Dict, List
from .signal_tracker import load_records, get_signal_performance


# Regime-based weight modifiers
REGIME_MODIFIERS = {
    "trend": {
        "rti": 1.0, "flow": 1.3, "smart_money": 0.9,
        "cost_basis": 0.8, "breakout": 1.0, "mtf": 0.7,
    },
    "rotation": {
        "rti": 1.3, "flow": 1.1, "smart_money": 1.0,
        "cost_basis": 1.0, "breakout": 0.9, "mtf": 0.9,
    },
    "choppy": {
        "rti": 0.7, "flow": 0.7, "smart_money": 1.0,
        "cost_basis": 1.2, "breakout": 0.6, "mtf": 1.4,
    },
    "risk_off": {
        "rti": 0.4, "flow": 0.4, "smart_money": 1.5,
        "cost_basis": 1.1, "breakout": 0.3, "mtf": 1.2,
    },
}


def learn_weights(regime: str = "rotation") -> Dict[str, float]:
    """
    从历史交易记录学习权重
    
    weight_i ∝ effect_i × regime_modifier_i
    """
    perf = get_signal_performance()
    modifiers = REGIME_MODIFIERS.get(regime, REGIME_MODIFIERS["rotation"])
    
    if not perf:
        return default_weights(regime)
    
    # 每个信号的有效性 = win_rate × avg_pnl × regime_modifier
    weights = {}
    total = 0.0
    for module, stats in perf.items():
        effectiveness = stats["win_rate"] * max(stats["avg_pnl"] * 50, 0.01)  # scale PnL
        modifier = modifiers.get(module, 1.0)
        w = max(0.01, effectiveness * modifier)
        weights[module] = w
        total += w
    
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    
    return weights


def default_weights(regime: str = "rotation") -> Dict[str, float]:
    """带regime的默认权重"""
    modifiers = REGIME_MODIFIERS.get(regime, REGIME_MODIFIERS["rotation"])
    base = {"rti": 0.22, "flow": 0.22, "smart_money": 0.18, "cost_basis": 0.14, "breakout": 0.14, "mtf": 0.10}
    
    adjusted = {}
    total = 0.0
    for k, v in base.items():
        w = v * modifiers.get(k, 1.0)
        adjusted[k] = w
        total += w
    return {k: round(v / total, 4) for k, v in adjusted.items()}

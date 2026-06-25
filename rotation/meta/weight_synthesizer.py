"""
rotation/meta/weight_synthesizer.py — 动态权重合成

基础权重 + 市场状态动态调整
"""
from typing import Dict

# 基础权重
BASE_WEIGHTS = {
    "rti": 0.20,
    "flow": 0.20,
    "smart_money": 0.20,
    "cost_basis": 0.15,
    "breakout": 0.15,
    "mtf": 0.10,
}

# 市场状态权重修正
REGIME_WEIGHT_MATRIX = {
    "trend_up": {
        "rti": 1.10, "flow": 1.30, "smart_money": 0.90,
        "cost_basis": 0.90, "breakout": 1.10, "mtf": 0.80,
    },
    "rotation": {
        "rti": 1.30, "flow": 1.10, "smart_money": 1.00,
        "cost_basis": 1.00, "breakout": 0.90, "mtf": 0.90,
    },
    "choppy": {
        "rti": 0.80, "flow": 0.90, "smart_money": 1.00,
        "cost_basis": 1.10, "breakout": 0.80, "mtf": 1.30,
    },
    "risk_off": {
        "rti": 0.50, "flow": 0.50, "smart_money": 1.50,
        "cost_basis": 1.10, "breakout": 0.50, "mtf": 1.00,
    },
    # Flow regime overrides
    "inflow_strong": {
        "rti": 1.20, "flow": 1.40, "smart_money": 0.90,
        "cost_basis": 1.00, "breakout": 1.10, "mtf": 0.80,
    },
    "distribution": {
        "rti": 0.50, "flow": 0.40, "smart_money": 1.60,
        "cost_basis": 1.20, "breakout": 0.50, "mtf": 1.10,
    },
}


def synthesize_weights(market_regime: str = "rotation", flow_regime: str = "neutral") -> Dict[str, float]:
    """
    动态合成权重
    
    优先级: market_regime → flow_regime override → base
    """
    weights = dict(BASE_WEIGHTS)
    
    # Apply market regime
    regime_mult = REGIME_WEIGHT_MATRIX.get(market_regime, {})
    for k in weights:
        weights[k] *= regime_mult.get(k, 1.0)
    
    # Apply flow regime (overrides market)
    if flow_regime in ("inflow_strong", "distribution"):
        flow_mult = REGIME_WEIGHT_MATRIX.get(flow_regime, {})
        for k in weights:
            weights[k] = BASE_WEIGHTS[k] * flow_mult.get(k, 1.0)
    
    # Normalize
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 3) for k, v in weights.items()}
    
    return weights

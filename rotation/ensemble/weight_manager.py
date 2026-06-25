"""
rotation/ensemble/weight_manager.py — 动态权重管理

不同模型在不同市场 regime 下权重不同
weight = historical_IC_in_regime × recent_stability × inverse_drawdown
"""
from typing import Dict, List
from .model_pool import build_ensemble_pool


# 预设 regime 权重 (基于一般经验，可由优化器调整)
REGIME_WEIGHTS = {
    "trend_up": {
        "RTI": 0.40,  # 轮动模型在主升期权重高
        "BSI": 0.30,
        "LS":  0.30,
        "rule": 0.25,
        "ML": 0.40,
    },
    "rotation": {
        "RTI": 0.45,
        "BSI": 0.20,
        "LS":  0.25,
        "rule": 0.30,
        "ML": 0.35,
    },
    "choppy": {
        "RTI": 0.20,
        "BSI": 0.30,
        "LS":  0.15,
        "rule": 0.20,
        "ML": 0.15,
    },
    "risk_off": {
        "RTI": 0.15,
        "BSI": 0.20,
        "LS":  0.10,
        "rule": 0.15,
        "ML": 0.10,
    },
}


def compute_dynamic_weights(
    model_pool: List[Dict],
    regime: str,
    market_volatility: float = 1.0,
) -> Dict[str, float]:
    """
    为模型池中每个模型计算在当前 regime 下的动态权重
    
    Args:
        model_pool: [{"name": str, "type": str, "ic": float, "stability": float, ...}, ...]
        regime: trend_up / rotation / choppy / risk_off
        market_volatility: 市场波动率 (高波动 → 降低ML权重)
    
    Returns:
        {model_name: weight}
    """
    regime_w = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["choppy"])
    weights = {}
    total = 0.0
    
    for m in model_pool:
        m_type = m.get("type", "rule")
        base = regime_w.get(m_type, 0.20)
        
        # 质量调整
        quality = m.get("stability", 0.5)
        ic_bonus = min(m.get("ic", 0) * 3, 0.3)
        
        w = base * (0.7 + quality * 0.3) + ic_bonus
        
        # 高波动时降低权重
        if market_volatility > 1.5:
            w *= 0.7
        
        weights[m["name"]] = w
        total += w
    
    # 归一化
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    
    return weights

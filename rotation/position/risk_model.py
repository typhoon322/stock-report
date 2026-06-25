"""
rotation/position/risk_model.py — 风险建模

基于波动率 + 市场状态计算风险因子 (0-1, 越低越危险)
"""
from typing import Dict


def compute_risk_factor(
    volatility: float,           # 市场波动率 (如 0.02 = 2%)
    max_drawdown: float = 0.0,   # 最大回撤
    regime: str = "rotation",    # 市场状态
    mtf_score: int = 0,          # MTF一致性
) -> Dict:
    """
    计算风险因子
    
    risk_factor = 1.0 - volatility_weight - drawdown_weight - regime_penalty
    0.0 = 极度危险(不交易), 1.0 = 无风险
    """
    # 波动率惩罚 (vol > 5% → 强惩罚)
    vol_penalty = min(volatility * 15, 0.5)
    
    # 回撤惩罚
    dd_penalty = min(max_drawdown * 0.5, 0.3)
    
    # Regime 惩罚
    regime_map = {
        "risk_off": 0.3,
        "distribution": 0.25,
        "choppy": 0.10,
        "rotation": 0.05,
        "trend_up": 0.0,
        "inflow_strong": 0.0,
    }
    regime_penalty = regime_map.get(regime, 0.10)
    
    # MTF 调整 (-3~+3 → -0.15~+0.15)
    mtf_factor = mtf_score * 0.05
    
    risk_factor = 1.0 - vol_penalty - dd_penalty - regime_penalty + mtf_factor
    risk_factor = max(0.1, min(risk_factor, 1.0))  # Floor at 10%
    
    return {
        "risk_factor": round(risk_factor, 3),
        "volatility_penalty": round(vol_penalty, 3),
        "drawdown_penalty": round(dd_penalty, 3),
        "regime_penalty": round(regime_penalty, 3),
        "mtf_adjustment": round(mtf_factor, 3),
        "risk_level": "low" if risk_factor > 0.7 else ("medium" if risk_factor > 0.4 else "high"),
    }

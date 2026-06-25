"""
rotation/model_selector/model_score.py — 模型评分系统

给每个模型打"适配当前市场"的分数
Score = 历史IC_in_regime + precision_in_regime + stability - drawdown_penalty
"""
from typing import Dict, List
from .regime_detector import Regime


def compute_model_score(
    model_ic: float,
    model_precision: float,
    model_stability: float,
    model_max_dd: float,
    regime: str,
    regime_match_bonus: float = 0.0,
) -> float:
    """
    计算模型在当前市场状态下的适配分数
    
    regime_match_bonus: 该模型在此regime下的历史超额 (如果有)
    """
    score = 0.0
    
    # 1. IC 权重 (0-40)
    score += min(model_ic * 400, 40)
    
    # 2. Precision (0-25)
    score += model_precision * 25
    
    # 3. 稳定性 (0-20)
    score += model_stability * 20
    
    # 4. 回撤惩罚 (0-10, 越小越好)
    dd_penalty = min(model_max_dd * 40, 10)
    score += (10 - dd_penalty)
    
    # 5. Regime 匹配加分 (0-5)
    score += regime_match_bonus * 5
    
    return round(score, 2)


def compute_regime_match_bonus(
    model_regime_performance: Dict[str, float],  # {regime: avg_ic}
    current_regime: str,
) -> float:
    """该模型在当前regime下的历史表现加分"""
    if current_regime in model_regime_performance:
        return model_regime_performance[current_regime]
    return 0.0


def score_all_models(
    models: List[Dict],
    current_regime: str,
) -> List[Dict]:
    """
    给模型池所有模型评分
    
    Args:
        models: [{"version": str, "ic": float, "precision_top10": float, ...}, ...]
        current_regime: trend_up / rotation / choppy / risk_off
    
    Returns:
        带分数的模型列表 (降序)
    """
    scored = []
    for m in models:
        score = compute_model_score(
            model_ic=m.get("ic", 0),
            model_precision=m.get("precision_top10", 0),
            model_stability=m.get("stability_score", 0.5),
            model_max_dd=m.get("max_drawdown", 0.15),
            regime=current_regime,
            regime_match_bonus=compute_regime_match_bonus(
                m.get("regime_performance", {}), current_regime
            ),
        )
        scored.append({**m, "regime_score": score, "regime": current_regime})
    
    return sorted(scored, key=lambda x: x["regime_score"], reverse=True)

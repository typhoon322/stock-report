"""
rotation/validation/metric_tracker.py — 指标统计

对比 baseline vs ablated 的性能差异
"""
from typing import Dict, List


def compute_metrics(signals: Dict[str, float], weights: Dict[str, float] = None) -> Dict:
    """
    从信号计算模拟指标
    
    简化的性能代理: weighted_signal × (1 - penalty)
    """
    if weights is None:
        weights = {k: 1.0/len(signals) for k in signals}
    
    weighted_score = sum(signals.get(k, 0) * weights.get(k, 1.0/len(signals)) 
                         for k in signals)
    total_weight = sum(weights.get(k, 1.0/len(signals)) for k in signals)
    score = weighted_score / max(total_weight, 0.01)
    
    # 代理指标
    entry_count = sum(1 for v in signals.values() if v > 0.3)
    
    return {
        "meta_score": round(score, 4),
        "active_modules": sum(1 for v in signals.values() if abs(v) > 0.01),
        "entry_signals": entry_count,
        # 简化的收益/风险代理
        "return_proxy": round(max(0, score) * 0.15, 3),     # 正信号→正收益
        "drawdown_proxy": round(max(0, -score) * 0.10, 3),  # 负信号→回撤
        "sharpe_proxy": round(score * 2.0, 3) if score > 0 else 0,
    }


def compare_configs(baseline_metrics: Dict, ablated_metrics: Dict, config_name: str) -> Dict:
    """
    对比基线 vs 消融的性能差异
    
    Returns: delta + contribution score
    """
    base_ret = baseline_metrics.get("return_proxy", 0)
    ablate_ret = ablated_metrics.get("return_proxy", 0)
    base_sharpe = baseline_metrics.get("sharpe_proxy", 0)
    ablate_sharpe = ablated_metrics.get("sharpe_proxy", 0)
    
    delta_return = round(base_ret - ablate_ret, 4)
    delta_sharpe = round(base_sharpe - ablate_sharpe, 4)
    
    # 贡献度: delta > 0 → 该模块有正贡献
    contribution = round(delta_return * 100, 2)  # 转为基点的感觉
    
    return {
        "config": config_name,
        "baseline_return": base_ret,
        "ablated_return": ablate_ret,
        "delta_return": delta_return,
        "delta_sharpe": delta_sharpe,
        "contribution_bps": contribution,
        "verdict": "positive" if contribution > 0.5 else ("neutral" if abs(contribution) <= 0.5 else "negative"),
    }

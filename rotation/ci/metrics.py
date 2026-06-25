"""
rotation/ci/metrics.py — 统一指标计算
"""
from typing import Dict, List
import numpy as np
import math


def compute_ic(predictions: List[float], returns: List[float]) -> float:
    """Information Coefficient (预测值与实际收益的秩相关)"""
    if len(predictions) < 5:
        return 0.0
    try:
        from scipy.stats import spearmanr
        ic, _ = spearmanr(predictions, returns)
        return round(float(ic), 4)
    except:
        # 用 numpy 近似
        pred_rank = np.argsort(np.argsort(predictions))
        ret_rank = np.argsort(np.argsort(returns))
        n = len(predictions)
        ic = 1 - 6 * sum((pred_rank - ret_rank)**2) / (n * (n**2 - 1))
        return round(float(ic), 4)


def precision_at_topk(predictions: List[float], labels: List[int], k: float = 0.1) -> float:
    """Precision @ Top K%"""
    n = len(predictions)
    if n == 0:
        return 0.0
    top_k = max(1, int(n * k))
    top_idx = np.argsort(predictions)[-top_k:]
    if len(top_idx) == 0:
        return 0.0
    hits = sum(labels[i] for i in top_idx)
    return round(hits / len(top_idx), 4)


def recall_main_theme(predictions: List[float], labels: List[int], threshold: float = 0.5) -> float:
    """主线捕捉率"""
    total_pos = sum(labels)
    if total_pos == 0:
        return 0.0
    predicted_pos = sum(1 for i in range(len(predictions)) if predictions[i] >= threshold)
    true_pos = sum(1 for i in range(len(predictions)) 
                   if predictions[i] >= threshold and labels[i] == 1)
    return round(true_pos / total_pos, 4)


def hit_rate(predictions: List[float], labels: List[int], threshold: float = 0.5) -> float:
    """命中率 (预测为正的样本中实际为正的比例)"""
    predicted_pos = sum(1 for p in predictions if p >= threshold)
    if predicted_pos == 0:
        return 0.0
    hits = sum(1 for i in range(len(predictions)) if predictions[i] >= threshold and labels[i] == 1)
    return round(hits / predicted_pos, 4)


def sharpe_proxy(returns: List[float]) -> float:
    """近似夏普比率"""
    if len(returns) < 2:
        return 0.0
    avg = np.mean(returns)
    std = np.std(returns)
    return round(float(avg / max(std, 0.0001)), 4)


def max_drawdown(returns: List[float]) -> float:
    """最大回撤"""
    if not returns:
        return 0.0
    cumulative = np.cumsum(returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / np.maximum(peak, 0.0001)
    return round(float(np.max(drawdown)), 4)


def return_over_benchmark(strategy_returns: List[float], benchmark_returns: List[float]) -> float:
    """超额收益"""
    if not strategy_returns:
        return 0.0
    strategy_total = sum(strategy_returns)
    benchmark_total = sum(benchmark_returns) if benchmark_returns else 0
    return round(strategy_total - benchmark_total, 4)


def compute_all_metrics(
    predictions: List[float],
    labels: List[int],
    returns: List[float],
    benchmark_returns: List[float] = None,
) -> Dict:
    """一站式计算所有指标"""
    if benchmark_returns is None:
        benchmark_returns = [0.0] * len(returns)
    
    return {
        "IC": compute_ic(predictions, returns),
        "precision_top10": precision_at_topk(predictions, labels, 0.1),
        "precision_top5": precision_at_topk(predictions, labels, 0.05),
        "recall_main_theme": recall_main_theme(predictions, labels),
        "hit_rate": hit_rate(predictions, labels),
        "sharpe_proxy": sharpe_proxy(returns),
        "max_drawdown": max_drawdown(returns),
        "return_over_benchmark": return_over_benchmark(returns, benchmark_returns),
    }

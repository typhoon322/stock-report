"""
rotation/ensemble/signal_aggregator.py — 信号聚合

多模型信号 → 统一投票分数
"""
from typing import Dict, List, Tuple
import numpy as np
from .model_pool import ModelSignal


def aggregate_signals(
    signals: List[ModelSignal],
    weights: Dict[str, float] = None,
) -> Tuple[float, float, str]:
    """
    聚合多模型信号
    
    Returns: (weighted_score, agreement_ratio, decision)
    weighted_score: -1.0 ~ 1.0
    agreement_ratio: 0~1 (模型一致性)
    decision: "LONG" / "SHORT" / "HOLD"
    """
    if not signals:
        return 0.0, 0.0, "HOLD"
    
    total_weight = 0.0
    weighted_sum = 0.0
    signals_list = []
    
    for s in signals:
        w = weights.get(s.model_name, 1.0 / len(signals)) if weights else 1.0 / len(signals)
        weighted_sum += w * s.signal * s.confidence
        total_weight += w
        signals_list.append(s.signal)
    
    score = weighted_sum / max(total_weight, 0.001)
    
    # 一致率: 多少模型同向
    if signals_list:
        majority = 1 if sum(signals_list) > 0 else (-1 if sum(signals_list) < 0 else 0)
        agreement = sum(1 for s in signals_list if s == majority or s == 0) / len(signals_list)
    else:
        agreement = 0.0
    
    # 决策
    if score > 0.30:
        decision = "LONG"
    elif score < -0.30:
        decision = "SHORT"
    else:
        decision = "HOLD"
    
    return round(score, 4), round(agreement, 4), decision


def compute_signal_entropy(signals: List[ModelSignal]) -> float:
    """信号熵 (越低越一致)"""
    if not signals:
        return 0.0
    counts = {"LONG": 0, "HOLD": 0, "SHORT": 0}
    for s in signals:
        counts[s.to_dict()["signal_label"]] += 1
    n = len(signals)
    entropy = 0.0
    for c in counts.values():
        if c > 0:
            p = c / n
            entropy -= p * np.log2(p)
    return round(entropy, 4)

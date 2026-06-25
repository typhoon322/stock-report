"""
rotation/meta/meta_scorer.py — Meta Score 计算

Meta Score = Σ(signal_i × weight_i)  →  -1.0 ~ +1.0
"""
from typing import Dict, Tuple
from .signal_hub import collect_signals
from .weight_synthesizer import synthesize_weights


def compute_meta_score(signals: Dict, weights: Dict) -> Tuple[float, Dict]:
    """
    计算 Meta Score
    
    Returns: (score, component_scores)
    """
    sig = signals.get("signals", signals)
    
    components = {}
    total = 0.0
    
    for key, weight in weights.items():
        value = sig.get(key, 0.0)
        contribution = value * weight
        components[key] = {
            "signal": round(value, 3),
            "weight": weight,
            "contribution": round(contribution, 4),
        }
        total += contribution
    
    return round(total, 4), components


def determine_decision(meta_score: float, meta: Dict) -> Dict:
    """
    决策规则
    
    - 风险强制降级: breakout=liquidity_trap → max HOLD
    - 资金反向保护: flow_distribution → cannot LONG
    - SM风控: distribution → force HOLD/SHORT
    """
    decision = "HOLD"
    confidence = abs(meta_score) * 1.5
    
    # 风险强制降级
    brk_cls = meta.get("breakout_classification", "none")
    sm = meta.get("smart_money_behavior", "neutral")
    flow_regime = meta.get("flow_regime", "neutral")
    
    if brk_cls == "liquidity_trap":
        decision = "SHORT"
        confidence = 0.8
        reason = "流动性陷阱 → 强制做空/回避"
    elif brk_cls == "failed_breakout":
        decision = "HOLD"
        confidence = 0.7
        reason = "突破失败 → 强制观望"
    elif flow_regime == "distribution" and meta_score > 0:
        decision = "HOLD"
        confidence = 0.6
        reason = "资金在出货阶段 → 禁止做多"
    elif sm == "distribution" and meta_score > 0:
        decision = "HOLD"
        confidence = 0.7
        reason = "主力出货 → 禁止做多"
    elif meta_score > 0.35:
        decision = "LONG"
        confidence = min(confidence + 0.2, 1.0)
        reason = f"Meta Score {meta_score:+.2f} 超过做多阈值"
    elif meta_score < -0.35:
        decision = "SHORT"
        confidence = min(confidence + 0.2, 1.0)
        reason = f"Meta Score {meta_score:+.2f} 低于做空阈值"
    else:
        reason = f"Meta Score {meta_score:+.2f} 在观望区间"
    
    return {
        "decision": decision,
        "confidence": round(min(confidence, 1.0), 3),
        "meta_score": meta_score,
        "reason": reason,
    }

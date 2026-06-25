"""
rotation/smart_money/behavior_score.py — 行为强度评分 + 交易含义映射
"""
from typing import Dict
from .pattern_library import match_pattern, BEHAVIOR_PATTERNS

# 行为 → 交易含义
BEHAVIOR_TRADE_MAP = {
    "accumulation": {
        "action": "early_positioning",
        "rti_modifier": 1.3,       # RTI权重+30%
        "ensemble_bias": "LONG",
        "risk": "low",
        "description": "低位吸筹结构 — 可早期建仓",
    },
    "markup": {
        "action": "aggressive_long",
        "rti_modifier": 1.5,
        "ensemble_bias": "LONG",
        "risk": "medium",
        "description": "主升确认 — 加仓信号",
    },
    "distribution": {
        "action": "reduce_or_avoid",
        "rti_modifier": 0.5,       # RTI降权50%
        "ensemble_bias": "HOLD",
        "risk": "high",
        "description": "高位出货结构 — 减仓/回避",
    },
    "manipulation": {
        "action": "dip_buying",
        "rti_modifier": 1.1,
        "ensemble_bias": "LONG",
        "risk": "medium",
        "description": "洗盘结构 — 低吸机会",
    },
}


def score_all_behaviors(features: Dict) -> Dict:
    """
    对所有行为评分
    
    Returns: {"accumulation": 0.72, "markup": 0.18, "distribution": 0.05, "manipulation": 0.55}
    """
    scores = {}
    for behavior in BEHAVIOR_PATTERNS:
        scores[behavior] = match_pattern(features, behavior)
    return scores


def classify_behavior(scores: Dict) -> Dict:
    """
    识别主导行为
    
    Returns: {"behavior": str, "score": float, "confidence": float, "trade_implication": dict}
    """
    best = max(scores, key=scores.get)
    best_score = scores[best]
    runner_up = max((v for k, v in scores.items() if k != best), default=0)
    
    # 置信度: 最强 vs 次强 的差距
    confidence = min(1.0, (best_score - runner_up) * 2 + 0.3)
    if best_score < 0.3:
        confidence *= 0.5  # 都不明显
    
    trade = BEHAVIOR_TRADE_MAP.get(best, BEHAVIOR_TRADE_MAP["accumulation"])
    
    return {
        "behavior": best,
        "score": round(best_score, 3),
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "trade_implication": trade,
    }

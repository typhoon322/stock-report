"""
rotation/position/confidence_mapper.py — 信号→仓位映射

confidence = flow × 0.3 + smart_money × 0.3 + mtf × 0.2 + breakout × 0.2
"""
from typing import Dict


def compute_confidence(
    flow_strength: float,         # 0~1
    smart_money_score: float,     # 0~1
    mtf_agreement: float,         # 0~1
    breakout_quality: float,      # 0~1
) -> Dict:
    """
    计算置信度加权
    
    confidence: 0~1, 越高越可信
    """
    weights = {
        "flow": 0.30,
        "smart_money": 0.30,
        "mtf": 0.20,
        "breakout": 0.20,
    }
    
    components = {
        "flow": round(flow_strength * weights["flow"], 3),
        "smart_money": round(smart_money_score * weights["smart_money"], 3),
        "mtf": round(mtf_agreement * weights["mtf"], 3),
        "breakout": round(breakout_quality * weights["breakout"], 3),
    }
    
    confidence = sum(components.values())
    
    return {
        "confidence": round(min(confidence, 1.0), 3),
        "components": components,
    }


def map_to_position_level(confidence: float) -> str:
    """置信度→仓位等级"""
    if confidence > 0.8:
        return "high_confidence"
    elif confidence > 0.5:
        return "moderate_confidence"
    else:
        return "low_confidence"

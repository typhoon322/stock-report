"""
rotation/breakout/authenticity_score.py — 真假突破评分

Breakout Score = volume + cost_basis_break + flow_alignment + smart_money - rejection
"""
from typing import Dict


def compute_authenticity_score(
    breakout_info: Dict,
    flow_info: Dict = None,         # from flow detector
    smart_money_info: Dict = None,  # from smart money detector
    cost_basis_info: Dict = None,   # from cost basis
    follow_through: Dict = None,    # from follow_through
) -> Dict:
    """
    计算突破真实性总分 (-1.0 ~ +1.0)
    
    各组件贡献:
    - volume_confirmation:     0.25
    - cost_basis_break:        0.25
    - flow_alignment:          0.20
    - smart_money_support:     0.20
    - rejection_pressure:      -0.30 (惩罚项)
    """
    scores = {
        "volume_confirmation": 0.0,   # -1 to +1
        "cost_basis_break": 0.0,      # -1 to +1
        "flow_alignment": 0.0,        # -1 to +1
        "smart_money_support": 0.0,   # -1 to +1
        "rejection_pressure": 0.0,    # 0 to -1 (always non-positive)
    }
    
    # 1. 成交量确认
    vol_ratio = breakout_info.get("volume_ratio", 1.0)
    if vol_ratio >= 2.0:
        scores["volume_confirmation"] = 1.0
    elif vol_ratio >= 1.5:
        scores["volume_confirmation"] = 0.7
    elif vol_ratio >= 1.3:
        scores["volume_confirmation"] = 0.3
    elif vol_ratio < 0.8:
        scores["volume_confirmation"] = -1.0
    elif vol_ratio < 1.0:
        scores["volume_confirmation"] = -0.5
    
    # 2. 成本区突破
    if cost_basis_info:
        position = cost_basis_info.get("status", "")
        if position == "above_cost":
            scores["cost_basis_break"] = 0.8
        elif position == "in_cost_zone":
            scores["cost_basis_break"] = 0.2
        else:
            scores["cost_basis_break"] = -0.3
    
    # 3. 资金一致性
    if flow_info:
        direction = flow_info.get("direction", {}).get("direction", 0)
        regime = flow_info.get("regime", "")
        if direction > 0.2 and regime != "distribution":
            scores["flow_alignment"] = 1.0
        elif direction > 0:
            scores["flow_alignment"] = 0.5
        elif direction < -0.2:
            scores["flow_alignment"] = -1.0  # 资金流出+突破 = 危险
        elif direction < 0:
            scores["flow_alignment"] = -0.5
    
    # 4. Smart Money 支持
    if smart_money_info:
        behavior = smart_money_info.get("behavior", "")
        if behavior == "markup":
            scores["smart_money_support"] = 1.0
        elif behavior == "distribution":
            scores["smart_money_support"] = -1.0
        elif behavior == "accumulation":
            scores["smart_money_support"] = 0.5
        elif behavior == "manipulation":
            scores["smart_money_support"] = -0.8  # 洗盘中的突破不可信
    
    # 5. 回撤压力 (惩罚项)
    if follow_through:
        if follow_through.get("followed_through"):
            scores["rejection_pressure"] = 0.0
        elif follow_through.get("immediate_rejection"):
            scores["rejection_pressure"] = -1.0
        else:
            scores["rejection_pressure"] = -0.5
    
    # 加权总分
    weights = {
        "volume_confirmation": 0.25,
        "cost_basis_break": 0.25,
        "flow_alignment": 0.20,
        "smart_money_support": 0.20,
        "rejection_pressure": 0.10,
    }
    
    total = sum(scores[k] * weights[k] for k in scores)
    
    return {
        "total_score": round(total, 3),
        "component_scores": {k: round(v, 3) for k, v in scores.items()},
        "confidence": round(min(abs(total) * 1.5, 1.0), 3),
    }

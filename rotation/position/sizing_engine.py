"""
rotation/position/sizing_engine.py — 仓位计算主引擎

position = signal_strength × confidence × risk_factor
"""
from typing import Dict
from .risk_model import compute_risk_factor
from .confidence_mapper import compute_confidence
from .portfolio_guard import apply_guards


def compute_position_size(
    meta_score: float,                 # -1~+1
    flow_strength: float = 0.5,        # 0~1
    smart_money_score: float = 0.5,    # 0~1
    mtf_agreement: float = 0.5,        # 0~1
    breakout_quality: float = 0.5,     # 0~1
    volatility: float = 0.02,          # 市场波动率
    max_drawdown: float = 0.0,         # 最大回撤
    regime: str = "rotation",          # 市场状态
    mtf_score: int = 0,                # -3~+3
    flow_direction: float = 0.0,       # -1~+1
    breakout_classification: str = "none",
) -> Dict:
    """
    主入口: 计算最终仓位
    
    Returns:
        {
            "direction": str,
            "position_size": float,
            "position_level": str,
            "risk_level": str,
            "breakdown": {...},
        }
    """
    # 方向判定
    if meta_score > 0.35:
        direction = "LONG"
    elif meta_score < -0.35:
        direction = "SHORT"
    else:
        direction = "HOLD"
    
    # 观望直接返回
    if direction == "HOLD":
        return {
            "direction": "HOLD",
            "position_size": 0.0,
            "position_level": "零仓位",
            "risk_level": "N/A",
            "breakdown": {"reason": "Meta Score在观望区间"},
        }
    
    # Step 1: 信号强度 = |meta_score|
    signal_strength = min(abs(meta_score), 1.0)
    
    # Step 2: 置信度
    conf = compute_confidence(flow_strength, smart_money_score, mtf_agreement, breakout_quality)
    confidence = conf["confidence"]
    
    # Step 3: 风险因子
    risk = compute_risk_factor(volatility, max_drawdown, regime, mtf_score)
    risk_factor = risk["risk_factor"]
    
    # Step 4: 仓位 = signal × confidence × risk_factor
    position = signal_strength * confidence * risk_factor
    
    # Step 5: 风控限制
    guarded = apply_guards(position, meta_score, flow_direction, breakout_classification, regime)
    
    # 仓位分级
    size = guarded["adjusted_size"]
    if size > 0.8:
        level = "满仓(极端信号)"
    elif size > 0.5:
        level = "重仓"
    elif size > 0.2:
        level = "中仓"
    else:
        level = "轻仓"
    if size == 0:
        level = "零仓位"
    
    return {
        "direction": direction,
        "position_size": size,
        "position_level": level,
        "risk_level": risk["risk_level"],
        "breakdown": {
            "signal_strength": round(signal_strength, 3),
            "confidence": round(confidence, 3),
            "confidence_components": conf["components"],
            "risk_factor": round(risk_factor, 3),
            "risk_detail": risk,
            "guards": guarded,
        },
    }


def get_position_report(result: Dict) -> str:
    """生成仓位报告"""
    bd = result.get("breakdown", {})
    guards = bd.get("guards", {})
    
    lines = [
        f"# 💰 Position Sizing Report",
        f"",
        f"## Direction",
        f"👉 **{result['direction']}**",
        f"",
        f"## Position Size",
        f"👉 **{result['position_size']:.0%}** ({result['position_level']})",
        f"Risk Level: {result['risk_level']}",
        f"",
        f"## Breakdown",
        f"- Signal Strength: {bd.get('signal_strength', 0):.3f}",
        f"- Confidence: {bd.get('confidence', 0):.3f}",
        f"- Risk Factor: {bd.get('risk_factor', 0):.3f}",
    ]
    
    comp = bd.get("confidence_components", {})
    if comp:
        lines.append(f"  - Flow: +{comp.get('flow', 0):.3f} | SM: +{comp.get('smart_money', 0):.3f} | MTF: +{comp.get('mtf', 0):.3f} | BRK: +{comp.get('breakout', 0):.3f}")
    
    if guards.get("guards_applied", 0) > 0:
        lines.append(f"")
        lines.append(f"## ⚠️ Adjustments Applied ({guards['guards_applied']})")
        for g in guards.get("guard_log", []):
            lines.append(f"- {g['guard']}: {g['action']}")
    
    lines.extend([
        f"",
        f"## Final Decision",
        f"👉 allocate **{result['position_size']:.0%}** capital",
    ])
    
    return "\n".join(lines)

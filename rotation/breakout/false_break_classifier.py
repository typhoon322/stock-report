"""
rotation/breakout/false_break_classifier.py — 假突破分类 + 主入口

genuine_breakout / liquidity_trap / failed_breakout
"""
from typing import Dict
from .authenticity_score import compute_authenticity_score


def classify_breakout(
    breakout_info: Dict,
    authenticity: Dict,
    trap_info: Dict,
    follow_through: Dict,
) -> Dict:
    """
    综合分类: 真突破 / 流动性陷阱 / 突破失败
    
    判定逻辑:
    - score > 0.3 + follow_through.confirmed → genuine
    - trap_detected → liquidity_trap
    - immediate_rejection → failed_breakout
    - else → suspicious (待观察)
    """
    score = authenticity.get("total_score", 0)
    ft = follow_through.get("followed_through", False)
    trap = trap_info.get("trap_detected", False)
    reject = follow_through.get("immediate_rejection", False)
    
    if score > 0.3 and ft:
        classification = "genuine_breakout"
        action = "LONG — 真突破确认"
        confidence = "high"
    elif trap:
        classification = "liquidity_trap"  
        action = "AVOID / SHORT — 流动性陷阱"
        confidence = "high"
    elif reject:
        classification = "failed_breakout"
        action = "AVOID — 突破失败"
        confidence = "medium"
    elif score > 0:
        classification = "suspicious_breakout"
        action = "WAIT — 信号偏多但未确认"
        confidence = "low"
    else:
        classification = "suspicious_breakout"
        action = "AVOID — 信号偏空"
        confidence = "low"
    
    return {
        "classification": classification,
        "action": action,
        "confidence": confidence,
        "score": score,
        "trap_detected": trap,
        "followed_through": ft,
    }


def get_breakout_report(breakout: Dict, auth: Dict, classification: Dict, trap: Dict, ft: Dict) -> str:
    """生成突破分析报告"""
    comp = auth.get("component_scores", {})
    
    def bar(v):
        s = "+" if v > 0 else ("-" if v < 0 else " ")
        return f"{s}{abs(v):.2f}"
    
    lines = [
        f"# 🔥 Breakout Authenticity Report",
        f"",
        f"## Breakout Detected",
        f"👉 {'Yes' if breakout.get('detected') else 'No'}",
    ]
    
    if breakout.get("detected"):
        lines.extend([
            f"- Price: {breakout.get('breakout_price', '?')} (prev high: {breakout.get('previous_high', '?')})",
            f"- Volume: {breakout.get('volume_ratio', 0):.1f}x avg",
        ])
    
    lines.extend([
        f"",
        f"## Classification",
        f"👉 **{classification.get('classification', '?')}**",
        f"Action: **{classification.get('action', '?')}**",
        f"Confidence: {classification.get('confidence', '?')}",
        f"",
        f"## Scores",
        f"- Volume Confirm:   {bar(comp.get('volume_confirmation', 0))}",
        f"- Cost Break:       {bar(comp.get('cost_basis_break', 0))}",
        f"- Flow Alignment:   {bar(comp.get('flow_alignment', 0))}",
        f"- Smart Money:      {bar(comp.get('smart_money_support', 0))}",
        f"- Rejection:        {comp.get('rejection_pressure', 0):+.2f}",
        f"",
        f"## Total Score",
        f"**{auth.get('total_score', 0):+.3f}**",
        f"",
        f"## Follow-Through",
        f"- {ft.get('final_verdict', 'N/A')}",
        f"",
        f"## Trap Signals",
        f"- {'⚠️ ' + trap.get('description', '') if trap.get('trap_detected') else '✅ No trap detected'}",
    ])
    
    return "\n".join(lines)

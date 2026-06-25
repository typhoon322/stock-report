"""
rotation/meta/decision_engine.py — 交易决策引擎（主入口 + 解释报告）
"""
from typing import Dict
from .signal_hub import collect_signals
from .weight_synthesizer import synthesize_weights
from .meta_scorer import compute_meta_score, determine_decision


def run_meta_decision(
    rti_signal: int = 0, rti_confidence: float = 0.5,
    flow_direction: float = 0.0, flow_regime: str = "neutral",
    smart_money_behavior: str = "neutral", smart_money_score: float = 0.0,
    cost_position: str = "mid", cost_absorption: float = 0.0,
    breakout_classification: str = "none", breakout_score: float = 0.0,
    mtf_score: int = 0, mtf_status: str = "divergent",
    phase: str = "", market_regime: str = "rotation",
) -> Dict:
    """
    主入口: 运行完整的 Meta Decision 管线
    
    所有6个子系统信号 → 动态权重 → Meta Score → 交易决策 → 解释报告
    """
    # Step 1: 收集信号
    hub = collect_signals(
        rti_signal=rti_signal, rti_confidence=rti_confidence,
        flow_direction=flow_direction, flow_regime=flow_regime,
        smart_money_behavior=smart_money_behavior, smart_money_score=smart_money_score,
        cost_position=cost_position, cost_absorption=cost_absorption,
        breakout_classification=breakout_classification, breakout_score=breakout_score,
        mtf_score=mtf_score, mtf_status=mtf_status,
        phase=phase,
    )
    
    # Step 2: 动态权重
    weights = synthesize_weights(market_regime, flow_regime)
    
    # Step 3: Meta Score
    score, components = compute_meta_score(hub, weights)
    
    # Step 4: 决策
    decision = determine_decision(score, hub["meta"])
    
    # Step 5: 解释
    report = build_decision_report(hub, weights, components, score, decision)
    
    return {
        "signals": hub["signals"],
        "weights": weights,
        "components": components,
        "meta_score": score,
        "decision": decision,
        "report": report,
    }


def build_decision_report(hub, weights, components, score, decision) -> str:
    """生成人类可读的决策报告"""
    sig = hub["signals"]
    meta = hub["meta"]
    
    def bar(v):
        s = "+" if v > 0 else ("-" if v < 0 else " ")
        return f"{s}{abs(v):.2f}"
    
    lines = [
        f"# 🧠 Meta Decision Report",
        f"",
        f"## 🎯 Decision",
        f"👉 **{decision['decision']}** (confidence: {decision['confidence']:.0%})",
        f"Meta Score: **{score:+.3f}**",
        f"Reason: {decision['reason']}",
        f"",
        f"## 📊 Signal Contributions",
        f"| System | Signal | Weight | Contribution |",
        f"|--------|--------|--------|-------------|",
    ]
    
    for k in ["rti", "flow", "smart_money", "cost_basis", "breakout", "mtf"]:
        c = components[k]
        icon = "🟢" if c["signal"] > 0 else ("🔴" if c["signal"] < 0 else "⚪")
        lines.append(f"| {icon} {k.replace('_',' ').title():12s} | {c['signal']:+.2f} | {c['weight']:.2f} | {c['contribution']:+.3f} |")
    
    lines.extend([
        f"",
        f"## ⚙️ Market Context",
        f"- Regime: {meta.get('flow_regime', '?')}",
        f"- Smart Money: {meta.get('smart_money_behavior', '?')}",
        f"- Phase: {meta.get('phase', '?')}",
        f"- MTF: {meta.get('mtf_status', '?')}",
        f"",
        f"## 🔥 Key Drivers",
    ])
    
    # Top contributors
    sorted_comp = sorted(components.items(), key=lambda x: abs(x[1]["contribution"]), reverse=True)
    for k, c in sorted_comp[:3]:
        dir_word = "看多" if c["signal"] > 0 else ("看空" if c["signal"] < 0 else "中性")
        lines.append(f"- **{k.replace('_',' ').title()}**: {dir_word} (贡献{c['contribution']:+.3f})")
    
    return "\n".join(lines)

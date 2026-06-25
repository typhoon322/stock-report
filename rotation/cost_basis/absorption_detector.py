"""
rotation/cost_basis/absorption_detector.py — 吸筹/派发增强识别

结合成本区变化 + 成交量分布 → 判断主力在吸筹还是派发
"""
from typing import Dict


def detect_absorption(profile: Dict, concentration: Dict) -> Dict:
    """
    检测吸筹/派发行为
    
    吸筹信号:
    - 成本区逐渐抬升 (VWAP上升)
    - 低位成交密集
    - 当前价在成本区附近
    
    派发信号:
    - 成本区分散不集中
    - 高位放量
    - 当前价在成本区上方且远离
    """
    position = profile.get("current_price", 0)
    vwap = profile.get("weighted_avg_cost", 0)
    dense = concentration.get("cost_dense_zone", {})
    total_density = dense.get("total_density", 0)
    
    signals = {
        "absorption_signal": 0.0,    # 0-1, 吸筹强度
        "distribution_signal": 0.0,  # 0-1, 派发强度
        "dominant_behavior": "neutral",
    }
    
    # 吸筹检测
    if total_density > 0.3 and position < vwap * 1.05:
        signals["absorption_signal"] += 0.4  # 密集 + 不贵
    if position <= vwap * 1.02 and position >= vwap * 0.98:
        signals["absorption_signal"] += 0.3  # 在成本附近
    if total_density > 0.5:
        signals["absorption_signal"] += 0.3  # 高度集中
    
    # 派发检测
    if total_density < 0.2 and position > vwap * 1.1:
        signals["distribution_signal"] += 0.4  # 分散 + 高价
    if position > vwap * 1.15:
        signals["distribution_signal"] += 0.3  # 远离成本
    if total_density < 0.1:
        signals["distribution_signal"] += 0.3  # 极度分散
    
    # Clip
    signals["absorption_signal"] = round(min(signals["absorption_signal"], 1.0), 3)
    signals["distribution_signal"] = round(min(signals["distribution_signal"], 1.0), 3)
    
    # 判定
    if signals["absorption_signal"] > 0.6:
        signals["dominant_behavior"] = "accumulation"
    elif signals["distribution_signal"] > 0.6:
        signals["dominant_behavior"] = "distribution"
    elif signals["absorption_signal"] > signals["distribution_signal"]:
        signals["dominant_behavior"] = "accumulation_bias"
    elif signals["distribution_signal"] > signals["absorption_signal"]:
        signals["dominant_behavior"] = "distribution_bias"
    
    return signals


def get_cost_basis_report(profile: Dict, concentration: Dict, position: Dict, sr: Dict, absorption: Dict) -> str:
    """生成成本区完整报告"""
    dense = concentration.get("cost_dense_zone", {})
    pos_status = position.get("status", "unknown")
    
    lines = [
        f"# 🧱 Cost Basis Report",
        f"",
        f"## Cost Structure",
        f"- **Cost Dense Zone**: {dense.get('low', '?')} - {dense.get('high', '?')}",
        f"- **VWAP**: {profile.get('weighted_avg_cost', '?')}",
        f"- **Density**: {dense.get('total_density', 0):.1%}",
        f"",
        f"### Support & Resistance",
    ]
    
    ks = sr.get("key_support", {})
    kr = sr.get("key_resistance", {})
    if ks:
        lines.append(f"- **Support**: {ks.get('price', '?')} (strength: {ks.get('strength', 0):.1f}x)")
    if kr:
        lines.append(f"- **Resistance**: {kr.get('price', '?')} (strength: {kr.get('strength', 0):.1f}x)")
    
    lines.extend([
        f"",
        f"## Current Position",
        f"👉 **{pos_status}**",
        f"- **Interpretation**: {position.get('interpretation', '')}",
        f"- **Gap**: {position.get('gap_pct', 0)}%",
        f"",
        f"## Absorption / Distribution",
        f"- Absorption: {absorption.get('absorption_signal', 0):.2f}",
        f"- Distribution: {absorption.get('distribution_signal', 0):.2f}",
        f"- Dominant: **{absorption.get('dominant_behavior', 'neutral')}**",
        f"",
        f"## Trade Bias",
        f"👉 **{position.get('trade_bias', 'neutral')}**",
        f"Risk: {position.get('risk', 'N/A')}",
    ])
    
    return "\n".join(lines)

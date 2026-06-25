"""
rotation/flow/flow_weight.py — 资金流驱动的动态权重

model_weight = base_weight × flow_alignment × regime_multiplier
"""
from typing import Dict, List
from .flow_regime import FLOW_REGIMES

# Regime 权重乘数
REGIME_MULTIPLIERS = {
    "inflow_strong": {
        "RTI": 1.30,    # 进攻期 RTI 权重 ↑30%
        "ML":  1.25,
        "BSI": 1.10,
        "LS":  0.90,    # 进攻期龙头权重略降
        "rule": 1.15,
    },
    "rotation": {
        "RTI": 1.15,
        "ML":  1.20,
        "BSI": 1.05,
        "LS":  1.00,
        "rule": 1.10,
    },
    "distribution": {
        "RTI": 0.75,    # 出货期 RTI 信号降权
        "ML":  0.70,
        "BSI": 0.85,
        "LS":  1.40,    # 出货期 LS 防守权重 ↑40%
        "rule": 0.80,
    },
    "neutral": {
        "RTI": 1.00,
        "ML":  1.00,
        "BSI": 1.00,
        "LS":  1.00,
        "rule": 1.00,
    },
}


def compute_flow_alignment(
    model_signal: int,       # 1 (LONG) / 0 (HOLD) / -1 (SHORT)
    flow_direction: float,   # -1 (流出) ~ +1 (流入)
) -> float:
    """
    计算模型信号与资金流向的对齐度
    
    alignment = +1  if model and flow same direction
              = -1  if opposite
              = 0   if neutral
    """
    if model_signal > 0 and flow_direction > 0.1:
        return 1.0   # 做多 + 资金流入 → 对齐
    elif model_signal < 0 and flow_direction < -0.1:
        return 1.0   # 做空 + 资金流出 → 对齐
    elif model_signal == 0 or abs(flow_direction) < 0.1:
        return 0.5   # 中性 → 半对齐
    else:
        return -0.5  # 方向相反 → 惩罚


def compute_flow_adjusted_weights(
    base_weights: Dict[str, float],     # {model_name: base_weight}
    model_types: Dict[str, str],        # {model_name: type}  e.g. "RTI"/"ML"/"LS"
    model_signals: Dict[str, int],      # {model_name: signal} 1/0/-1
    flow_regime: str,
    flow_direction: float,
) -> Dict[str, float]:
    """
    计算资金流调整后的动态权重
    
    formula: adj_weight = base_weight × regime_multiplier × (1 + alignment × 0.2)
    """
    multipliers = REGIME_MULTIPLIERS.get(flow_regime, REGIME_MULTIPLIERS["neutral"])
    adjusted = {}
    total = 0.0
    
    for name, base in base_weights.items():
        m_type = model_types.get(name, "rule")
        regime_mult = multipliers.get(m_type, 1.0)
        
        # 资金对齐
        signal = model_signals.get(name, 0)
        alignment = compute_flow_alignment(signal, flow_direction)
        alignment_bonus = 1.0 + alignment * 0.25  # ±25% 对齐调整
        
        adj = base * regime_mult * alignment_bonus
        adjusted[name] = max(0.01, adj)  # 最低保底 1%
        total += adjusted[name]
    
    # 归一化
    if total > 0:
        adjusted = {k: round(v / total, 4) for k, v in adjusted.items()}
    
    return adjusted


def get_flow_report(flow_result: Dict, adjusted_weights: Dict) -> str:
    """生成资金流权重报告"""
    regime = flow_result.get("regime", "unknown")
    direction = flow_result.get("direction", {})
    features = flow_result.get("features", {})
    desc = FLOW_REGIMES.get(regime, "")
    
    lines = [
        f"## 💰 Flow-Weighted Report",
        f"",
        f"**Flow Regime**: {regime} — {desc}",
        f"**Flow Direction**: {direction.get('direction', 0):+.3f} (strength={direction.get('strength', 0):.2f})",
        f"**Net Flow**: {features.get('net_flow_total', 0):.1f}亿",
        f"**Concentration**: {features.get('flow_concentration', 0):.1%}",
        f"",
        f"### Adjusted Weights",
        f"| Model | Weight |",
        f"|-------|--------|",
    ]
    for name, w in sorted(adjusted_weights.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {name} | {w:.4f} |")
    
    return "\n".join(lines)

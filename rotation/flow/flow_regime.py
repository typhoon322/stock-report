"""
rotation/flow/flow_regime.py — 资金流状态识别

状态: inflow_strong / rotation / distribution / neutral
"""
from typing import Dict

FLOW_REGIMES = {
    "inflow_strong": "强进攻 — 资金大幅流入，广度扩张",
    "rotation":     "轮动 — 资金重新分配，板块分化",
    "distribution": "出货 — 资金流出，防御为主",
    "neutral":      "平衡 — 无明确方向",
}


def detect_flow_regime(
    net_flow_total: float,         # 全市场净流入 (亿)
    breadth_up: float,             # 上涨占比
    sector_dispersion: float,      # 板块分化度
    flow_acceleration: float,      # 资金加速度 (>0加速, <0减速)
) -> str:
    """
    识别资金流状态
    
    逻辑优先级:
    1. 出货: 净流出 + 低breadth
    2. 强进攻: 大幅净流入 + 高breadth
    3. 轮动: 适中流入 + 高分化
    4. 平衡: 其余
    """
    # 出货: 净流出 + 上涨占比低
    if net_flow_total < -10 and breadth_up < 0.35:
        return "distribution"
    
    # 强进攻: 大幅净流入 + 广度好 + 资金加速
    if net_flow_total > 20 and breadth_up > 0.55 and flow_acceleration > 0:
        return "inflow_strong"
    
    # 轮动: 适中流入 + 高板块分化
    if sector_dispersion > 1.5 and net_flow_total > -5:
        return "rotation"
    
    # 强进攻 (简化条件)
    if net_flow_total > 15 and breadth_up > 0.50:
        return "inflow_strong"
    
    return "neutral"


def compute_flow_direction(net_flow_total: float, flow_acceleration: float) -> Dict:
    """计算资金方向信号"""
    # 方向: -1(流出) ~ +1(流入)
    if net_flow_total > 10:
        direction = min(net_flow_total / 30, 1.0)
    elif net_flow_total < -10:
        direction = max(net_flow_total / 30, -1.0)
    else:
        direction = net_flow_total / 30
    
    # 强度: 0~1
    strength = min(abs(net_flow_total) / 25, 1.0)
    
    return {
        "direction": round(direction, 3),
        "strength": round(strength, 3),
        "accelerating": flow_acceleration > 0,
        "label": "flow_in" if direction > 0 else ("flow_out" if direction < 0 else "flat"),
    }

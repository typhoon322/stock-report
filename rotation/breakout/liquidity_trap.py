"""
rotation/breakout/liquidity_trap.py — 流动性陷阱识别

放量突破 + 快速回撤 + 收盘回成本区下方 = 诱多
"""
from typing import Dict


def detect_liquidity_trap(
    breakout_info: Dict,
    prices: list,
    volumes: list,
    cost_basis: Dict = None,
) -> Dict:
    """
    检测流动性陷阱 (诱多/诱空)
    
    核心特征:
    - 放量突破 (volume spike)
    - 快速回撤 (当日或次日回到突破点以下)
    - 收盘在成本密集区下方 (主力出货)
    """
    if not breakout_info or not breakout_info.get("detected"):
        return {"trap_detected": False, "trap_type": "none"}
    
    # 特征1: 放量
    vol_ratio = breakout_info.get("volume_ratio", 1.0)
    is_spike = vol_ratio > 1.8
    
    # 特征2: 快速回撤 (价格从突破点回落)
    if len(prices) >= 3:
        breakout_price = breakout_info.get("breakout_price", 0)
        current = prices[-1]
        previous = prices[-2]
        
        # 当日回落: 收盘 < 开盘 且 低于突破点
        same_day_reject = current < breakout_price and current < previous
        # 次日回落: 昨天突破，今天跌回
        next_day_reject = len(prices) >= 2 and prices[-1] < prices[-2] * 0.98
        
        rapid_rejection = same_day_reject or next_day_reject
    else:
        rapid_rejection = False
    
    # 特征3: 成本区下方 (如果有 cost_basis)
    below_cost = False
    if cost_basis:
        position = cost_basis.get("status", "")
        below_cost = position == "below_cost"
    
    # 综合判断
    trap_score = 0
    if is_spike:
        trap_score += 1
    if rapid_rejection:
        trap_score += 2  # 回撤是强信号
    if below_cost:
        trap_score += 1
    
    trap_detected = trap_score >= 3
    
    trap_types = {
        0: ("none", "无诱多信号"),
        1: ("suspicious", "疑似诱多"),
        2: ("likely", "大概率诱多"),
        3: ("liquidity_trap", "确定流动性陷阱"),
        4: ("liquidity_trap", "确认诱多 — 放量突破后快速回撤至成本下方"),
    }
    trap_type, trap_desc = trap_types.get(trap_score, trap_types[4])
    
    return {
        "trap_detected": trap_detected,
        "trap_type": trap_type,
        "trap_score": trap_score,
        "description": trap_desc,
        "signals": {
            "volume_spike": is_spike,
            "rapid_rejection": rapid_rejection,
            "below_cost": below_cost,
        },
    }

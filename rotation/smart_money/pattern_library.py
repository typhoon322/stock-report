"""
rotation/smart_money/pattern_library.py — 行为模式库

定义4种主力行为的规则特征
"""
from typing import Dict


# 行为模式定义: {行为: {特征: (min, max, weight)}}
BEHAVIOR_PATTERNS = {
    "accumulation": {
        "position_zone_low":     (0, 1.0, 0.25),   # 必须在低位
        "volume_dry_up":         (0.3, 1.0, 0.15),  # 缩量
        "range_contraction":     (0.2, 1.0, 0.15),  # 波动收敛
        "shadow_ratio":          (0.05, 1.0, 0.15), # 下影线(吸筹信号)
        "price_momentum":        (-0.3, 0.3, 0.10), # 横盘(不涨不跌)
        "intraday_bias":         (-0.3, 0.3, 0.10), # 日内平稳
        "pullback_depth":        (0, 0.3, 0.10),    # 小幅回撤
    },
    "markup": {
        "breakout_strength":     (0.02, 1.0, 0.20), # 突破
        "volume_spike":          (0.2, 1.0, 0.20),  # 放量
        "price_momentum":        (0.1, 1.0, 0.20),  # 正动量
        "intraday_bias":         (0.05, 1.0, 0.15), # 日内偏强
        "rebound_speed":         (0.3, 1.0, 0.15),  # 快速反弹
        "shadow_ratio":          (-0.3, 0.3, 0.10), # 影线少(稳定)
    },
    "distribution": {
        "position_zone_high":    (0, 1.0, 0.25),    # 必须在高位
        "volume_spike":          (0.1, 1.0, 0.15),  # 放量但...
        "price_momentum":        (-0.2, 0.1, 0.15), # 滞涨
        "shadow_ratio":          (-1.0, -0.03, 0.15), # 上影线(出货)
        "pullback_depth":        (0.05, 1.0, 0.15), # 回撤加大
        "intraday_bias":         (-1.0, -0.02, 0.15), # 日内走弱
    },
    "manipulation": {
        "volume_spike":          (0.3, 1.0, 0.20),  # 异常放量
        "rebound_speed":         (0.5, 1.0, 0.20),  # 快速收回
        "pullback_depth":        (0.03, 0.2, 0.20), # 深跌后收回
        "breakout_strength":     (-0.05, 0.02, 0.15), # 未真跌破
        "price_momentum":        (-0.5, 0.5, 0.15), # 剧烈波动
        "shadow_ratio":          (0.02, 1.0, 0.10),  # 下影线
    },
}


def match_pattern(features: Dict, behavior: str) -> float:
    """
    计算特征与行为模式的匹配度 (0-1)
    
    features: from microstructure.compute_microstructure()
    behavior: "accumulation" | "markup" | "distribution" | "manipulation"
    """
    pattern = BEHAVIOR_PATTERNS.get(behavior)
    if not pattern:
        return 0.0
    
    total_weight = 0.0
    match_score = 0.0
    
    for rule_name, (vmin, vmax, weight) in pattern.items():
        # 提取特征值
        if rule_name.startswith("position_zone_"):
            zone = rule_name.replace("position_zone_", "")
            value = 1.0 if features.get("position_zone") == zone else 0.0
        else:
            value = features.get(rule_name, 0)
        
        # 判断是否在区间内
        if vmin <= value <= vmax:
            match_score += weight
        else:
            # 部分匹配: 距离区间越近越好
            dist = min(abs(value - vmin), abs(value - vmax)) if vmin != vmax else abs(value - vmin)
            partial = max(0, 1 - dist * 2) * weight * 0.5
            match_score += partial
        
        total_weight += weight
    
    return round(match_score / max(total_weight, 0.01), 3)

"""
rotation/model_selector/regime_detector.py — 市场状态识别

输出: trend_up / rotation / choppy / risk_off
"""
from typing import Dict, List
import numpy as np


class Regime:
    TREND_UP   = "trend_up"    # 主升
    ROTATION   = "rotation"    # 轮动
    CHOPPY     = "choppy"      # 震荡
    RISK_OFF   = "risk_off"    # 退潮


def detect_regime(
    market_breadth: float,
    limit_up_count: int,
    sector_dispersion: float = 0.0,
    volume_change: float = 1.0,
    consecutive_board: int = 0,
    phase: str = "",
) -> str:
    """
    判断当前市场状态
    
    Args:
        market_breadth: 上涨占比 (0-1)
        limit_up_count: 涨停家数
        sector_dispersion: 板块涨跌幅标准差 (衡量分化程度)
        volume_change: 成交量变化
        consecutive_board: 最高连板
        phase: 已有的 Phase 判断 (优先使用)
    
    Returns:
        regime string
    """
    # 退潮: 极端悲观
    if market_breadth < 0.30 or limit_up_count < 15:
        if "退潮" in phase or "冰点" in phase:
            return Regime.RISK_OFF
        if market_breadth < 0.25:
            return Regime.RISK_OFF
        return Regime.CHOPPY
    
    # 主升: 普涨 + 涨停多 + 连板高
    if market_breadth > 0.55 and limit_up_count > 50 and consecutive_board >= 5:
        if "主升" in phase:
            return Regime.TREND_UP
        if market_breadth > 0.65:
            return Regime.TREND_UP
        return Regime.ROTATION
    
    # 轮动: 中等breadth + 适中断连
    if 0.40 <= market_breadth <= 0.70:
        if sector_dispersion > 1.5:
            return Regime.ROTATION  # 板块分化大 → 轮动
        if "轮动" in phase:
            return Regime.ROTATION
        if market_breadth > 0.5:
            return Regime.TREND_UP
        return Regime.ROTATION
    
    # 震荡: 其余
    return Regime.CHOPPY


def compute_sector_dispersion(sectors: List[Dict]) -> float:
    """计算板块涨跌幅标准差 (分化程度)"""
    changes = [s.get("change_1d", 0) or s.get("change_pct", 0) or 0 for s in sectors]
    if len(changes) < 3:
        return 0.0
    return round(float(np.std(changes)), 3)


def get_regime_from_market_state(
    breadth: float,
    limit_up: int,
    fall_limit: int = 0,
    strong_sectors_count: int = 0,
) -> str:
    """从简单市场数据推断 regime（备选入口）"""
    if breadth < 0.30:
        return Regime.RISK_OFF
    if breadth > 0.60 and limit_up > 60:
        return Regime.TREND_UP
    if fall_limit > limit_up * 0.5:
        return Regime.RISK_OFF
    if strong_sectors_count >= 5:
        return Regime.ROTATION
    return Regime.CHOPPY

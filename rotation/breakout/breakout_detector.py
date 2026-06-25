"""
rotation/breakout/breakout_detector.py — 初始突破识别

检测"候选突破" — 只是门槛，不是有效突破
"""
from typing import Dict, List, Optional
import numpy as np


def detect_breakout(
    prices: List[float],
    volumes: List[float],
    highs: List[float] = None,
    lookback: int = 20,
) -> Optional[Dict]:
    """
    检测是否发生价格突破
    
    条件:
    - price > recent high (过去N日高点)
    - volume > avg_volume * 1.5
    - volatility 扩张
    
    Returns: None if no breakout, or breakout details
    """
    n = len(prices)
    if n < lookback:
        return None
    
    current = prices[-1]
    current_vol = volumes[-1]
    
    # 最近N日高点 (用收盘价，不用当日high，避免包含当前bar)
    if highs:
        recent_high_candidates = highs[-lookback:-1] if len(highs) >= lookback else highs[:-1]
        recent_high = max(recent_high_candidates) if len(recent_high_candidates) > 0 else 0
    else:
        recent_high_candidates = prices[-lookback:-1] if len(prices) >= lookback else prices[:-1]
        recent_high = max(recent_high_candidates) if len(recent_high_candidates) > 0 else 0
    
    # 突破?
    if current <= recent_high:
        return None
    
    # 突破幅度
    breakout_pct = (current - recent_high) / recent_high * 100
    
    # 成交量确认
    avg_vol = np.mean(volumes[-lookback:-1])
    vol_ratio = current_vol / max(avg_vol, 1)
    
    # 波动扩张
    recent_volatility = np.std(prices[-5:]) / np.mean(prices[-5:])
    hist_volatility = np.std(prices[-lookback:-5]) / np.mean(prices[-lookback:-5])
    vol_expansion = recent_volatility > hist_volatility if hist_volatility > 0 else False
    
    # 仅当成交量放大 + 有一定突破幅度才是候选
    if breakout_pct < 0.1 and vol_ratio < 1.1:
        return None  # 太弱，不算突破
    
    return {
        "detected": True,
        "breakout_price": round(current, 2),
        "previous_high": round(recent_high, 2),
        "breakout_pct": round(breakout_pct, 2),
        "volume_ratio": round(vol_ratio, 2),
        "volume_confirmed": vol_ratio >= 1.5,
        "volatility_expansion": vol_expansion,
        "is_candidate": vol_ratio >= 1.3 or breakout_pct >= 0.5,
    }

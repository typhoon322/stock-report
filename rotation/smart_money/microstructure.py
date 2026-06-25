"""
rotation/smart_money/microstructure.py — 微观结构特征工程

从 K线结构 + 成交量 + 换手率提取主力行为特征
"""
from typing import Dict, List
import numpy as np


def compute_microstructure(
    prices: List[float],           # 收盘价序列 (最近N天)
    volumes: List[float],          # 成交量序列
    highs: List[float] = None,     # 最高价
    lows: List[float] = None,      # 最低价
    opens: List[float] = None,     # 开盘价
) -> Dict:
    """
    从 OHLCV 数据提取微观结构特征
    
    Returns:
        {
            "price_momentum": float,       # 价格动量 -1~1
            "volume_spike": float,         # 成交量异动 0~1
            "volume_dry_up": float,        # 缩量程度 0~1  
            "breakout_strength": float,    # 突破强度 0~1
            "pullback_depth": float,       # 回撤深度 0~1
            "rebound_speed": float,        # 反弹速度 0~1
            "range_contraction": float,    # 波动收敛 0~1
            "shadow_ratio": float,         # 影线占比 (上影诱多/下影吸筹)
            "position_zone": str,          # low/mid/high
            "intraday_bias": float,        # 日内偏向 (收盘-开盘)
        }
    """
    n = len(prices)
    if n < 5:
        return _empty_microstructure()
    
    prices = np.array(prices)
    volumes = np.array(volumes)
    
    # 1. 价格动量
    returns = np.diff(prices) / prices[:-1]
    momentum = float(np.mean(returns[-5:]) * 50)  # -1 to +1
    momentum = max(-1, min(1, momentum))
    
    # 2. 成交量异动 (最近3天 vs 前20天)
    if n >= 20:
        recent_vol = np.mean(volumes[-3:])
        hist_vol = np.mean(volumes[-20:-3])
        vol_spike = min(recent_vol / max(hist_vol, 1), 3.0) - 1
        vol_spike = max(0, min(1, vol_spike / 2))
    else:
        vol_spike = 0.0
    
    # 3. 缩量程度 (最近成交量 vs 峰值)
    peak_vol = np.max(volumes[-20:]) if n >= 20 else np.max(volumes)
    volume_dry_up = 1.0 - min(np.mean(volumes[-3:]) / max(peak_vol, 1), 1.0)
    
    # 4. 突破强度 (当前价 vs 20日高点)
    if n >= 20:
        high_20 = np.max(prices[-20:])
        breakout = prices[-1] / max(high_20, 0.01) - 1
        breakout_strength = min(max(breakout, 0), 1.0)
    else:
        breakout_strength = 0.0
    
    # 5. 回撤深度 (从高点跌了多少)
    if n >= 10:
        peak = np.max(prices[-10:])
        pullback = (peak - prices[-1]) / max(peak, 0.01)
        pullback_depth = min(pullback, 1.0)
    else:
        pullback_depth = 0.0
    
    # 6. 反弹速度
    if n >= 5 and pullback_depth > 0.02:
        recent_low = np.min(prices[-5:])
        rebound = (prices[-1] - recent_low) / max(recent_low, 0.01)
        rebound_speed = min(max(rebound * 10, 0), 1.0)
    else:
        rebound_speed = 0.0
    
    # 7. 波动收敛
    if n >= 10:
        range_recent = np.std(prices[-5:]) / np.mean(prices[-5:])
        range_prev = np.std(prices[-10:-5]) / np.mean(prices[-10:-5])
        if range_prev > 0:
            contraction = 1 - range_recent / range_prev
            range_contraction = max(0, min(1, contraction))
        else:
            range_contraction = 0.0
    else:
        range_contraction = 0.0
    
    # 8. 影线比例 (上影=诱多, 下影=吸筹)
    if highs and lows and opens and len(highs) >= 3:
        recent_highs = np.array(highs[-3:])
        recent_lows = np.array(lows[-3:])
        recent_opens = np.array(opens[-3:])
        recent_closes = prices[-3:]
        
        upper_shadows = (recent_highs - np.maximum(recent_opens, recent_closes)) / np.maximum(recent_highs - recent_lows, 0.001)
        lower_shadows = (np.minimum(recent_opens, recent_closes) - recent_lows) / np.maximum(recent_highs - recent_lows, 0.001)
        
        upper_ratio = float(np.mean(upper_shadows))
        lower_ratio = float(np.mean(lower_shadows))
        
        # 正=下影多(吸筹), 负=上影多(出货)
        shadow_ratio = lower_ratio - upper_ratio
    else:
        shadow_ratio = 0.0
    
    # 9. 位置区间
    if n >= 30:
        low_30 = np.min(prices[-30:])
        high_30 = np.max(prices[-30:])
        pos_pct = (prices[-1] - low_30) / max(high_30 - low_30, 0.01)
        if pos_pct < 0.3:
            position_zone = "low"
        elif pos_pct < 0.7:
            position_zone = "mid"
        else:
            position_zone = "high"
    else:
        position_zone = "mid"
    
    # 10. 日内偏向
    if opens and len(opens) >= 3:
        intraday = np.mean(prices[-3:] - np.array(opens[-3:])) / np.mean(prices[-3:])
        intraday_bias = float(max(-1, min(1, intraday * 20)))
    else:
        intraday_bias = 0.0
    
    return {
        "price_momentum": round(momentum, 3),
        "volume_spike": round(vol_spike, 3),
        "volume_dry_up": round(volume_dry_up, 3),
        "breakout_strength": round(breakout_strength, 3),
        "pullback_depth": round(pullback_depth, 3),
        "rebound_speed": round(rebound_speed, 3),
        "range_contraction": round(range_contraction, 3),
        "shadow_ratio": round(shadow_ratio, 3),
        "position_zone": position_zone,
        "intraday_bias": round(intraday_bias, 3),
    }


def _empty_microstructure() -> Dict:
    return {
        "price_momentum": 0, "volume_spike": 0, "volume_dry_up": 0,
        "breakout_strength": 0, "pullback_depth": 0, "rebound_speed": 0,
        "range_contraction": 0, "shadow_ratio": 0, "position_zone": "mid",
        "intraday_bias": 0,
    }

"""
rotation/mtf/trend_extractor.py — 每周期趋势提取

输出: +1(上升) / 0(震荡) / -1(下降)
"""
from typing import Dict, List
import numpy as np


def extract_trend(prices: List[float], days: int) -> Dict:
    """
    从一个价格序列提取趋势信号
    
    Returns:
        {"trend": +1|0|-1, "slope": float, "return_pct": float, "volatility": float, "label": str}
    """
    n = len(prices)
    if n < 2:
        return {"trend": 0, "slope": 0.0, "return_pct": 0.0, "volatility": 0.0, "label": "震荡"}
    
    prices = np.array(prices)
    
    # 1. 收益率
    ret = (prices[-1] - prices[0]) / max(prices[0], 0.01) * 100
    
    # 2. 线性斜率 (正=上升)
    x = np.arange(n)
    slope = np.polyfit(x, prices, 1)[0] / np.mean(prices) * 100  # 百分比斜率
    
    # 3. 波动率
    returns = np.diff(prices) / prices[:-1]
    vol = float(np.std(returns) * 100)
    
    # 4. 趋势判定
    if slope > 0.05 and ret > 0.5:
        trend = 1
        label = "上升趋势"
    elif slope < -0.05 and ret < -0.5:
        trend = -1
        label = "下降趋势"
    else:
        trend = 0
        label = "震荡"
    
    return {
        "trend": trend,
        "slope": round(float(slope), 3),
        "return_pct": round(ret, 2),
        "volatility": round(vol, 3),
        "label": label,
    }


def extract_all_trends(timeframes: Dict) -> Dict:
    """从三层时间框架提取所有趋势"""
    trends = {}
    for key in ["short", "mid", "long"]:
        tf = timeframes.get(key, {})
        prices = tf.get("prices", [])
        days = tf.get("days", 0)
        trends[key] = extract_trend(prices, days)
    
    return trends

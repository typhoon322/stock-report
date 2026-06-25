"""
rotation/breakout/follow_through.py — 突破延续性验证

连续2-3天收盘 > 突破点 + 成交量维持 = 真突破
当天/次日跌破 = 假突破
"""
from typing import Dict, List


def check_follow_through(
    prices: List[float],
    volumes: List[float],
    breakout_price: float,
    days: int = 3,
) -> Dict:
    """
    验证突破持续性
    
    检查最后N个交易日收盘价是否都高于突破点
    """
    n = len(prices)
    if n < days:
        return {
            "followed_through": False,
            "immediate_rejection": False,
            "days_held": 0,
            "volume_maintained": False,
            "final_verdict": "insufficient_data",
        }
    
    # 检查最近N天收盘 vs 突破点
    recent = prices[-days:]
    held = sum(1 for p in recent if p > breakout_price)
    
    immediate_rejection = held == 0 and prices[-1] <= breakout_price
    
    # 成交量维持
    if len(volumes) >= days:
        recent_vol = volumes[-days:]
        avg_recent_vol = sum(recent_vol) / len(recent_vol)
        all_vol = volumes[max(0, n-days*2):]
        avg_all_vol = sum(all_vol) / max(len(all_vol), 1)
        volume_maintained = avg_recent_vol > avg_all_vol * 0.6
    else:
        volume_maintained = False
    
    # 判定
    if held >= days * 0.7:
        verdict = f"confirmed — {held}/{days}天站稳突破点"
        followed = True
    elif held >= 1:
        verdict = f"pending — {held}/{days}天站稳，待观察"
        followed = False
    elif immediate_rejection:
        verdict = "failed — 当天即回落，假突破"
        followed = False
    else:
        verdict = "weak — 未能持续站稳"
        followed = False
    
    return {
        "followed_through": followed,
        "immediate_rejection": immediate_rejection,
        "days_held": held,
        "required_days": days,
        "volume_maintained": volume_maintained,
        "final_verdict": verdict,
    }
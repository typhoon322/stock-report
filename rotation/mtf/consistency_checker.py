"""
rotation/mtf/consistency_checker.py — 多周期一致性评分

MTF Score = short_trend + mid_trend + long_trend
"""
from typing import Dict
from .timeframe_builder import build_timeframes
from .trend_extractor import extract_all_trends


def compute_mtf_score(trends: Dict = None) -> Dict:
    """
    计算多时间周期一致性评分
    
    MTF Score: -3 to +3
    +3: 强一致上升 (short+mid+long全多)
    +1~+2: 偏多
    0: 分歧/不确定
    -1~-2: 偏空
    -3: 强一致下降
    """
    if trends is None:
        frames = build_timeframes()
        trends = extract_all_trends(frames)
    
    short_t = trends.get("short", {}).get("trend", 0)
    mid_t = trends.get("mid", {}).get("trend", 0)
    long_t = trends.get("long", {}).get("trend", 0)
    
    mtf_score = short_t + mid_t + long_t
    
    # 一致性: 所有周期同向的比例
    total = 3
    if mtf_score > 0:
        agreement = sum(1 for t in [short_t, mid_t, long_t] if t > 0) / total
    elif mtf_score < 0:
        agreement = sum(1 for t in [short_t, mid_t, long_t] if t < 0) / total
    else:
        agreement = sum(1 for t in [short_t, mid_t, long_t] if t == 0) / total
    
    # 状态判定
    if mtf_score >= 3:
        status = "strong_bullish"
        desc = "强一致上升 — 趋势共振"
    elif mtf_score >= 1:
        status = "moderately_bullish"
        desc = f"偏多 — {agreement:.0%}周期同向"
    elif mtf_score <= -3:
        status = "strong_bearish"
        desc = "强一致下降 — 趋势共振偏空"
    elif mtf_score <= -1:
        status = "moderately_bearish"
        desc = f"偏空 — {agreement:.0%}周期同向"
    else:
        status = "divergent"
        desc = "分歧 — 多周期方向不一致，信号不可靠"
    
    return {
        "mtf_score": mtf_score,
        "agreement": round(agreement, 2),
        "status": status,
        "description": desc,
        "trends": {
            "short": short_t,
            "mid": mid_t,
            "long": long_t,
        },
        "details": {
            k: {
                "trend": v.get("trend", 0),
                "label": v.get("label", "?"),
                "return_pct": v.get("return_pct", 0),
            }
            for k, v in trends.items()
        },
    }


def run_mtf_check() -> Dict:
    """主入口: 运行完整MTF检查 (纯计算, 零API)"""
    frames = build_timeframes()
    trends = extract_all_trends(frames)
    return compute_mtf_score(trends)

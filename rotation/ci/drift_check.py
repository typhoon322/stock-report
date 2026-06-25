"""
rotation/ci/drift_check.py — 市场结构漂移检测

防止"历史上有效但现在失效"的模型被使用
"""
from typing import Dict, List, Tuple
import numpy as np
import math

def detect_distribution_shift(
    historical: List[float],
    recent: List[float],
) -> Tuple[float, str]:
    """
    KS-test 检测分布变化
    
    Returns: (drift_score, status)
    drift_score: 0-1, 越大表示变化越大
    """
    if len(historical) < 10 or len(recent) < 10:
        return 0.0, "stable (insufficient data)"
    
    try:
        from scipy.stats import ks_2samp
        stat, pvalue = ks_2samp(historical, recent)
        drift = round(float(stat), 4)
    except:
        # 用均值和方差变化近似
        hist_mean, hist_std = np.mean(historical), np.std(historical)
        recent_mean, recent_std = np.mean(recent), np.std(recent)
        mean_shift = abs(recent_mean - hist_mean) / max(abs(hist_mean), 0.0001)
        std_shift = abs(recent_std - hist_std) / max(hist_std, 0.0001)
        drift = round(min(mean_shift + std_shift, 1.0), 4)
    
    if drift > 0.3:
        return drift, "critical — 市场结构剧变，模型可能失效"
    elif drift > 0.15:
        return drift, "warning — 出现结构性变化"
    else:
        return drift, "stable"


def check_volume_structure(
    historical_volumes: List[List[float]],
    recent_volumes: List[List[float]],
) -> Dict:
    """成交量结构变化检测"""
    hist_avg = [np.mean(v) for v in zip(*historical_volumes)] if historical_volumes else []
    recent_avg = [np.mean(v) for v in zip(*recent_volumes)] if recent_volumes else []
    
    drift_score, status = detect_distribution_shift(
        [float(x) for x in hist_avg],
        [float(x) for x in recent_avg],
    )
    return {"volume_drift": drift_score, "volume_status": status}


def check_sector_rotation_speed(
    sector_changes_hist: List[float],  # 历史每日Top5板块变化率
    sector_changes_recent: List[float],
) -> Dict:
    """板块轮动速度变化"""
    drift_score, status = detect_distribution_shift(
        sector_changes_hist, sector_changes_recent
    )
    
    if drift_score > 0.25:
        interpretation = "轮动加速 — 主线切换更快，旧策略可能滞后"
    elif drift_score > 0.1:
        interpretation = "轮动节奏变化 — 注意调整持有周期"
    else:
        interpretation = "轮动节奏稳定"
    
    return {
        "rotation_speed_drift": drift_score,
        "rotation_status": status,
        "interpretation": interpretation,
    }


def check_concentration(
    flow_concentration_hist: List[float],
    flow_concentration_recent: List[float],
) -> Dict:
    """资金集中度变化"""
    drift_score, status = detect_distribution_shift(
        flow_concentration_hist, flow_concentration_recent
    )
    
    hist_avg = np.mean(flow_concentration_hist) if flow_concentration_hist else 0
    recent_avg = np.mean(flow_concentration_recent) if flow_concentration_recent else 0
    
    if recent_avg > hist_avg * 1.5:
        note = "资金更集中 — 强者恒强"
    elif recent_avg < hist_avg * 0.5:
        note = "资金更分散 — 轮动机会增加"
    else:
        note = "集中度稳定"
    
    return {
        "concentration_drift": drift_score,
        "concentration_status": status,
        "note": note,
    }


def full_drift_check(
    historical_returns: List[float],
    recent_returns: List[float],
    historical_ic: List[float] = None,
    recent_ic: List[float] = None,
) -> Dict:
    """完整的市场结构检测"""
    drift_score, status = detect_distribution_shift(historical_returns, recent_returns)
    
    result = {
        "drift_score": drift_score,
        "drift_status": status,
        "alert": drift_score > 0.15,
        "details": {},
    }
    
    if historical_ic and recent_ic:
        ic_drift, ic_status = detect_distribution_shift(historical_ic, recent_ic)
        result["details"]["IC_drift"] = ic_drift
        result["details"]["IC_status"] = ic_status
        # IC漂移更关键
        if ic_drift > 0.15:
            result["alert"] = True
            result["drift_status"] = "critical — IC显著退化"
    
    return result

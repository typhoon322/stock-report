"""
rotation/rollback/stability_tracker.py — 稳定性评分系统

stability_score = IC一致性 + 低方差 + 低回撤 + 无CI失败
"""
from typing import List, Dict
import numpy as np


def compute_stability_score(
    ic_values: List[float],
    precision_values: List[float],
    drawdown_values: List[float],
    ci_failures: int,
    drift_values: List[float] = None,
) -> float:
    """
    计算稳定性评分 (0-1)
    
    越高越稳定:
    - IC高且波动小 → +0.35
    - Precision波动小 → +0.20
    - 回撤低 → +0.20
    - 无CI失败 → +0.15
    - Drift小 → +0.10
    """
    score = 0.0
    
    # 1. IC 一致性 (0.35)
    if ic_values:
        ic_mean = np.mean(ic_values)
        ic_std = np.std(ic_values)
        cv = ic_std / max(abs(ic_mean), 0.0001)  # 变异系数
        ic_score = max(0, 1 - cv) * 0.35
        score += ic_score
    
    # 2. Precision 稳定性 (0.20)
    if precision_values and len(precision_values) >= 2:
        prec_std = np.std(precision_values)
        prec_stability = max(0, 1 - prec_std * 5) * 0.20
        score += prec_stability
    
    # 3. 低回撤 (0.20)
    if drawdown_values:
        max_dd = max(drawdown_values)
        dd_score = max(0, 1 - max_dd) * 0.20
        score += dd_score
    
    # 4. CI 通过率 (0.15)
    total_runs = len(ic_values) if ic_values else 1
    pass_rate = 1 - (ci_failures / max(total_runs, 1))
    score += pass_rate * 0.15
    
    # 5. Drift 稳定 (0.10)
    if drift_values:
        avg_drift = np.mean(drift_values)
        drift_score = max(0, 1 - avg_drift / 0.3) * 0.10
        score += drift_score
    
    return round(min(score, 1.0), 4)


def classify_stability(score: float) -> str:
    """稳定性分类"""
    if score >= 0.8:
        return "🟢 高稳定"
    elif score >= 0.6:
        return "🟡 中等"
    elif score >= 0.4:
        return "🟠 偏低"
    else:
        return "🔴 不稳定"


def should_auto_rollback(
    new_ic: float,
    new_precision: float,
    new_max_dd: float,
    prod_ic: float,
    prod_precision: float,
    prod_max_dd: float,
    ci_pass: bool,
    drift_critical: bool,
) -> tuple:
    """
    判断是否应该回滚
    
    Returns: (should_rollback: bool, reason: str)
    """
    # 1. CI 失败 → 立即回滚
    if not ci_pass:
        return True, "CI_FAIL — 新模型未通过门检测试"
    
    # 2. 市场结构剧变 → 回滚
    if drift_critical:
        return True, "DRIFT_CRITICAL — 市场结构剧变，新模型不可靠"
    
    # 3. IC 显著下降 (相对下降>10%)
    if prod_ic > 0 and new_ic < prod_ic * 0.9:
        return True, f"IC_DROP — IC从{prod_ic:.4f}降至{new_ic:.4f} (下降{((1-new_ic/prod_ic)*100):.0f}%)"
    
    # 4. IC 绝对下降 >0.02
    if new_ic < prod_ic - 0.02:
        return True, f"IC_DROP_ABS — IC下降{prod_ic - new_ic:.4f}"
    
    # 5. Precision 显著下降
    if prod_precision > 0 and new_precision < prod_precision - 0.05:
        return True, f"PRECISION_DROP — Precision下降{prod_precision - new_precision:.3f}"
    
    # 6. 回撤过大
    if new_max_dd > 0.25:
        return True, f"HIGH_DRAWDOWN — 最大回撤{new_max_dd:.1%}超过25%阈值"
    
    return False, "OK"

"""
rotation/ci/thresholds.py — CI 合格线定义
"""
THRESHOLDS = {
    "IC": 0.05,
    "IC_warning": 0.03,
    "precision_top10": 0.55,
    "precision_top10_warning": 0.45,
    "max_drawdown": 0.20,
    "max_drawdown_warning": 0.30,
    "return_over_benchmark": 0.0,
    "return_over_benchmark_warning": -0.05,
    "hit_rate": 0.50,
    "hit_rate_warning": 0.35,
    "sharpe_proxy": 0.5,
    "sharpe_proxy_warning": 0.0,
    "drift_max": 0.3,
    "drift_warning": 0.15,
}

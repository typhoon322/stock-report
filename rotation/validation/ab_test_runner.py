"""
rotation/validation/ab_test_runner.py — A/B测试执行器

逐步关闭每个模块 → 观察性能变化
"""
from typing import Dict, List
from .feature_switcher import get_config, apply_config, ALL_FEATURES, PRESET_CONFIGS
from .metric_tracker import compute_metrics, compare_configs


def run_ablation(
    base_signals: Dict[str, float],   # {"rti": 0.8, "flow": 0.6, ...}
    weights: Dict[str, float] = None,
) -> List[Dict]:
    """
    运行完整消融分析
    
    测试: baseline → 逐个关闭模块 → 对比性能差异
    
    Returns: 每个配置的对比结果
    """
    results = []
    
    # Baseline: 全开
    baseline_metrics = compute_metrics(base_signals, weights)
    results.append({
        "config": "baseline",
        "type": "baseline",
        "metrics": baseline_metrics,
    })
    
    # 逐个关闭
    for feature in ALL_FEATURES:
        config_name = f"no_{feature.lower()}"
        config = get_config(config_name)
        
        # 应用配置: 关闭当前特性
        ablated_signals = apply_config(config, base_signals)
        ablated_metrics = compute_metrics(ablated_signals, weights)
        
        comparison = compare_configs(baseline_metrics, ablated_metrics, config_name)
        results.append({
            "config": config_name,
            "type": "ablation",
            "feature_removed": feature,
            "metrics": ablated_metrics,
            "comparison": comparison,
        })
    
    return results


def run_minimal_test(
    base_signals: Dict[str, float],
    weights: Dict[str, float] = None,
) -> List[Dict]:
    """测试最小系统 vs 完整系统的性能"""
    results = []
    
    baseline = compute_metrics(base_signals, weights)
    
    # 最小核心: RTI + Flow
    minimal_config = get_config("minimal_core")
    minimal_signals = apply_config(minimal_config, base_signals)
    minimal_metrics = compute_metrics(minimal_signals, weights)
    
    results.append({
        "config": "baseline",
        "metrics": baseline,
    })
    results.append({
        "config": "minimal_core",
        "metrics": minimal_metrics,
        "comparison": compare_configs(baseline, minimal_metrics, "minimal_core"),
    })
    
    return results

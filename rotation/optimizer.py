"""
rotation/optimizer.py — 参数自动优化

Grid Search + 简单目标函数
Score = avg_return + signal_accuracy/10 - max_drawdown_penalty
"""
from .rti3 import DEFAULT_WEIGHTS, RTI_THRESHOLD_MAINLINE, RTI_THRESHOLD_PROBING
from .backtest import BacktestEngine
from typing import Dict, List, Tuple
import itertools
import math


def grid_search(history: Dict, hold_days: int = 10) -> Dict:
    """
    Grid Search 优化 RTI v3 权重
    
    搜索空间:
    - 每个权重: [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    - rti_threshold: [2.5, 3.0, 3.5, 4.0, 4.5]
    
    约束: Σweights = 1.0
    """
    weight_options = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    threshold_options = [2.5, 3.0, 3.5, 4.0, 4.5]
    
    best_score = -float('inf')
    best_weights = dict(DEFAULT_WEIGHTS)
    best_threshold = 3.0
    best_metrics = {}
    results = []
    
    # 生成权重组合（约束: 和为1.0）
    weight_combos = []
    for w1 in weight_options:
        for w2 in weight_options:
            for w3 in weight_options:
                for w4 in weight_options:
                    for w5 in weight_options:
                        w6 = 1.0 - (w1 + w2 + w3 + w4 + w5)
                        if 0 <= w6 <= 0.35:
                            combo = {
                                "w1_flow_shift": round(w1, 2),
                                "w2_acceleration": round(w2, 2),
                                "w3_low_base": round(w3, 2),
                                "w4_expansion": round(w4, 2),
                                "w5_news_decouple": round(w5, 2),
                                "w6_old_decay": round(w6, 2),
                            }
                            # Verify sum ≈ 1.0
                            if abs(sum(combo.values()) - 1.0) < 0.02:
                                weight_combos.append(combo)
    
    # 限制搜索空间（约500-1000个组合）
    if len(weight_combos) > 200:
        weight_combos = weight_combos[::len(weight_combos)//200]
    
    print(f"🔍 Grid Search: {len(weight_combos)}权重组合 × {len(threshold_options)}阈值")
    
    tested = 0
    for weights in weight_combos:
        for threshold in threshold_options:
            engine = BacktestEngine(history)
            metrics = engine.run(rti_threshold=threshold, hold_days=hold_days)
            
            if metrics.get("completed_trades", 0) < 3:
                continue  # 样本太少，跳过
            
            # 目标函数: 收益 + 准确率 - 回撤惩罚
            score = (
                metrics.get("avg_return", 0) * 2 +
                metrics.get("signal_accuracy", 0) / 10 +
                metrics.get("win_rate", 0) / 20 -
                abs(metrics.get("min_return", 0)) * 0.5
            )
            
            results.append({
                "weights": weights,
                "threshold": threshold,
                "score": round(score, 2),
                "metrics": metrics,
            })
            
            if score > best_score:
                best_score = score
                best_weights = weights
                best_threshold = threshold
                best_metrics = metrics
            
            tested += 1
    
    if not results:
        return {
            "status": "insufficient_data",
            "message": "历史数据不足以运行回测",
            "tested_combinations": tested,
        }
    
    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "status": "optimized",
        "tested_combinations": tested,
        "best_score": round(best_score, 2),
        "best_weights": best_weights,
        "best_threshold": best_threshold,
        "best_metrics": best_metrics,
        "top3": results[:3],
    }


def quick_optimize(history: Dict) -> Dict:
    """
    快速优化（5个典型权重组合）
    用于每日快速验证
    """
    preset_weights = [
        {"w1_flow_shift": 0.25, "w2_acceleration": 0.20, "w3_low_base": 0.20,
         "w4_expansion": 0.15, "w5_news_decouple": 0.10, "w6_old_decay": 0.10},  # 均衡
        {"w1_flow_shift": 0.35, "w2_acceleration": 0.20, "w3_low_base": 0.15,
         "w4_expansion": 0.10, "w5_news_decouple": 0.10, "w6_old_decay": 0.10},  # 偏FlowShift
        {"w1_flow_shift": 0.15, "w2_acceleration": 0.15, "w3_low_base": 0.30,
         "w4_expansion": 0.20, "w5_news_decouple": 0.10, "w6_old_decay": 0.10},  # 偏低位突破
        {"w1_flow_shift": 0.20, "w2_acceleration": 0.15, "w3_low_base": 0.15,
         "w4_expansion": 0.20, "w5_news_decouple": 0.20, "w6_old_decay": 0.10},  # 偏扩散+新闻
        {"w1_flow_shift": 0.20, "w2_acceleration": 0.15, "w3_low_base": 0.15,
         "w4_expansion": 0.15, "w5_news_decouple": 0.10, "w6_old_decay": 0.25},  # 偏旧主线衰减
    ]
    
    best_score = -float('inf')
    best_result = {}
    
    for weights in preset_weights:
        engine = BacktestEngine(history)
        metrics = engine.run(rti_threshold=3.0, hold_days=10)
        score = metrics.get("avg_return", 0) * 2 + metrics.get("win_rate", 0) / 20
        
        if score > best_score:
            best_score = score
            best_result = {"weights": weights, "score": round(score, 2), "metrics": metrics}
    
    return best_result

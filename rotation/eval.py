"""
rotation/eval.py — 模型评估

指标: AUC, Precision@Top10%, Recall(主线捕捉率), RTI Top10% → 未来3天上涨概率
"""
from typing import List, Dict, Tuple
import numpy as np
from .audit_builder import AuditBundle, bundles_to_arrays
from .rti_ml import RTIMLModel


def evaluate(model: RTIMLModel, bundles: List[AuditBundle]) -> Dict:
    """评估模型性能"""
    if not model.trained or not bundles:
        return {"status": "no_model_or_data"}
    
    X, y_true = bundles_to_arrays(bundles)
    y_prob = model.predict_batch(bundles)
    
    metrics = {}
    
    # 1. AUC
    try:
        from sklearn.metrics import roc_auc_score
        metrics["auc"] = round(roc_auc_score(y_true, y_prob), 4)
    except:
        metrics["auc"] = None
    
    # 2. Precision @ Top 10% RTI
    top10_threshold = np.percentile(y_prob, 90) if y_prob else 0
    top10_idx = [i for i, p in enumerate(y_prob) if p >= top10_threshold]
    if top10_idx:
        top10_true = sum(y_true[i] for i in top10_idx)
        metrics["precision_top10"] = round(top10_true / len(top10_idx), 4)
        # 未来3天上涨概率
        metrics["top10_win_rate"] = metrics["precision_top10"]
    else:
        metrics["precision_top10"] = None
    
    # 3. Recall (主线捕捉率)
    true_positives = sum(1 for i in range(len(y_true)) 
                         if y_true[i] == 1 and y_prob[i] >= 0.5)
    total_positives = int(sum(y_true))
    metrics["recall"] = round(true_positives / max(total_positives, 1), 4)
    
    # 4. 按RTI分位分组统计
    if y_prob:
        thresholds = [0.3, 0.5, 0.7]
        quantile_stats = {}
        for t in thresholds:
            idx = [i for i, p in enumerate(y_prob) if p >= t]
            if idx:
                wins = sum(y_true[i] for i in idx)
                quantile_stats[f"RTI≥{t}"] = {
                    "count": len(idx),
                    "win_rate": round(wins / len(idx), 4),
                }
        metrics["quantile_stats"] = quantile_stats
    
    metrics["n_samples"] = len(bundles)
    metrics["positive_rate"] = round(int(sum(y_true)) / max(len(y_true), 1), 4)
    
    return metrics


def evaluate_and_report(model: RTIMLModel, bundles: List[AuditBundle]):
    """评估并打印报告"""
    metrics = evaluate(model, bundles)
    
    print("\n" + "=" * 50)
    print("📊 RTI ML 模型评估报告")
    print("=" * 50)
    print(f"  样本数: {metrics.get('n_samples', 0)}")
    print(f"  正例率: {metrics.get('positive_rate', 0):.1%}")
    print(f"  AUC: {metrics.get('auc', 'N/A')}")
    print(f"  Precision@Top10%: {metrics.get('precision_top10', 'N/A')}")
    print(f"  Recall: {metrics.get('recall', 'N/A')}")
    
    qs = metrics.get("quantile_stats", {})
    for k, v in qs.items():
        print(f"  {k}: 样本{v['count']}个, 胜率{v['win_rate']:.1%}")
    
    return metrics

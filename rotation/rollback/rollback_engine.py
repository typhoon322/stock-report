"""
rotation/rollback/rollback_engine.py — 自动回滚引擎

核心决策: 新模型是否上线 or 回退到上一个稳定版本
"""
import json, os
from datetime import datetime
from typing import Dict, Optional

from .registry import ModelRegistry, ModelVersion
from .stability_tracker import should_auto_rollback, compute_stability_score, classify_stability
from .version_manager import archive_model, restore_model

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(ROOT, "rotation", "rollback", "logs", "rollback_log.jsonl")


def log_rollback_event(
    from_version: str,
    to_version: str,
    reason: str,
    trigger: str,
):
    """记录回滚事件"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    event = {
        "timestamp": datetime.now().isoformat(),
        "from_version": from_version,
        "to_version": to_version,
        "reason": reason,
        "trigger": trigger,
    }
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')


def run_rollback_check(
    new_model_version: str,
    new_metrics: Dict,
    drift: Dict,
    ci_pass: bool,
) -> Dict:
    """
    运行回滚检查
    
    Returns: {"action": "KEEP"|"ROLLBACK", "reason": str, "from": str, "to": str}
    """
    registry = ModelRegistry()
    prod = registry.get_production()
    
    new_ic = new_metrics.get("IC", 0)
    new_precision = new_metrics.get("precision_top10", 0)
    new_max_dd = new_metrics.get("max_drawdown", 0)
    
    # 计算稳定性
    stability = compute_stability_score(
        [new_ic], [new_precision], [new_max_dd],
        ci_failures=0 if ci_pass else 1,
        drift_values=[drift.get("drift_score", 0)],
    )
    
    # 注册新模型
    model = ModelVersion(
        version=new_model_version,
        timestamp=datetime.now().isoformat(),
        ic=new_ic,
        precision_top10=new_precision,
        max_drawdown=new_max_dd,
        stability_score=stability,
        is_production=False,
        ci_pass=ci_pass,
        drift_score=drift.get("drift_score", 0),
    )
    registry.add_model(model)
    
    # 归档模型文件
    archive_model(new_model_version)
    
    # 如果没有生产模型 → 首次上线
    if prod is None:
        registry.set_production(new_model_version)
        print(f"🚀 首次上线: {new_model_version} (IC={new_ic:.4f})")
        return {
            "action": "KEEP",
            "reason": "FIRST_DEPLOY — 首次模型上线",
            "from": None,
            "to": new_model_version,
            "stability": stability,
            "stability_label": classify_stability(stability),
        }
    
    # 判断是否需要回滚
    should_roll, reason = should_auto_rollback(
        new_ic, new_precision, new_max_dd,
        prod.ic, prod.precision_top10, prod.max_drawdown,
        ci_pass, drift.get("alert", False),
    )
    
    if should_roll:
        # 找上一个稳定版本
        last_stable = registry.get_last_stable(min_stability=0.6)
        
        if last_stable and last_stable.version != new_model_version:
            registry.set_production(last_stable.version)
            restore_model(last_stable.version)
            log_rollback_event(new_model_version, last_stable.version, reason, "AUTO_ROLLBACK")
            
            print(f"\n🔁 自动回滚触发!")
            print(f"  ❌ 拒绝: {new_model_version} (IC={new_ic:.4f})")
            print(f"  ✅ 恢复: {last_stable.version} (IC={last_stable.ic:.4f})")
            print(f"  📝 原因: {reason}")
            
            return {
                "action": "ROLLBACK",
                "reason": reason,
                "from": new_model_version,
                "to": last_stable.version,
                "stability": stability,
                "stability_label": classify_stability(stability),
            }
        else:
            # 没有可用的稳定版本 → 保持当前
            print(f"\n⚠️ 需要回滚但无可用稳定版本")
            return {
                "action": "KEEP_CURRENT",
                "reason": f"NO_STABLE_FALLBACK — {reason}",
                "from": new_model_version,
                "to": prod.version,
                "stability": stability,
                "stability_label": classify_stability(stability),
            }
    
    # 通过 → 上线新版本
    registry.set_production(new_model_version)
    print(f"\n✅ 新模型上线: {new_model_version} (IC={new_ic:.4f}, stability={stability:.2f})")
    
    return {
        "action": "KEEP",
        "reason": "PASSED — 新模型优于或等于生产版本",
        "from": prod.version,
        "to": new_model_version,
        "stability": stability,
        "stability_label": classify_stability(stability),
    }

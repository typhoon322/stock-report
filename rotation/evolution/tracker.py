"""
rotation/evolution/tracker.py — 自动进化追踪器

每次 CI 结束时自动调用，记录模型进化轨迹
"""
import os, subprocess
from datetime import datetime
from typing import Dict, Optional
from .log_store import EvolutionRecord, append_record, get_latest_record


def get_git_commit() -> str:
    """获取当前 git commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()[:8]
    except:
        return "unknown"


def get_git_diff_summary() -> str:
    """获取本次变更摘要 (最近一次commit message)"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()[:100]
    except:
        return "manual_run"


def detect_change_type(summary: str) -> str:
    """从 commit message 推断变更类型"""
    summary_lower = summary.lower()
    if any(kw in summary_lower for kw in ["feature", "特征", "add"]):
        return "feature"
    elif any(kw in summary_lower for kw in ["weight", "权重", "tune", "adjust"]):
        return "weight"
    elif any(kw in summary_lower for kw in ["data", "数据", "history"]):
        return "data"
    elif any(kw in summary_lower for kw in ["ml", "model", "train", "结构"]):
        return "structure"
    else:
        return "general"


def log_model_evolution(
    model_version: str,
    metrics: Dict,
    drift: Dict,
    ci_pass: bool,
    change_summary: str = "",
    notes: str = "",
) -> EvolutionRecord:
    """
    记录一次模型进化
    
    自动计算 vs 上一版本的 delta
    """
    if not change_summary:
        change_summary = get_git_diff_summary()
    
    prev = get_latest_record()
    ic_delta = 0.0
    precision_delta = 0.0
    
    if prev:
        ic_delta = round(metrics.get("IC", 0) - prev.get("ic", 0), 4)
        precision_delta = round(metrics.get("precision_top10", 0) - prev.get("precision_top10", 0), 4)
    
    record = EvolutionRecord(
        timestamp=datetime.now().isoformat(),
        model_version=model_version,
        change_type=detect_change_type(change_summary),
        change_summary=change_summary[:200],
        ic=round(metrics.get("IC", 0), 4),
        precision_top10=round(metrics.get("precision_top10", 0), 4),
        max_drawdown=round(metrics.get("max_drawdown", 0), 4),
        ic_delta=ic_delta,
        precision_delta=precision_delta,
        ci_pass=ci_pass,
        drift_score=round(drift.get("drift_score", 0), 4),
        git_commit=get_git_commit(),
        notes=notes[:500],
    )
    
    append_record(record)
    
    # Print summary
    trend_icon = "📈" if ic_delta > 0 else ("📉" if ic_delta < 0 else "➡️")
    print(f"\n🧬 进化记录: {model_version}")
    print(f"  {trend_icon} IC: {record.ic:.4f} (Δ{ic_delta:+.4f})")
    print(f"  {'✅' if ci_pass else '❌'} CI: {'PASS' if ci_pass else 'FAIL'}")
    print(f"  📝 {change_summary[:80]}")
    
    return record

"""
rotation/evolution/diff.py — 版本差异分析

回答"这次到底改了什么？"以及"改得好不好？"
"""
from typing import Dict, List
from .log_store import read_all_records, get_latest_record


def compare_versions(v1: str, v2: str) -> Dict:
    """比较两个版本的性能差异"""
    records = read_all_records()
    r1 = next((r for r in records if r["model_version"] == v1), None)
    r2 = next((r for r in records if r["model_version"] == v2), None)
    
    if not r1 or not r2:
        return {"error": f"Version not found: {v1 if not r1 else ''} {v2 if not r2 else ''}"}
    
    return {
        "version_from": v1,
        "version_to": v2,
        "ic_change": round(r2["ic"] - r1["ic"], 4),
        "precision_change": round(r2["precision_top10"] - r1["precision_top10"], 4),
        "drawdown_change": round(r2["max_drawdown"] - r1["max_drawdown"], 4),
        "ci_from": r1["ci_pass"],
        "ci_to": r2["ci_pass"],
        "change_summary": r2.get("change_summary", ""),
        "verdict": "improved" if r2["ic"] > r1["ic"] and r2["ci_pass"] else (
            "degraded" if r2["ic"] < r1["ic"] else "unchanged"
        ),
    }


def find_best_version() -> Dict:
    """找历史最佳版本 (按IC排序)"""
    records = read_all_records()
    if not records:
        return {"error": "no records"}
    
    best = max(records, key=lambda r: r.get("ic", 0))
    return {
        "version": best["model_version"],
        "ic": best["ic"],
        "precision_top10": best["precision_top10"],
        "timestamp": best["timestamp"],
        "change_summary": best.get("change_summary", ""),
    }


def find_worst_regression() -> Dict:
    """找最大退化"""
    records = read_all_records()
    if len(records) < 2:
        return {"error": "need at least 2 records"}
    
    worst = None
    max_drop = 0
    for i in range(1, len(records)):
        drop = records[i-1]["ic"] - records[i]["ic"]
        if drop > max_drop:
            max_drop = drop
            worst = {
                "from_version": records[i-1]["model_version"],
                "to_version": records[i]["model_version"],
                "ic_drop": round(drop, 4),
                "change": records[i].get("change_summary", ""),
            }
    
    return worst or {"error": "no regression found"}


def find_best_improvement() -> Dict:
    """找最大改进"""
    records = read_all_records()
    if len(records) < 2:
        return {"error": "need at least 2 records"}
    
    best = None
    max_gain = 0
    for i in range(1, len(records)):
        gain = records[i]["ic"] - records[i-1]["ic"]
        if gain > max_gain:
            max_gain = gain
            best = {
                "from_version": records[i-1]["model_version"],
                "to_version": records[i]["model_version"],
                "ic_gain": round(gain, 4),
                "change": records[i].get("change_summary", ""),
            }
    
    return best or {"error": "no improvement found"}

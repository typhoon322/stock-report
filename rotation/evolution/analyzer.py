"""
rotation/evolution/analyzer.py — 进化分析引擎

输出: 趋势/plateau/最佳改动/最差退化
"""
from typing import Dict, List
import numpy as np
from .log_store import read_all_records


def analyze_trend() -> Dict:
    """分析模型进化趋势"""
    records = read_all_records()
    if len(records) < 3:
        return {"status": "insufficient_data", "records": len(records)}
    
    ic_values = [r["ic"] for r in records]
    precision_values = [r["precision_top10"] for r in records]
    
    # 线性趋势
    x = np.arange(len(ic_values))
    ic_slope = np.polyfit(x, ic_values, 1)[0]
    precision_slope = np.polyfit(x, precision_values, 1)[0]
    
    # 趋势方向
    def trend_label(slope):
        if slope > 0.002:
            return "📈 improving"
        elif slope < -0.002:
            return "📉 declining"  
        else:
            return "➡️ stable"
    
    # Plateau detection: 最近3个版本的IC标准差 < 0.003
    recent_ic = ic_values[-3:] if len(ic_values) >= 3 else ic_values
    ic_std = float(np.std(recent_ic))
    plateau = ic_std < 0.003 and ic_slope < 0.001
    
    # Pass rate
    pass_count = sum(1 for r in records if r.get("ci_pass"))
    
    return {
        "total_records": len(records),
        "versions": [r["model_version"] for r in records],
        "ic_trend": trend_label(ic_slope),
        "ic_slope": round(float(ic_slope), 6),
        "precision_trend": trend_label(precision_slope),
        "current_ic": round(ic_values[-1], 4),
        "best_ic": round(max(ic_values), 4),
        "worst_ic": round(min(ic_values), 4),
        "plateau_detected": plateau,
        "plateau_note": "⚠️ 模型进入平台期，IC不再增长" if plateau else "",
        "ci_pass_rate": round(pass_count / len(records), 2),
        "drift_trend": [r.get("drift_score", 0) for r in records],
    }


def generate_evolution_summary() -> str:
    """生成可读的进化摘要"""
    trend = analyze_trend()
    records = read_all_records()
    
    if not records:
        return "暂无进化记录"
    
    latest = records[-1]
    lines = [
        f"## 📊 模型进化摘要",
        f"",
        f"**当前版本**: {latest['model_version']}",
        f"**总记录**: {len(records)} 次变更",
        f"",
        f"### 趋势",
        f"- IC: {trend.get('ic_trend', 'N/A')} (当前: {trend.get('current_ic', 0):.4f})",
        f"- Precision: {trend.get('precision_trend', 'N/A')}",
        f"- CI 通过率: {trend.get('ci_pass_rate', 0):.0%}",
    ]
    
    if trend.get("plateau_detected"):
        lines.append(f"- ⚠️ {trend.get('plateau_note', '')}")
    
    lines.append("")
    lines.append("### 进化时间线")
    for r in records:
        icon = "✅" if r.get("ci_pass") else "❌"
        delta = r.get("ic_delta", 0)
        arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
        lines.append(f"- {icon} {r['model_version']}: IC={r['ic']:.4f} {arrow} {r.get('change_summary','')[:50]}")
    
    return "\n".join(lines)

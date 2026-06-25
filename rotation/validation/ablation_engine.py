"""
rotation/validation/ablation_engine.py — 消融分析主引擎 + 报告
"""
from typing import Dict, List
from datetime import datetime
from .ab_test_runner import run_ablation, run_minimal_test


def run_full_ablation(
    base_signals: Dict[str, float],
    weights: Dict[str, float] = None,
) -> Dict:
    """
    主入口: 运行完整消融分析
    
    Returns: ablation_results + report
    """
    # 消融分析
    ablation_results = run_ablation(base_signals, weights)
    
    # 最小系统测试
    minimal_results = run_minimal_test(base_signals, weights)
    
    # 提取贡献度
    contributions = []
    for r in ablation_results:
        if r.get("type") == "ablation" and "comparison" in r:
            comp = r["comparison"]
            contributions.append({
                "feature": r["feature_removed"],
                "contribution_bps": comp["contribution_bps"],
                "verdict": comp["verdict"],
                "delta_return": comp["delta_return"],
            })
    
    # 排序: 贡献度降序
    contributions.sort(key=lambda x: x["contribution_bps"], reverse=True)
    
    # 生成报告
    report = generate_ablation_report(contributions, ablation_results[0]["metrics"])
    
    return {
        "timestamp": datetime.now().isoformat(),
        "ablation_results": ablation_results,
        "minimal_results": minimal_results,
        "contributions": contributions,
        "core_modules": [c["feature"] for c in contributions if c["verdict"] == "positive"],
        "redundant_modules": [c["feature"] for c in contributions if c["verdict"] == "negative"],
        "report": report,
    }


def generate_ablation_report(contributions: List[Dict], baseline: Dict) -> str:
    """生成消融验证报告"""
    lines = [
        f"# 🧪 Ablation Report",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## Baseline Performance",
        f"- Return Proxy: {baseline.get('return_proxy', 0):.3f}",
        f"- Sharpe Proxy: {baseline.get('sharpe_proxy', 0):.3f}",
        f"- Active Modules: {baseline.get('active_modules', 0)}",
        f"",
        f"## Module Contributions",
        f"",
        f"| Module | Contribution (bps) | Impact | Return Delta |",
        f"|--------|-------------------|--------|-------------|",
    ]
    
    for c in contributions:
        icon = "📈" if c["verdict"] == "positive" else ("📉" if c["verdict"] == "negative" else "➡️")
        lines.append(f"| {icon} {c['feature']:20s} | {c['contribution_bps']:+.1f} bps | {c['verdict']} | {c['delta_return']:+.4f} |")
    
    # Key insights
    pos = [c for c in contributions if c["verdict"] == "positive"]
    neg = [c for c in contributions if c["verdict"] == "negative"]
    
    lines.extend([
        f"",
        f"## Key Insights",
    ])
    
    if pos:
        lines.append(f"### ✅ Positive Contributors ({len(pos)})")
        lines.append(f"核心alpha源: {', '.join(c['feature'] for c in pos[:3])}")
    
    if neg:
        lines.append(f"### ⚠️ Negative/Redundant ({len(neg)})")
        lines.append(f"可能冗余: {', '.join(c['feature'] for c in neg)}")
    
    if pos:
        lines.extend([
            f"",
            f"## Minimal Effective System",
            f"👉 {', '.join(c['feature'] for c in pos[:3])}",
        ])
    
    lines.extend([
        f"",
        f"---",
        f"*🤖 Ablation Engine v1 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])
    
    return "\n".join(lines)

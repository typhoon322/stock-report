"""
rotation/ci/report_generator.py — CI 报告输出
"""
import json, os
from datetime import datetime
from typing import Dict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_DIR = os.path.join(ROOT, "rotation", "ci", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def generate_ci_report(
    model_name: str,
    metrics: Dict,
    drift_result: Dict,
    decision: str,
    details: Dict = None,
) -> Dict:
    """生成CI报告"""
    report = {
        "model": model_name,
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "metrics": metrics,
        "drift": drift_result,
        "details": details or {},
    }
    return report


def save_ci_report(report: Dict):
    """保存 CI 报告"""
    date = datetime.now().strftime("%Y%m%d")
    model = report["model"].replace(" ", "_")
    
    # JSON
    json_path = os.path.join(REPORT_DIR, f"ci_report_{model}_{date}.json")
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    # Markdown
    md_path = os.path.join(REPORT_DIR, f"ci_report_{model}_{date}.md")
    md = format_ci_markdown(report)
    with open(md_path, 'w') as f:
        f.write(md)
    
    return json_path, md_path


def format_ci_markdown(report: Dict) -> str:
    """CI报告 → Markdown"""
    m = report.get("metrics", {})
    d = report.get("drift", {})
    decision = report["decision"]
    
    icon = "✅" if "APPROVED" in decision else "❌"
    
    return f"""# CI REPORT

## Model: {report['model']}
**Timestamp**: {report['timestamp']}

---

### Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| IC | {m.get('IC', 'N/A')} | > 0.05 | {'✅' if m.get('IC',0) and m['IC'] > 0.05 else '❌'} |
| Precision@Top10% | {m.get('precision_top10', 'N/A')} | > 0.55 | {'✅' if m.get('precision_top10',0) and m['precision_top10'] > 0.55 else '❌'} |
| Hit Rate | {m.get('hit_rate', 'N/A')} | > 0.50 | {'✅' if m.get('hit_rate',0) and m['hit_rate'] > 0.50 else '❌'} |
| Sharpe | {m.get('sharpe_proxy', 'N/A')} | > 0.5 | {'✅' if m.get('sharpe_proxy',0) and m['sharpe_proxy'] > 0.5 else '❌'} |
| Max Drawdown | {m.get('max_drawdown', 'N/A')} | < 20% | {'✅' if m.get('max_drawdown',0) and m['max_drawdown'] < 0.2 else '❌'} |
| Return vs Benchmark | {m.get('return_over_benchmark', 'N/A')} | > 0 | {'✅' if m.get('return_over_benchmark',0) and m['return_over_benchmark'] > 0 else '❌'} |

### Drift Check

| Check | Score | Status |
|-------|-------|--------|
| Distribution Shift | {d.get('drift_score', 'N/A')} | {d.get('drift_status', 'N/A')} |
| Alert | {'⚠️ YES' if d.get('alert') else '✅ NO'} | |

---

### Decision

# {icon} {decision}
"""

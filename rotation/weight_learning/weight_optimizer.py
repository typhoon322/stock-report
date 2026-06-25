"""
rotation/weight_learning/weight_optimizer.py — 在线权重优化 + 报告

主入口: trade_result → weight_update → next_cycle
"""
import os
from datetime import datetime
from typing import Dict, List
from .signal_tracker import record_trade, get_signal_performance, load_records
from .reward_function import attribute_contribution
from .weight_model import learn_weights, default_weights
from .weight_store import save_weights, load_current_weights

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_weights(
    signals: Dict[str, float],
    old_weights: Dict[str, float],
    pnl: float,
    regime: str = "rotation",
    learning_rate: float = 0.05,
) -> Dict:
    """
    核心: 交易结果 → 学习 → 更新权重
    
    new_weight = old_weight + LR × (signal_effectiveness × regime_modifier - old_weight)
    """
    # 记录交易
    record_trade(signals, sum(signals.get(k, 0) * old_weights.get(k, 0.1) for k in old_weights), pnl)
    
    # 归因: 各模块对PnL的贡献
    contributions = attribute_contribution(signals, old_weights, pnl)
    
    # 从历史数据学习新权重
    learned = learn_weights(regime)
    
    # 平滑更新
    new_weights = {}
    for k in old_weights:
        if k in learned:
            new_weights[k] = round(old_weights[k] + learning_rate * (learned[k] - old_weights[k]), 4)
        else:
            new_weights[k] = old_weights[k]
    
    # 归一化
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}
    
    # 保存
    save_weights(new_weights, regime)
    
    return new_weights, contributions


def generate_weight_report(weights: Dict[str, float], regime: str, perf: Dict, contributions: Dict) -> str:
    """生成权重报告 HTML"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Build rows
    old_data = load_current_weights()
    old_w = old_data.get("weights", {})
    
    rows = ""
    for name, w in weights.items():
        old = old_w.get(name, 0)
        delta = round(w - old, 4)
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        
        perf_info = perf.get(name, {})
        win_rate = perf_info.get("win_rate", 0)
        cont = contributions.get(name, 0)
        
        rows += f"""<tr>
            <td><code>{name}</code></td>
            <td>{w:.4f}</td>
            <td style="color:{'var(--r)' if delta>0 else ('var(--g)' if delta<0 else 'var(--t2)')}">{arrow} {delta:+.4f}</td>
            <td>{win_rate:.0%}</td>
            <td>{cont:+.1f}</td>
        </tr>"""
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Weight Report | {now[:10]}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
body{{font-family:-apple-system,'PingFang SC',sans-serif;background:var(--bg);color:var(--tx);padding:24px 16px;max-width:600px;margin:0 auto}}
h1{{color:var(--a);font-size:22px;text-align:center}}table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#222531;padding:8px 10px;text-align:left;color:var(--t2)}}
td{{padding:6px 10px;border-bottom:1px solid var(--bd)}}.footer{{margin-top:24px;text-align:center;font-size:10px;color:var(--t2)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-trend{{background:rgba(245,34,45,0.15);color:var(--r)}}.badge-rot{{background:rgba(99,102,241,0.15);color:var(--a)}}
</style></head><body>
<h1>🧬 Dynamic Weight Report</h1>
<p style="text-align:center;color:var(--t2);margin-bottom:20px">{now} · Regime: <span class="badge badge-{'trend' if 'trend' in regime else ('rot' if 'rotation' in regime else 'trend')}">{regime}</span></p>
<table><tr><th>Module</th><th>Weight</th><th>Delta</th><th>Win Rate</th><th>Contribution</th></tr>{rows}</table>
<div class="footer"><p>🧠 Dynamic Weight Learning Engine · Auto-generated</p><p>weights = old + LR × (learned − old)</p></div>
</body></html>"""


def run_learning_cycle(
    signals: Dict[str, float],
    pnl: float,
    regime: str = "rotation",
    learning_rate: float = 0.05,
) -> Dict:
    """完整学习周期"""
    old = load_current_weights()
    old_weights = old.get("weights", {})
    if not old_weights:
        old_weights = default_weights(regime)
    
    # 更新权重
    new_weights, contributions = update_weights(signals, old_weights, pnl, regime, learning_rate)
    
    # 获取性能统计
    perf = get_signal_performance()
    
    # 生成报告
    report_html = generate_weight_report(new_weights, regime, perf, contributions)
    report_path = os.path.join(ROOT, "docs", "weight_report.html")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(report_html)
    
    return {
        "old_weights": old_weights,
        "new_weights": new_weights,
        "contributions": contributions,
        "perf": perf,
        "regime": regime,
        "report_path": report_path,
    }

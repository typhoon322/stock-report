"""
Module Pruner — Identify and remove underperforming modules.

Decision logic:
1. For each module, compute marginal contribution from PnL records
2. If contribution < prune_threshold_bps for ≥ consistency_days: flag
3. If win_rate < prune_win_rate_min: flag regardless
4. Apply safeguards: max_prune_count, protected_modules
5. Generate pruning decision + rationale report

Pruning = setting weight to 0 in production config.
Does NOT delete code — modules can be re-enabled if market conditions change.
"""
import os


def prune_modules(pnl_records, training_result, config=None):
    """
    Evaluate each module for pruning.

    Args:
        pnl_records: output of compute_real_pnl()
        training_result: output of train_weights_from_pnl()
        config: PHASE2_CONFIG override

    Returns:
        {pruned: [...], kept: [...], decisions: {...}, report: str}
    """
    if config is None:
        from .config import PHASE2_CONFIG as config

    threshold = config.get("prune_threshold_bps", -5.0)
    consistency = config.get("prune_consistency_days", 15)
    win_rate_min = config.get("prune_win_rate_min", 0.30)
    max_prune = config.get("max_prune_count", 2)
    protected = set(config.get("protected_modules", []))

    modules_raw = pnl_records.get("modules", {})
    daily = pnl_records.get("daily", [])
    module_details = training_result.get("module_details", {})

    decisions = {}
    prune_candidates = []

    for mod, stats in modules_raw.items():
        if mod in protected:
            decisions[mod] = {"action": "protected", "reason": "protected module"}
            continue

        total_pnl = stats.get("total_pnl_bps", 0)
        win_rate = stats.get("win_rate", 0)
        days = stats.get("days_traded", 0)
        sharpe = stats.get("sharpe", 0)

        # Count underperforming days
        mod_daily_pnls = _collect_module_daily(daily, mod)
        bad_days = sum(1 for p in mod_daily_pnls if p < threshold)
        bad_ratio = bad_days / len(mod_daily_pnls) if mod_daily_pnls else 1

        reasons = []
        action = "keep"

        # Rule 1: Total PnL significantly negative
        if total_pnl < threshold * consistency:
            reasons.append(f"总PnL {total_pnl}bps < 阈值{threshold}bps × {consistency}天")

        # Rule 2: Win rate too low
        if win_rate < win_rate_min and days >= 10:
            reasons.append(f"胜率{win_rate:.0%} < {win_rate_min:.0%} (交易{days}天)")

        # Rule 3: Consistently underperforming
        if bad_ratio > 0.6 and days >= consistency:
            reasons.append(f"{bad_days}/{len(mod_daily_pnls)}天PnL < {threshold}bps ({bad_ratio:.0%})")

        # Rule 4: Negative Sharpe with enough samples
        if sharpe < -0.5 and days >= 15:
            reasons.append(f"Sharpe {sharpe} < -0.5 (样本{days}天)")

        if reasons:
            prune_candidates.append((mod, len(reasons), reasons, total_pnl))

        decisions[mod] = {
            "action": "keep",
            "total_pnl_bps": total_pnl,
            "win_rate": win_rate,
            "sharpe": sharpe,
            "days_traded": days,
            "bad_days": bad_days,
            "bad_ratio": round(bad_ratio, 2),
            "reasons": reasons,
            "weight": module_details.get(mod, {}).get("new_weight", 0),
        }

    # Select modules to prune (worst first, limited by max_prune_count)
    prune_candidates.sort(key=lambda x: x[3])  # sort by total_pnl ascending
    to_prune = prune_candidates[:max_prune]

    pruned_list = []
    for mod, score, reasons, total_pnl in to_prune:
        decisions[mod]["action"] = "prune"
        pruned_list.append({
            "module": mod,
            "total_pnl_bps": total_pnl,
            "reasons": reasons,
            "previous_weight": module_details.get(mod, {}).get("new_weight", 0),
        })

    kept_list = [mod for mod in modules_raw if decisions.get(mod, {}).get("action") != "prune"]

    # Generate report
    report_lines = ["# 模块剪枝决策报告", "", f"## 分析概览", "",
                    f"- 评估模块: {len(modules_raw)}", f"- 建议保留: {len(kept_list)}",
                    f"- 建议剪除: {len(pruned_list)}", f"- 策略: {config.get('prune_threshold_bps')}bps 阈值",
                    "", "## 决策明细", ""]

    for mod in sorted(decisions.keys()):
        d = decisions[mod]
        icon = "🗑️" if d["action"] == "prune" else "✅"
        report_lines.append(f"### {icon} {mod} ({d['action']})")
        report_lines.append(f"- PnL: {d['total_pnl_bps']}bps | 胜率: {d['win_rate']:.0%} | Sharpe: {d.get('sharpe',0)}")
        report_lines.append(f"- 权重: {d.get('weight',0):.4f} | 负贡献天数: {d['bad_days']}/{d.get('days_traded',0)}")
        if d["reasons"]:
            for r in d["reasons"]:
                report_lines.append(f"  - {r}")
        report_lines.append("")

    if pruned_list:
        report_lines.append("## 剪除模块详情")
        report_lines.append("")
        report_lines.append("| 模块 | PnL (bps) | 原因 |")
        report_lines.append("|------|-----------|------|")
        for p in pruned_list:
            report_lines.append(f"| {p['module']} | {p['total_pnl_bps']} | {'; '.join(p['reasons'][:2])} |")
        report_lines.append("")
        report_lines.append("> ⚠️ 剪除后模块代码保留，权重设为0。市场环境变化时可重新激活。")

    return {
        "pruned": pruned_list,
        "kept": kept_list,
        "decisions": decisions,
        "report": "\n".join(report_lines),
        "prune_count": len(pruned_list),
    }


def apply_pruning(weights, prune_result):
    """Apply pruning decisions: set pruned modules to weight 0, renormalize."""
    pruned_mods = {p["module"] for p in prune_result.get("pruned", [])}
    new_weights = {}
    for mod, w in weights.items():
        new_weights[mod] = 0 if mod in pruned_mods else w
    total = sum(new_weights.values())
    if total > 0:
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}
    return new_weights


def _collect_module_daily(daily_records, module_name):
    """Collect per-day PnL for a specific module."""
    result = []
    for d in daily_records:
        mpnl = d.get("module_pnl_bps", {})
        if module_name in mpnl:
            result.append(mpnl[module_name])
    return result

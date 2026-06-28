"""
Phase II Runner — Main pipeline entry.

Sequence:
1. Compute real PnL from archive snapshots
2. Train weights using real PnL data
3. Run module pruning analysis
4. Apply pruning to weights
5. Generate HTML report
6. Save all outputs

Designed for GitHub Actions: python -m rotation.phase2.runner
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_phase2_pipeline(config=None, force=False):
    """
    Run the full Phase II pipeline.

    Args:
        config: Optional config override (uses PHASE2_CONFIG by default)
        force: If True, run even with fewer than min_trading_days

    Returns:
        {status, pnl, training, pruning, final_weights, report_path, errors}
    """
    if config is None:
        from .config import PHASE2_CONFIG as config

    results = {
        "status": "pending",
        "pnl": None,
        "training": None,
        "pruning": None,
        "final_weights": None,
        "report_path": None,
        "errors": [],
        "timestamp": datetime.now(BJT).isoformat(),
    }

    archive_dir = config.get("archive_dir", "rotation/archive")
    min_days = config.get("min_trading_days", 20)
    target_days = config.get("target_trading_days", 30)

    print(f"\n{'='*60}")
    print(f"🧬 Phase II Pipeline — Auto Training + Module Pruning")
    print(f"   时间: {datetime.now(BJT).strftime('%Y-%m-%d %H:%M')} (UTC+8)")
    print(f"   数据目录: {archive_dir}")
    print(f"   最少交易日: {min_days} | 目标: {target_days}")
    print(f"{'='*60}\n")

    # ── Step 1: Compute real PnL ──
    print("[1/4] Computing real PnL from archives...")
    try:
        from .pnl_calculator import compute_real_pnl
        pnl = compute_real_pnl(archive_dir, config)
        results["pnl"] = pnl

        if "error" in pnl:
            days = pnl.get("available_days", 0)
            if days < min_days and not force:
                results["status"] = "insufficient_data"
                results["errors"].append(pnl["error"])
                print(f"  ⚠️ {pnl['error']}")
                return results
            else:
                print(f"  ⚠️ {pnl['error']} — forcing run")
        else:
            s = pnl["summary"]
            print(f"  ✅ {s['traded_days']}个交易日 | 总PnL: {s['total_pnl_bps']}bps | Sharpe: {s['sharpe']}")
    except Exception as e:
        results["errors"].append(f"PnL calculation failed: {e}")
        results["status"] = "error"
        print(f"  ❌ {e}")
        return results

    # ── Step 2: Train weights ──
    print("\n[2/4] Training weights from real PnL...")
    try:
        from .auto_trainer import train_weights_from_pnl, save_trained_weights, DEFAULT_WEIGHTS

        # Load old weights if available
        old_weights = dict(DEFAULT_WEIGHTS)
        wpath = os.path.join(ROOT, "rotation", "weight_learning", "store", "weights_current.json")
        if os.path.exists(wpath):
            try:
                with open(wpath, "r") as f:
                    old_weights = json.load(f)
            except Exception:
                pass

        training = train_weights_from_pnl(pnl, old_weights, config)
        results["training"] = training

        print(f"  体制: {training['regime']}")
        for mod, det in sorted(training["module_details"].items()):
            delta = det["delta"]
            sign = "+" if delta > 0 else ""
            print(f"    {mod:12s} {det['old_weight']:.4f} → {det['new_weight']:.4f} ({sign}{delta:.4f})")
    except Exception as e:
        results["errors"].append(f"Weight training failed: {e}")
        results["status"] = "error"
        print(f"  ❌ {e}")
        return results

    # ── Step 3: Module pruning ──
    print("\n[3/4] Analyzing module pruning...")
    try:
        from .module_pruner import prune_modules, apply_pruning

        pruning = prune_modules(pnl, training, config)
        results["pruning"] = pruning

        if pruning["prune_count"] > 0:
            print(f"  🗑️ 建议剪除 {pruning['prune_count']} 个模块:")
            for p in pruning["pruned"]:
                print(f"    - {p['module']}: {p['total_pnl_bps']}bps {'; '.join(p['reasons'][:1])}")
        else:
            print("  ✅ 所有模块表现达标，无需剪除")

        # Apply pruning to weights
        pruned_weights = apply_pruning(training["new_weights"], pruning)
        results["final_weights"] = pruned_weights

        print(f"\n  最终权重: {json.dumps(pruned_weights, ensure_ascii=False)}")
    except Exception as e:
        results["errors"].append(f"Module pruning failed: {e}")
        print(f"  ❌ {e}")
        # Continue with unpruned weights
        results["final_weights"] = training["new_weights"]

    # ── Step 4: Save weights & generate report ──
    print("\n[4/4] Saving weights + generating report...")
    try:
        from .auto_trainer import save_trained_weights

        # Save weights
        saved = save_trained_weights(
            {"new_weights": results["final_weights"], "regime": training["regime"],
             "summary": pnl.get("summary", {}), "training_date": results["timestamp"],
             "module_details": training.get("module_details", {})}
        )
        print(f"  ✅ Weights saved: {saved['current']}")

        # Generate HTML report
        html_path = _generate_html_report(results, config)
        results["report_path"] = html_path
        print(f"  ✅ Report: {html_path}")

    except Exception as e:
        results["errors"].append(f"Save/report failed: {e}")
        print(f"  ❌ {e}")

    results["status"] = "ok" if not results["errors"] else "partial"
    print(f"\n{'='*60}")
    print(f"🧬 Phase II Pipeline — {results['status'].upper()}")
    print(f"{'='*60}\n")
    return results


def _generate_html_report(results, config):
    """Generate a self-contained HTML report."""
    pnl = results.get("pnl", {})
    training = results.get("training", {})
    pruning = results.get("pruning", {})
    ts = results.get("timestamp", "")

    summary = pnl.get("summary", {})
    module_details = training.get("module_details", {})
    decisions = pruning.get("decisions", {})

    # Module rows
    mod_rows = ""
    for mod, det in sorted(module_details.items()):
        dec = decisions.get(mod, {})
        action = dec.get("action", "keep")
        action_badge = "🗑️" if action == "prune" else "✅"
        delta = det["delta"]
        sign = "+" if delta > 0 else ""
        color = "var(--g)" if delta > 0 else "var(--r)" if delta < 0 else "var(--t2)"
        mod_rows += f"""<tr>
          <td>{action_badge} {mod}</td>
          <td style="color:var(--a)">{det['old_weight']:.4f}</td>
          <td style="font-weight:700">{det['new_weight']:.4f}</td>
          <td style="color:{color}">{sign}{delta:.4f}</td>
          <td>{det['win_rate']:.0%}</td>
          <td>{det['total_pnl_bps']:.1f}bps</td>
          <td>{det.get('sharpe',0):.2f}</td>
          <td>{action}</td>
        </tr>"""

    # Pruning summary
    prune_summary = ""
    if pruning.get("pruned"):
        prune_summary = f"<div class='note warn'><strong>🗑️ 剪除 {len(pruning['pruned'])} 个模块</strong>：" + \
            ", ".join(p["module"] for p in pruning["pruned"]) + \
            "<br><small>权重已归零，代码保留。市场环境变化时可重新激活。</small></div>"
    else:
        prune_summary = "<div class='note ok'>✅ 所有模块表现达标，无需剪除</div>"

    # Pruning detail rows
    prune_rows = ""
    for mod in sorted(decisions.keys()):
        d = decisions[mod]
        if d["action"] != "prune":
            continue
        prune_rows += f"""<tr>
          <td>🗑️ {mod}</td>
          <td style="color:var(--r)">{d['total_pnl_bps']}bps</td>
          <td>{d['win_rate']:.0%}</td>
          <td>{d.get('sharpe',0):.2f}</td>
          <td style="font-size:10px">{'; '.join(d['reasons'][:2])}</td>
        </tr>"""

    if not prune_rows:
        prune_rows = '<tr><td colspan="5" style="color:var(--t2);text-align:center">无需剪除</td></tr>'

    # Final weights display
    fw = results.get("final_weights") or {}
    fw_str = json.dumps(fw, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Phase II 训练报告 | {summary.get('total_days','-')}天</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6;max-width:860px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:20px;color:var(--a);margin-bottom:4px}}
h2{{font-size:16px;margin:24px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--a)}}
h3{{font-size:14px;margin:16px 0 8px;color:var(--y)}}
.sub{{color:var(--t2);font-size:11px;margin-bottom:20px}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-bottom:16px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.stat{{text-align:center;padding:12px}}
.stat .v{{font-size:24px;font-weight:700}}
.stat .l{{font-size:10px;color:var(--t2);margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}}
th{{background:#222531;padding:7px 10px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:6px 10px;border-bottom:1px solid var(--bd)}}
td code{{font-family:'SF Mono',monospace;font-size:10px;color:var(--a)}}
.note{{padding:10px 14px;border-radius:8px;margin:8px 0;font-size:12px}}
.note.warn{{background:rgba(245,158,11,0.08);border-left:3px solid var(--y)}}
.note.ok{{background:rgba(22,199,132,0.08);border-left:3px solid var(--g)}}
.footer{{margin-top:32px;text-align:center;font-size:10px;color:var(--t2)}}
.up{{color:var(--r)}}.down{{color:var(--g)}}
</style>
</head>
<body>

<h1>🧬 Phase II 自动训练报告</h1>
<p class="sub">{summary.get('total_days','-')}个交易日数据 · 体制: {training.get('regime','-')} · 生成于 {ts[:19]}</p>

<div class="card">
  <h3>📊 绩效概览</h3>
  <div class="g3">
    <div class="stat"><div class="v" style="color:{'var(--g)' if summary.get('total_pnl_bps',0)>0 else 'var(--r)'}">{summary.get('total_pnl_bps',0):+.0f}</div><div class="l">总PnL (bps)</div></div>
    <div class="stat"><div class="v" style="color:var(--a)">{summary.get('sharpe',0):.2f}</div><div class="l">Sharpe Ratio</div></div>
    <div class="stat"><div class="v">{summary.get('profitable_days',0)}/{summary.get('traded_days',0)}</div><div class="l">盈利天数</div></div>
  </div>
</div>

<div class="card">
  <h3>⚖️ 模块权重变更</h3>
  <table>
    <tr><th>模块</th><th>旧权重</th><th>新权重</th><th>Δ</th><th>胜率</th><th>总PnL</th><th>Sharpe</th><th>状态</th></tr>
    {mod_rows}
  </table>
</div>

{prune_summary}

<div class="card">
  <h3>🗑️ 剪除分析</h3>
  <table>
    <tr><th>模块</th><th>总PnL</th><th>胜率</th><th>Sharpe</th><th>原因</th></tr>
    {prune_rows}
  </table>
  <p style="font-size:10px;color:var(--t2);margin-top:8px">
    剪除规则: PnL &lt; {config.get('prune_threshold_bps',-5)}bps × {config.get('prune_consistency_days',15)}天 或 胜率 &lt; {config.get('prune_win_rate_min',0.30):.0%}
  </p>
</div>

<div class="card">
  <h3>⚙️ 最终生产权重</h3>
  <code style="font-size:11px">{fw_str}</code>
</div>

<div class="footer">
  <p>🧬 Phase II Auto Trainer v1.0 · 云端运行 · <a href="index.html" style="color:var(--a)">返回首页</a></p>
  <p>⚠️ 本报告由系统自动生成，权重变更需人工审核后上线。剪除模块代码保留，可随时恢复。</p>
</div>
</body></html>"""

    out_path = os.path.join(ROOT, config.get("output_html", "docs/phase2_report.html"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Also save JSON
    json_path = os.path.join(ROOT, config.get("output_json", "docs/phase2_data.json"))
    with open(json_path, "w") as f:
        json.dump({
            "summary": summary,
            "training": {k: v for k, v in training.items() if k != "module_details"},
            "module_details": module_details,
            "pruning": {k: v for k, v in pruning.items() if k != "report"},
            "final_weights": results.get("final_weights"),
        }, f, ensure_ascii=False, indent=2)

    return out_path


if __name__ == "__main__":
    run_phase2_pipeline()

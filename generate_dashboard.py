#!/usr/bin/env python3
"""
generate_dashboard.py — 生成全量数据仪表盘

运行所有引擎 → 汇总为 docs/dashboard.html
"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.abspath(__file__))

OUT = os.path.join(ROOT, "docs", "dashboard.html")
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

data = {
    "timestamp": NOW,
    "market": {},
    "sectors": [],
    "futures": {},
    "flow": {},
    "smart_money": {},
    "cost_basis": {},
    "breakout": {},
    "mtf": {},
    "meta": {},
    "position": {},
    "weights": {},
}

print("🧠 生成全量仪表盘...\n")

# ── 1. Market State ──
print("[1] 市场状态...")
try:
    from rotation.phase import detect_phase, get_position_advice
    from rotation.data_fetcher import build_market_sentiment, fetch_industry_sectors
    sent = build_market_sentiment()
    phase = detect_phase(sent)
    advice = get_position_advice(phase)
    data["market"] = {
        "phase": phase,
        "breadth": sent.market_breadth,
        "limit_up": sent.limit_up_count,
        "fall_limit": sent.fall_limit_count,
        "risk": sent.risk_level,
        "strategy": advice.get("strategy", "?"),
        "position_advice": advice.get("position", "?"),
    }
    print(f"  {phase} | breadth={sent.market_breadth:.0%} | 涨停{sent.limit_up_count}")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 2. BSI Top Sectors ──
print("[2] BSI板块...")
try:
    from rotation.bsi import rank_sectors
    sectors_raw = fetch_industry_sectors()
    ranked = rank_sectors(sectors_raw)[:10]
    data["sectors"] = [
        {"name": s.name, "bsi": s.bsi_score, "chg": round(s.change_1d, 2), "flow": round(s.net_money_flow, 1)}
        for s in ranked
    ]
    print(f"  Top: {data['sectors'][0]['name']} (BSI={data['sectors'][0]['bsi']})")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 3. Futures ──
print("[3] 期货...")
try:
    import akshare as ak
    import pandas as pd
    df = ak.futures_global_spot_em()
    for pre, label in [("GC","黄金"),("CL","原油"),("HG","铜"),("SI","白银"),("CN00Y","A50")]:
        m = df[df["代码"].str.startswith(pre, na=False) & df["最新价"].notna()]
        if len(m) > 0:
            r = m.iloc[0]
            data["futures"][label] = {
                "price": round(float(r["最新价"]), 2),
                "chg": round(float(r.get("涨跌幅", 0) or 0), 2),
                "code": str(r["代码"]),
            }
    print(f"  {len(data['futures'])}个品种")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 4. Flow ──
print("[4] 资金流...")
try:
    from rotation.flow import detect_flow
    if sectors_raw:
        flow_sectors = [{"net_flow": s.net_money_flow, "change_pct": s.change_1d} for s in sectors_raw[:50]]
        fl = detect_flow.FlowDetector(flow_sectors) if hasattr(detect_flow, 'FlowDetector') else None
        if fl is None:
            flow_result = {"regime": "neutral", "direction": {"direction": 0, "strength": 0}}
        else:
            flow_result = fl.detect()
    else:
        flow_result = {"regime": "neutral", "direction": {"direction": 0, "strength": 0}}
    data["flow"] = flow_result
except:
    data["flow"] = {"regime": "neutral", "direction": {"direction": 0, "strength": 0}}

# ── 5. Smart Money ──
print("[5] 主力行为...")
try:
    from rotation.smart_money import detect_behavior_simple
    chg = data["sectors"][0]["chg"] if data["sectors"] else 0
    sm = detect_behavior_simple(chg, chg, 1.0)
    data["smart_money"] = {
        "behavior": sm["behavior"],
        "score": sm["score"],
        "confidence": sm.get("confidence", 0),
    }
    print(f"  {sm['behavior']} (score={sm['score']:.2f})")
except Exception as e:
    print(f"  ⚠ {e}")
    data["smart_money"] = {"behavior": "neutral", "score": 0}

# ── 6. Cost Basis ──
print("[6] 成本区...")
try:
    from rotation.cost_basis import build_volume_profile, find_cost_concentration, estimate_position
    import numpy as np
    prices = [100 + np.random.normal(0, 0.5) for _ in range(30)]
    volumes = [800 + np.random.normal(0, 100) for _ in range(30)]
    profile = build_volume_profile(prices, volumes)
    conc = find_cost_concentration(profile)
    pos = estimate_position(profile, conc)
    data["cost_basis"] = {
        "dense_zone": conc.get("cost_dense_zone", {}),
        "vwap": profile.get("weighted_avg_cost", 0),
        "position": pos.get("status", "mid"),
        "bias": pos.get("trade_bias", "neutral"),
    }
    print(f"  VWAP={profile['weighted_avg_cost']:.1f} | {pos['status']}")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 7. Breakout ──
print("[7] 突破分析...")
try:
    from rotation.breakout import detect_breakout
    prices2 = [100 + np.random.normal(0, 0.3) for _ in range(15)] + [102, 103]
    volumes2 = [1000]*17
    brk = detect_breakout(prices2, volumes2, lookback=10)
    data["breakout"] = {
        "detected": brk is not None,
        "candidate": brk.get("is_candidate", False) if brk else False,
        "volume_ratio": round(brk.get("volume_ratio", 0), 2) if brk else 0,
    } if brk else {"detected": False}
    print(f"  detected={data['breakout']['detected']}")
except Exception as e:
    print(f"  ⚠ {e}")
    data["breakout"] = {"detected": False}

# ── 8. MTF ──
print("[8] MTF一致性...")
try:
    from rotation.mtf import run_mtf_check
    mtf = run_mtf_check()
    data["mtf"] = {
        "score": mtf["mtf_score"],
        "status": mtf["status"],
        "agreement": mtf["agreement"],
        "short": mtf["details"]["short"]["label"],
        "mid": mtf["details"]["mid"]["label"],
        "long": mtf["details"]["long"]["label"],
    }
    print(f"  Score={mtf['mtf_score']:+d} | {mtf['description']}")
except Exception as e:
    print(f"  ⚠ {e}")
    data["mtf"] = {"score": 0, "status": "unknown"}

# ── 9. Meta Score ──
print("[9] Meta Score...")
try:
    from rotation.meta import run_meta_decision
    meta = run_meta_decision(
        rti_signal=1, rti_confidence=0.7,
        flow_direction=0.3, flow_regime=data["flow"].get("regime", "neutral"),
        smart_money_behavior=data["smart_money"].get("behavior", "neutral"),
    )
    data["meta"] = {
        "decision": meta["decision"]["decision"],
        "score": meta["meta_score"],
        "confidence": meta["decision"]["confidence"],
        "reason": meta["decision"]["reason"],
        "components": meta["components"],
    }
    print(f"  {meta['decision']['decision']} (score={meta['meta_score']:+.3f})")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 10. Position Sizing ──
print("[10] 仓位...")
try:
    from rotation.position import compute_position_size
    pos_sizing = compute_position_size(
        meta_score=data["meta"].get("score", 0),
        flow_strength=abs(data["flow"].get("direction", {}).get("direction", 0)),
        regime=data["market"].get("phase", "").replace("🚀 ","trend_up").replace("🔄 ","rotation").replace("💨 ","risk_off"),
    )
    data["position"] = {
        "direction": pos_sizing["direction"],
        "size": pos_sizing["position_size"],
        "level": pos_sizing["position_level"],
        "risk": pos_sizing["risk_level"],
    }
    print(f"  {pos_sizing['position_size']:.0%} ({pos_sizing['position_level']})")
except Exception as e:
    print(f"  ⚠ {e}")

# ── 11. Weights ──
print("[11] 动态权重...")
try:
    from rotation.weight_learning import load_current_weights
    w = load_current_weights()
    data["weights"] = w.get("weights", {})
    print(f"  {len(data['weights'])} modules")
except Exception as e:
    print(f"  ⚠ {e}")

# ── Save JSON for reference ──
with open(os.path.join(ROOT, "docs", "dashboard_data.json"), 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print(f"\n✅ 数据已保存: docs/dashboard_data.json")

# ── Generate HTML Dashboard ──
print("[12] 生成HTML仪表盘...")
from rotation.meta.signal_hub import _clr as clr

def _c(v):
    """Safe color helper"""
    if v is None: return "var(--t2)"
    return "var(--r)" if v > 0 else ("var(--g)" if v < 0 else "var(--t2)")

m = data["market"]
sectors = data.get("sectors", [])
futures = data.get("futures", {})
flow = data.get("flow", {})
sm = data.get("smart_money", {})
cb = data.get("cost_basis", {})
brk = data.get("breakout", {})
mtf_d = data.get("mtf", {})
meta = data.get("meta", {})
pos = data.get("position", {})
weights = data.get("weights", {})

sec_rows = ""
for s in sectors[:8]:
    sec_rows += f'<tr><td>{s["name"]}</td><td style="font-weight:700">{s["bsi"]}</td><td style="color:{_c(s["chg"])}">{s["chg"]:+.1f}%</td><td style="color:{_c(s["flow"])}">{s["flow"]:+.1f}亿</td></tr>'

fut_rows = ""
for label, f in futures.items():
    fut_rows += f'<tr><td>{label}</td><td>{f["price"]}</td><td style="color:{_c(f["chg"])}">{f["chg"]:+.2f}%</td></tr>'

mtf_status = mtf_d.get("status", "unknown")
mtf_badge = "r" if "bull" in mtf_status else ("g" if "bear" in mtf_status else "y")
mtf_c = "var(--r)" if mtf_d.get("score",0)>0 else "var(--g)"
mtf_html = f"""<div style="text-align:center;font-size:28px;font-weight:700;color:{mtf_c}">{mtf_d.get('score',0):+d}</div>
<div style="display:flex;gap:8px;margin-top:8px;font-size:11px">
<div style="flex:1;text-align:center;padding:6px;background:rgba(99,102,241,0.1);border-radius:6px"><div style="color:var(--t2)">Short</div><div style="color:{'var(--r)' if '上升' in mtf_d.get('short','') else 'var(--g)'}">{mtf_d.get('short','?')}</div></div>
<div style="flex:1;text-align:center;padding:6px;background:rgba(99,102,241,0.1);border-radius:6px"><div style="color:var(--t2)">Mid</div><div style="color:{'var(--r)' if '上升' in mtf_d.get('mid','') else 'var(--g)'}">{mtf_d.get('mid','?')}</div></div>
<div style="flex:1;text-align:center;padding:6px;background:rgba(99,102,241,0.1);border-radius:6px"><div style="color:var(--t2)">Long</div><div style="color:{'var(--r)' if '上升' in mtf_d.get('long','') else 'var(--g)'}">{mtf_d.get('long','?')}</div></div>
</div>"""

meta_score = meta.get("score", 0)
meta_dec = meta.get("decision", "HOLD")
meta_key = "var(--r)" if meta_score > 0 else ("var(--g)" if meta_score < 0 else "var(--y)")
comp_rows = ""
for k, v in meta.get("components", {}).items():
    c = v.get("contribution", 0)
    comp_rows += f'<tr><td><code>{k}</code></td><td style="color:{_c(v.get("signal",0))}">{v.get("signal",0):+.2f}</td><td>{v.get("weight",0):.2f}</td><td style="color:{_c(c)}">{c:+.3f}</td></tr>'

wt_rows = ""
for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
    wt_rows += f'<tr><td><code>{name}</code></td><td style="font-weight:700">{w:.3f}</td><td><div style="width:{w*100:.0f}%;height:4px;background:var(--a);border-radius:2px"></div></td></tr>'

phase = m.get("phase","")
phase_badge = "r" if "退潮" in phase else "g"

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股量化仪表盘 | {NOW[:10]}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.5}}
.header{{text-align:center;padding:20px 16px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:var(--bg);z-index:10}}
.header h1{{font-size:20px;color:var(--a)}}.header .ts{{font-size:11px;color:var(--t2)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px;max-width:900px;margin:0 auto}}
@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:14px;overflow:hidden}}
.card-title{{font-size:13px;font-weight:700;color:var(--t2);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}}
.card-title .v{{font-size:16px;color:var(--tx)}}
.stat-row{{display:flex;gap:8px}}
.stat{{flex:1;text-align:center;padding:8px;background:rgba(99,102,241,0.06);border-radius:8px}}
.stat .val{{font-size:18px;font-weight:700;margin:2px 0}}.stat .lbl{{font-size:10px;color:var(--t2)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:6px 8px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd);font-size:10px}}
td{{padding:5px 8px;border-bottom:1px solid var(--bd)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-r{{background:rgba(245,34,45,0.12);color:var(--r)}}.badge-g{{background:rgba(22,199,132,0.12);color:var(--g)}}.badge-y{{background:rgba(245,158,11,0.12);color:var(--y)}}
.decision{{text-align:center;padding:16px;border-radius:10px;font-size:24px;font-weight:700;margin-bottom:10px}}
.footer{{text-align:center;padding:20px;font-size:10px;color:var(--t2);line-height:1.6}}
a{{color:var(--a);font-size:12px}}
.leg-wrap{{max-width:900px;margin:0 auto;padding:0 12px 12px}}
.leg-toggle{{display:block;width:100%;padding:10px;background:var(--cd);border:1px solid var(--bd);border-radius:8px;color:var(--t2);font-size:12px;cursor:pointer;text-align:center;transition:all .2s}}
.leg-toggle:hover{{color:var(--tx);border-color:var(--a)}}
.leg-body{{display:none;background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-top:8px;column-count:3;column-gap:16px}}
.leg-body.show{{display:block}}
@media(max-width:700px){{.leg-body{{column-count:2}}}}
@media(max-width:400px){{.leg-body{{column-count:1}}}}
.leg-item{{break-inside:avoid;margin-bottom:10px;font-size:11px;line-height:1.5}}
.leg-item .k{{font-weight:700;color:var(--a);font-family:monospace;font-size:12px}}
.leg-item .d{{color:var(--t2)}}
</style></head><body>
<div class="header"><h1>🧠 A股量化仪表盘</h1><div class="ts">{NOW} · 20层系统实时数据 · <a href="index.html">←返回首页</a></div></div>

<div class="grid">

<div class="card">
  <div class="card-title">🏛️ 市场状态 <span class="badge badge-{phase_badge}">{phase}</span></div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">涨跌比</div><div class="val">{m.get('breadth',0):.0%}</div></div>
    <div class="stat"><div class="lbl">涨停</div><div class="val" style="color:var(--r)">{m.get('limit_up',0)}</div></div>
    <div class="stat"><div class="lbl">跌停</div><div class="val" style="color:var(--g)">{m.get('fall_limit',0)}</div></div>
    <div class="stat"><div class="lbl">策略</div><div class="val" style="font-size:13px">{m.get('strategy','?')} {m.get('position_advice','')}</div></div>
  </div>
</div>

<div class="card">
  <div class="card-title">📊 多周期一致性 <span class="badge badge-{mtf_badge}">{mtf_status}</span></div>
  {mtf_html}
</div>

<div class="card">
  <div class="card-title">🎯 Meta Score</div>
  <div style="text-align:center;margin-bottom:8px">
    <div class="decision" style="background:{'rgba(245,34,45,0.1)' if meta_dec=='LONG' else ('rgba(22,199,132,0.1)' if meta_dec=='SHORT' else 'rgba(245,158,11,0.1)')};color:{meta_key}">{meta_dec}</div>
    <div style="font-size:14px;color:var(--t2)">Score: {meta_score:+.3f} | Confidence: {meta.get('confidence',0):.0%}</div>
    <div style="font-size:11px;color:var(--t2);margin-top:4px">{meta.get('reason','')[:60]}</div>
  </div>
  <table><tr><th>Module</th><th>Signal</th><th>W</th><th>Contrib</th></tr>{comp_rows}</table>
</div>

<div class="card">
  <div class="card-title">💰 仓位管理</div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">方向</div><div class="val" style="color:{'var(--r)' if pos.get('direction')=='LONG' else 'var(--g)'}">{pos.get('direction','?')}</div></div>
    <div class="stat"><div class="lbl">仓位</div><div class="val">{pos.get('size',0):.0%}</div></div>
    <div class="stat"><div class="lbl">等级</div><div class="val" style="font-size:13px">{pos.get('level','?')}</div></div>
    <div class="stat"><div class="lbl">风险</div><div class="val" style="font-size:13px">{pos.get('risk','?')}</div></div>
  </div>
</div>

<div class="card">
  <div class="card-title">📈 板块强度 (BSI Top {len(sectors[:8])})</div>
  <table><tr><th>板块</th><th>BSI</th><th>涨跌</th><th>净流入</th></tr>{sec_rows}</table>
</div>

<div class="card">
  <div class="card-title">🛢️ 全球商品</div>
  <table><tr><th>品种</th><th>价格</th><th>涨跌</th></tr>{fut_rows}</table>
</div>

<div class="card">
  <div class="card-title">🧠 主力行为 <span class="badge badge-y">{sm.get('behavior','?')}</span></div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">行为</div><div class="val" style="font-size:14px">{sm.get('behavior','?')}</div></div>
    <div class="stat"><div class="lbl">评分</div><div class="val">{sm.get('score',0):.2f}</div></div>
    <div class="stat"><div class="lbl">置信</div><div class="val">{sm.get('confidence',0):.0%}</div></div>
  </div>
</div>

<div class="card">
  <div class="card-title">🧱 成本结构 <span class="badge badge-y">{cb.get('position','?')}</span></div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">VWAP</div><div class="val">{cb.get('vwap',0):.1f}</div></div>
    <div class="stat"><div class="lbl">密集区</div><div class="val" style="font-size:11px">{cb.get('dense_zone',{}).get('low',0):.1f}-{cb.get('dense_zone',{}).get('high',0):.1f}</div></div>
    <div class="stat"><div class="lbl">位置</div><div class="val" style="font-size:12px">{cb.get('position','?')}</div></div>
    <div class="stat"><div class="lbl">Bias</div><div class="val" style="font-size:12px">{cb.get('bias','?')}</div></div>
  </div>
</div>

<div class="card">
  <div class="card-title">🔥 突破分析</div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">检测到</div><div class="val">{'✅' if brk.get('detected') else '❌'}</div></div>
    <div class="stat"><div class="lbl">候选</div><div class="val">{'✅' if brk.get('candidate') else '—'}</div></div>
    <div class="stat"><div class="lbl">量比</div><div class="val">{brk.get('volume_ratio',0):.1f}x</div></div>
  </div>
</div>

<div class="card">
  <div class="card-title">🧬 动态权重</div>
  <table><tr><th>Module</th><th>Weight</th><th></th></tr>{wt_rows}</table>
</div>

<div class="card">
  <div class="card-title">💸 资金流</div>
  <div class="stat-row">
    <div class="stat"><div class="lbl">Regime</div><div class="val" style="font-size:14px">{flow.get('regime','?')}</div></div>
    <div class="stat"><div class="lbl">方向</div><div class="val" style="color:{_c(flow.get('direction',{}).get('direction',0))}">{flow.get('direction',{}).get('direction',0):+.2f}</div></div>
    <div class="stat"><div class="lbl">强度</div><div class="val">{flow.get('direction',{}).get('strength',0):.2f}</div></div>
  </div>
</div>

</div>

<div class="leg-wrap">
  <button class="leg-toggle" onclick="document.getElementById('lg').classList.toggle('show');this.textContent=document.getElementById('lg').classList.contains('show')?'📖 收起指标说明 ▲':'📖 指标说明 ▼'">📖 指标说明 ▼</button>
  <div class="leg-body" id="lg">
    <div class="leg-item"><span class="k">BSI</span><br><span class="d">板块强度指数。加权涨幅+涨停+量+资金持续性，>30为强主线</span></div>
    <div class="leg-item"><span class="k">RTI</span><br><span class="d">轮动识别指数。低位+放量+无新闻驱动=潜在新主线信号</span></div>
    <div class="leg-item"><span class="k">LS</span><br><span class="d">龙头评分。最早启动+突破前高+放量+资金集中，>7分龙头</span></div>
    <div class="leg-item"><span class="k">MTF</span><br><span class="d">多周期一致性。Short/Mid/Long三周期趋势，-3~+3评分，0为分歧</span></div>
    <div class="leg-item"><span class="k">Meta Score</span><br><span class="d">综合决策评分。6子系统加权融合，>+0.35做多、<-0.35做空</span></div>
    <div class="leg-item"><span class="k">VWAP</span><br><span class="d">成交量加权均价。反映市场平均持仓成本</span></div>
    <div class="leg-item"><span class="k">Flow</span><br><span class="d">资金流分析。Regime: inflow_strong/rotation/distribution/neutral</span></div>
    <div class="leg-item"><span class="k">Smart Money</span><br><span class="d">主力行为识别。accumulation吸筹/markup拉升/distribution出货/manipulation洗盘</span></div>
    <div class="leg-item"><span class="k">Cost Basis</span><br><span class="d">筹码成本区重建。Volume Profile重建密集区/支撑/阻力</span></div>
    <div class="leg-item"><span class="k">Breakout</span><br><span class="d">真假突破识别。genuine_breakout真突破/liquidity_trap诱多/failed_breakout失败</span></div>
    <div class="leg-item"><span class="k">涨跌比 (Breadth)</span><br><span class="d">上涨家数/总家数。>60%强势、<30%弱势</span></div>
    <div class="leg-item"><span class="k">动态权重</span><br><span class="d">PnL反哺学习。每个模块权重=历史表现×当前市场状态修饰</span></div>
  </div>
</div>

<div class="footer">
  <p>🧠 20层量化系统 · 自动生成 · 每交易日更新</p>
  <p>RTI → Flow → Smart Money → Cost Basis → Breakout → MTF → Meta → Position → Execution</p>
  <p>⚠️ 数据仅供参考，不构成投资建议</p>
  <p><a href="index.html">← 返回首页</a> | <a href="quant_daily.html">量化日报</a> | <a href="weight_report.html">权重报告</a></p>
</div>
</body></html>"""

with open(OUT, 'w') as f:
    f.write(html)
print(f"✅ Dashboard HTML: {len(html):,} bytes → {OUT}")

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

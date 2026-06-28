"""
Auto Trainer — Learn weights from real PnL data after 30 days.

Uses the same learning logic as weight_model.py but fed with
real computed PnL instead of simulated/synthetic data.

Process:
1. Read per-module PnL stats from compute_real_pnl()
2. Compute effectiveness = win_rate * max(avg_pnl * 50, 0.01)
3. Apply regime modifier (from existing weight_model.py)
4. Normalize to sum=1.0
5. Smooth update: new = old + LR * (learned - old)
6. Save versioned weights + update current
"""
import json, os, sys
from datetime import datetime, timezone, timedelta


BJT = timezone(timedelta(hours=8))

# Regime modifiers — kept in sync with weight_learning/weight_model.py
REGIME_MODIFIERS = {
    "rti":         {"trend": 1.0, "rotation": 1.3, "choppy": 0.7, "risk_off": 0.4},
    "flow":        {"trend": 1.3, "rotation": 1.1, "choppy": 0.7, "risk_off": 0.4},
    "smart_money": {"trend": 0.9, "rotation": 1.0, "choppy": 1.0, "risk_off": 1.5},
    "cost_basis":  {"trend": 0.8, "rotation": 1.0, "choppy": 1.2, "risk_off": 1.1},
    "breakout":    {"trend": 1.0, "rotation": 0.9, "choppy": 0.6, "risk_off": 0.3},
    "mtf":         {"trend": 0.7, "rotation": 0.9, "choppy": 1.4, "risk_off": 1.2},
}
DEFAULT_WEIGHTS = {"rti": 0.22, "flow": 0.22, "smart_money": 0.18,
                   "cost_basis": 0.14, "breakout": 0.14, "mtf": 0.10}
ALL_MODULES = ["rti", "flow", "smart_money", "cost_basis", "breakout", "mtf"]


def detect_regime(pnl_records):
    """Auto-detect market regime from PnL patterns."""
    daily = pnl_records.get("daily", [])
    if not daily:
        return "rotation"

    pnls = [d.get("trade_pnl_bps", 0) for d in daily if d["trade_pnl_bps"] != 0]
    if not pnls:
        return "rotation"

    # Regime detection heuristics
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls)
    volatility = (sum((p - sum(pnls)/len(pnls))**2 for p in pnls) / len(pnls)) ** 0.5
    total_pnl = sum(pnls)

    if total_pnl > 100 and win_rate > 0.55 and volatility < 15:
        return "trend"
    elif volatility > 30:
        return "choppy"
    elif total_pnl < -50 and win_rate < 0.40:
        return "risk_off"
    return "rotation"


def train_weights_from_pnl(pnl_records, old_weights=None, config=None):
    """
    Learn new weights from real PnL performance data.

    Args:
        pnl_records: output of compute_real_pnl()
        old_weights: current weights to smooth from (optional)
        config: PHASE2_CONFIG override

    Returns:
        {regime, old_weights, learned_raw, learned_smoothed, new_weights,
         module_details, training_date}
    """
    if config is None:
        from .config import PHASE2_CONFIG as config

    lr = config.get("learning_rate", 0.08)
    min_w = config.get("min_weight", 0.03)
    smooth = config.get("smoothing_factor", 0.15)

    if old_weights is None:
        old_weights = dict(DEFAULT_WEIGHTS)

    regime = detect_regime(pnl_records)
    modules_raw = pnl_records.get("modules", {})
    summary = pnl_records.get("summary", {})

    # Compute raw learned weights
    learned_raw = {}
    total_eff = 0

    for mod in ALL_MODULES:
        if mod not in modules_raw:
            learned_raw[mod] = 0
            continue
        stats = modules_raw[mod]
        win_rate = stats.get("win_rate", 0)
        avg_pnl = stats.get("avg_pnl_bps", 0)

        # Effectiveness formula (consistent with weight_model.py)
        effectiveness = win_rate * max(avg_pnl * 50, 0.01)
        modifier = REGIME_MODIFIERS.get(mod, {}).get(regime, 1.0)
        learned_raw[mod] = max(0.001, effectiveness * modifier)
        total_eff += learned_raw[mod]

    # Normalize
    if total_eff > 0:
        learned_raw = {k: v / total_eff for k, v in learned_raw.items()}
    else:
        learned_raw = dict(DEFAULT_WEIGHTS)

    # Smooth update: new = old + LR * (learned - old)
    learned_smoothed = {}
    for mod in ALL_MODULES:
        old = old_weights.get(mod, DEFAULT_WEIGHTS.get(mod, 0.1))
        raw = learned_raw.get(mod, 0)
        smoothed = old + lr * (raw - old)
        learned_smoothed[mod] = max(min_w, smoothed)

    # Re-normalize
    total_sm = sum(learned_smoothed.values())
    new_weights = {k: round(v / total_sm, 4) for k, v in learned_smoothed.items()}

    # Build module details
    module_details = {}
    for mod in ALL_MODULES:
        stats = modules_raw.get(mod, {})
        module_details[mod] = {
            "old_weight": old_weights.get(mod, 0),
            "new_weight": new_weights[mod],
            "delta": round(new_weights[mod] - old_weights.get(mod, 0), 4),
            "win_rate": stats.get("win_rate", 0),
            "avg_pnl_bps": stats.get("avg_pnl_bps", 0),
            "total_pnl_bps": stats.get("total_pnl_bps", 0),
            "sharpe": stats.get("sharpe", 0),
            "days_traded": stats.get("days_traded", 0),
        }

    return {
        "regime": regime,
        "old_weights": old_weights,
        "learned_raw": {k: round(v, 4) for k, v in learned_raw.items()},
        "learned_smoothed": {k: round(v, 4) for k, v in learned_smoothed.items()},
        "new_weights": new_weights,
        "module_details": module_details,
        "summary": summary,
        "training_date": datetime.now(BJT).isoformat(),
    }


def save_trained_weights(result, store_dir="rotation/weight_learning/store"):
    """Save trained weights as versioned JSON + current."""
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    store = os.path.join(ROOT, store_dir)
    os.makedirs(store, exist_ok=True)

    weights = result["new_weights"]
    regime = result["regime"]
    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")

    # Versioned file
    ver_path = os.path.join(store, f"weights_{regime}_{ts}.json")
    meta = {
        "regime": regime,
        "trained_at": result["training_date"],
        "trained_days": result["summary"].get("traded_days", 0),
        "total_pnl_bps": result["summary"].get("total_pnl_bps", 0),
        "weights": weights,
        "module_details": result.get("module_details", {}),
    }
    with open(ver_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Current weights
    cur_path = os.path.join(store, "weights_current.json")
    with open(cur_path, "w") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)

    return {"versioned": ver_path, "current": cur_path}

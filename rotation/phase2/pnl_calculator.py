"""
PnL Calculator — Compute real PnL from archived Phase I data.

For each trading day in the archive:
1. Read signal snapshot → Meta decision (LONG/SHORT/HOLD)
2. Read raw snapshot → next-day index returns
3. Attribute PnL to each module using signal * weight * return
4. Output: per-day, per-module PnL records
"""
import json, os, glob
from datetime import datetime, timezone, timedelta
from collections import defaultdict


BJT = timezone(timedelta(hours=8))


def compute_real_pnl(archive_dir="rotation/archive", config=None):
    """
    Compute real PnL from archived signal snapshots.

    Returns: {
        "summary": {total_days, profitable_days, total_pnl_bps, sharpe, ...},
        "daily": [ {date, meta_decision, pnl_bps, module_pnl: {...}}, ... ],
        "modules": { rti: {total_pnl, win_rate, avg_pnl, sharpe}, ... },
        "errors": [...]
    }
    """
    if config is None:
        from .config import PHASE2_CONFIG as config

    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sig_dir = os.path.join(ROOT, archive_dir, "signal")
    raw_dir = os.path.join(ROOT, archive_dir, "raw")

    if not os.path.isdir(sig_dir):
        return {"error": f"Signal archive not found: {sig_dir}", "daily": [], "modules": {}}

    sig_files = sorted(glob.glob(os.path.join(sig_dir, "*.json")))
    if len(sig_files) < config.get("min_trading_days", 10):
        return {
            "error": f"Only {len(sig_files)} days archived. Need ≥{config['min_trading_days']}.",
            "available_days": len(sig_files),
            "daily": [],
            "modules": {},
        }

    tx_cost = config.get("transaction_cost_bps", 20) / 10000.0
    daily_records = []
    module_pnl = defaultdict(list)
    errors = []

    for sig_path in sig_files:
        date_str = os.path.basename(sig_path).replace(".json", "")
        raw_path = os.path.join(raw_dir, f"{date_str}.json")

        try:
            with open(sig_path, "r") as f:
                sig = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            errors.append(f"Failed to read signal: {date_str}")
            continue

        # Extract key signals
        meta = sig.get("meta", {})
        decision = meta.get("decision", "HOLD")
        meta_score = meta.get("score", 0)
        weights = sig.get("weights", {})
        signals_in = sig.get("signals", {})

        # Try to get full signal hub output if available
        raw_signals = signals_in  # fallback: archive format
        raw_meta = meta

        # Compute next-day return as PnL proxy
        next_day_return = _get_next_day_return(date_str, raw_dir, sig_files)
        if next_day_return is None:
            errors.append(f"No next-day data for: {date_str}")
            continue

        # Compute PnL
        if decision == "LONG":
            trade_pnl = next_day_return - tx_cost
        elif decision == "SHORT":
            trade_pnl = -next_day_return - tx_cost
        else:
            trade_pnl = 0  # HOLD → no PnL

        # Attribute PnL to modules (proportional to signal contribution)
        mpnl = {}
        if trade_pnl != 0 and weights:
            total_weighted = 0
            sig_values = {}
            for mod, w in weights.items():
                sv = _extract_signal_value(raw_signals, mod)
                sig_values[mod] = sv
                total_weighted += abs(sv) * w

            if total_weighted > 0:
                for mod in weights:
                    contribution = (abs(sig_values.get(mod, 0)) * weights.get(mod, 0)
                                    / total_weighted) * trade_pnl
                    mpnl[mod] = round(contribution * 10000, 2)  # convert to bps
                    module_pnl[mod].append(contribution * 10000)

        daily_records.append({
            "date": date_str,
            "meta_decision": decision,
            "meta_score": meta_score,
            "next_day_return_pct": round(next_day_return * 100, 2),
            "trade_pnl_bps": round(trade_pnl * 10000, 2),
            "module_pnl_bps": mpnl,
        })

    # Compute module-level stats
    module_stats = {}
    for mod, pnls in module_pnl.items():
        if not pnls:
            continue
        wins = sum(1 for p in pnls if p > 0)
        module_stats[mod] = {
            "total_pnl_bps": round(sum(pnls), 2),
            "win_rate": round(wins / len(pnls), 3) if pnls else 0,
            "avg_pnl_bps": round(sum(pnls) / len(pnls), 2),
            "days_traded": len(pnls),
            "sharpe": _sharpe(pnls),
        }

    # Summary
    all_pnls = [d["trade_pnl_bps"] for d in daily_records if d["trade_pnl_bps"] != 0]
    summary = {
        "total_days": len(sig_files),
        "traded_days": len(daily_records),
        "profitable_days": sum(1 for p in all_pnls if p > 0),
        "total_pnl_bps": round(sum(all_pnls), 2),
        "avg_pnl_bps": round(sum(all_pnls) / len(all_pnls), 2) if all_pnls else 0,
        "sharpe": _sharpe(all_pnls),
        "transaction_cost_bps": config.get("transaction_cost_bps", 20),
    }

    return {
        "summary": summary,
        "daily": daily_records,
        "modules": module_stats,
        "errors": errors,
    }


def _get_next_day_return(date_str, raw_dir, sig_files):
    """Find next trading day's index return from raw snapshots."""
    # find the next date in sig_files
    target = None
    found = False
    for f in sorted(sig_files):
        fdate = os.path.basename(f).replace(".json", "")
        if found:
            target = fdate
            break
        if fdate == date_str:
            found = True
    if not target:
        return None

    # read the raw snapshot for the target date and extract index change
    raw_path = os.path.join(raw_dir, f"{target}.json")
    if not os.path.exists(raw_path):
        return None

    try:
        with open(raw_path, "r") as f:
            raw = json.load(f)

        # Try portfolio stocks first for individual PnL
        # Fall back to market breadth
        market = raw.get("market", {})
        sectors = raw.get("sectors", [])

        # Use sector average change as proxy (weighted by sector count)
        if sectors:
            changes = [s.get("chg", 0) for s in sectors if s.get("chg") is not None]
            if changes:
                return sum(changes) / len(changes) / 100.0  # convert % to decimal

        # Fallback: use limit_up ratio as sentiment proxy
        total = market.get("total", 1)
        up = market.get("up", 0)
        if total > 0:
            return (up / total - 0.5) * 0.02  # rough daily return proxy

        return 0
    except Exception:
        return None


def _extract_signal_value(signals, module_name):
    """Extract normalized signal value for a module."""
    # Try direct key
    if module_name in signals:
        sv = signals[module_name]
        if isinstance(sv, (int, float)):
            return sv
        if isinstance(sv, dict):
            return sv.get("score", sv.get("signal", 0))

    # Try nested paths
    for key in signals:
        val = signals[key]
        if isinstance(val, dict):
            if module_name in val:
                return val[module_name]
            for sub in val.values():
                if isinstance(sub, dict) and module_name in sub:
                    return sub[module_name]

    return 0


def _sharpe(values, rf=0.02):
    """Annualized Sharpe ratio from daily bps values."""
    if not values or len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = var ** 0.5
    if std == 0:
        return 0
    # Daily Sharpe → Annualized (×√250)
    daily_rf = rf / 250 * 10000  # RF in bps
    return round((mean - daily_rf) / std * (250 ** 0.5), 2)

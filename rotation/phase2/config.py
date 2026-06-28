"""
Phase II Configuration — thresholds and constants for auto-training + pruning.

All values are tunable. These defaults are conservative — they prefer
keeping modules over aggressive pruning.
"""

PHASE2_CONFIG = {
    # ── Data Requirements ──
    "min_trading_days": 20,       # Minimum archive days before running
    "target_trading_days": 30,    # Ideal: full month
    "archive_dir": "rotation/archive",

    # ── PnL Calculation ──
    "transaction_cost_bps": 20,   # 0.2% round-trip cost
    "pnl_lookahead_days": 1,      # Use next-day return as PnL proxy
    "min_stocks_for_signal": 3,   # Signal must fire on ≥3 stocks

    # ── Weight Training ──
    "learning_rate": 0.08,        # Higher than daily LR (更多数据→更激进)
    "min_weight": 0.03,           # Floor weight per module (pruning除外)
    "smoothing_factor": 0.15,     # EMA smoothing for noisy PnL series

    # ── Module Pruning ──
    "prune_threshold_bps": -5.0,   # Marginal contribution < -5bps → flag
    "prune_consistency_days": 15,   # Must underperform for ≥15 of 30 days
    "prune_win_rate_min": 0.30,     # Win rate below 30% → flag regardless
    "max_prune_count": 2,           # Never prune more than 2 modules at once
    "protected_modules": [],        # Never prune these (empty = all eligible)

    # ── Reporting ──
    "output_html": "docs/phase2_report.html",
    "output_json": "docs/phase2_data.json",
    "output_weights": "rotation/weight_learning/store/weights_current.json",
}

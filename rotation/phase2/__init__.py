"""
Phase II — 30-Day Auto Trainer + Module Pruner
================================================
After 30 trading days of Phase I data collection:

1. Compute real PnL from archived signal/trade snapshots
2. Auto-train weights using real performance data
3. Run ablation on real PnL (not proxy metrics)
4. Prune underperforming modules
5. Generate training + pruning report
6. Update production config

Entry: run_phase2_pipeline()
Output: docs/phase2_report.html, updated weights
"""

from .runner import run_phase2_pipeline
from .pnl_calculator import compute_real_pnl
from .auto_trainer import train_weights_from_pnl
from .module_pruner import prune_modules
from .config import PHASE2_CONFIG

__all__ = [
    "run_phase2_pipeline",
    "compute_real_pnl",
    "train_weights_from_pnl",
    "prune_modules",
    "PHASE2_CONFIG",
]

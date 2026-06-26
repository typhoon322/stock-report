"""
rotation/shadow — Phase I Shadow Mode 基础设施

三类每日产出:
  - Signal Snapshot  (snapshots/signal_YYYYMMDD.json)
  - Shadow Trade Log (trades/shadow_trades_YYYYMMDD.json)
  - System Health    (logs/system_health_YYYYMMDD.json)

时区: 统一 UTC+8 (北京时间)
"""
from .signal_snapshot import save_signal_snapshot
from .shadow_trade import save_shadow_trades
from .health_collector import save_health_log
from .runner import run_shadow_mode

__all__ = [
    "save_signal_snapshot",
    "save_shadow_trades",
    "save_health_log",
    "run_shadow_mode",
]

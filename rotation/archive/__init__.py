"""
rotation/archive — Phase I 数据存储系统

三层结构:
  raw/   — 原始市场快照（回测核心源）
  signal/ — 策略输出快照（weight learning 核心源）
  trade/  — 影子交易日志（PnL 验证核心源）

五条强制规则:
  1. 所有决策必须可回放（replayable）
  2. 不允许只存HTML
  3. 不允许丢失signal snapshot
  4. 不允许修改历史数据
  5. 不允许使用未结构化日志作为训练数据

时区: UTC+8
"""
from .raw_snapshot import save_raw_snapshot
from .signal_snapshot import save_signal_snapshot
from .trade_log import save_trade_log
from .runner import run_daily_archive

__all__ = [
    "save_raw_snapshot",
    "save_signal_snapshot",
    "save_trade_log",
    "run_daily_archive",
]

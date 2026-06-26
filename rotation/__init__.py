"""
rotation/ — 量化轮动策略引擎
"""
from .models import Stock, Sector, MarketSentiment, RotationSignal, DailyReport
from .rti import compute_rti, rank_rotation_signals, detect_news_drivers
from .bsi import compute_bsi, classify_bsi, rank_sectors
from .ls import compute_leader_score, classify_leader, find_leaders, find_sector_leader
from .phase import detect_phase, get_position_advice, compute_risk_level

__all__ = [
    "Stock", "Sector", "MarketSentiment", "RotationSignal", "DailyReport",
    "compute_rti", "rank_rotation_signals", "detect_news_drivers",
    "compute_bsi", "classify_bsi", "rank_sectors",
    "compute_leader_score", "classify_leader", "find_leaders", "find_sector_leader",
    "detect_phase", "get_position_advice", "compute_risk_level",
]

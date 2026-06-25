"""
rotation/models.py — 核心数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Stock:
    code: str
    name: str
    change_pct: float = 0.0
    volume_ratio: float = 1.0
    is_limit_up: bool = False
    is_breakout: bool = False
    industry: str = ""
    money_flow: float = 0.0
    is_early_starter: bool = False
    leader_score: int = 0

@dataclass
class Sector:
    name: str
    change_1d: float = 0.0
    change_3d: float = 0.0
    change_5d: float = 0.0
    volume_change: float = 1.0
    num_stocks_up: int = 0
    num_limit_up: int = 0
    net_money_flow: float = 0.0
    leader_stock: str = ""
    stocks: List[Stock] = field(default_factory=list)
    is_low_position: bool = False
    has_news_driver: bool = False
    rti_score: int = 0
    bsi_score: int = 0

@dataclass
class MarketSentiment:
    limit_up_count: int = 0
    fall_limit_count: int = 0
    market_breadth: float = 0.0
    up_down_ratio: float = 0.0
    consecutive_board: int = 0
    index_trend: str = "未知"
    risk_level: str = "medium"
    phase: str = "未知"

@dataclass
class RotationSignal:
    sector: Sector
    rti_score: int
    status: str  # "潜在新主线" | "轮动试探" | "无轮动"
    reason: str
    leader: Optional[Stock] = None

@dataclass
class DailyReport:
    date: str
    sentiment: MarketSentiment
    rotation_signals: List[RotationSignal]  # RTI ≥ 3
    strong_sectors: List[Sector]            # BSI > 30
    leaders: List[Stock]                    # LS ≥ 5
    phase: str
    risk_alerts: List[str]
    strategy: dict

"""
rotation/mtf/timeframe_builder.py — 多周期时间框架构建 (零新API)

Short: 1-5日 | Mid: 5-20日 | Long: 20-60日
全部来自 history_cache 已有数据, 纯计算不拉API
"""
import json, os
from typing import Dict, List, Optional
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(ROOT, "history_cache")


def load_prices_from_cache() -> List[float]:
    """从缓存加载价格序列 (取上证指数近似)"""
    prices = []
    
    # 从 sector 缓存中取某个代表性板块的价格变化累积
    files = sorted([f for f in os.listdir(CACHE_DIR) if f.startswith("sector_") and f.endswith(".json")])
    if not files:
        return _fallback_prices()
    
    base = 100.0
    for f in files[-60:]:  # 最多60天
        try:
            with open(os.path.join(CACHE_DIR, f)) as fh:
                sectors = json.load(fh)
            # 所有板块平均涨跌作为市场代理
            if sectors:
                avg_chg = sum(s.get("change_pct", 0) or 0 for s in sectors) / max(len(sectors), 1)
                base *= (1 + avg_chg / 100)
                prices.append(round(base, 2))
        except:
            pass
    
    return prices if len(prices) >= 5 else _fallback_prices()


def _fallback_prices() -> List[float]:
    """无缓存时的兜底数据"""
    return [100.0] * 60


def build_timeframes(prices: List[float] = None) -> Dict:
    """
    构建三层时间框架
    
    Returns:
        {"short": {"prices": [...], ...}, "mid": {...}, "long": {...}}
    """
    if prices is None:
        prices = load_prices_from_cache()
    
    n = len(prices)
    
    return {
        "short": {
            "prices": prices[-5:] if n >= 5 else prices,
            "days": min(5, n),
            "label": "短期 (1-5日)",
        },
        "mid": {
            "prices": prices[-20:] if n >= 20 else prices,
            "days": min(20, n),
            "label": "中期 (5-20日)",
        },
        "long": {
            "prices": prices[-60:] if n >= 60 else prices,
            "days": min(60, n),
            "label": "长期 (20-60日)",
        },
    }

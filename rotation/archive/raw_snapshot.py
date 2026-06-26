"""
Raw Market Snapshot — 每日原始市场数据快照

产出: rotation/archive/raw/YYYY-MM-DD.json
这是回测和训练的核心数据源，包含当日全部可观测变量。
"""
import json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tz_now():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")


def save_raw_snapshot(
    market_breadth: dict = None,
    sectors: list = None,
    futures: dict = None,
    flows: dict = None,
    portfolio_stocks: dict = None,
) -> str:
    """保存原始市场快照
    
    所有数据来自实时API，不做二次加工。用于 Phase II 回放验证。
    """
    snapshot = {
        "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "timestamp": _tz_now(),
        "version": "v2.19",
        "market": market_breadth or {},
        "sectors": sectors or [],
        "futures": futures or {},
        "flows": flows or {},
        "portfolio": portfolio_stocks or {},
    }
    
    os.makedirs(os.path.join(ROOT, "rotation", "archive", "raw"), exist_ok=True)
    path = os.path.join(ROOT, "rotation", "archive", "raw", f"{_today()}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    
    size = os.path.getsize(path)
    print(f"  📦 raw snapshot: {os.path.basename(path)} ({size:,} bytes)")
    return path

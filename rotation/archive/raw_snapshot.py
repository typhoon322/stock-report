"""
Raw Market Snapshot — 每日原始市场数据快照

产出: rotation/archive/raw/YYYY-MM-DD.json
这是回测和训练的核心数据源，包含当日全部可观测变量。

支持历史回填: 传入 as_of_date (YYYYMMDD) 可写入指定日期的快照,
并标记 backfilled=True 表示数据来自历史重建(非实时)。
"""
import json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tz_now():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _date_parts(as_of_date=None):
    """返回 (YYYYMMDD, YYYY-MM-DD)，as_of_date 缺省为当前(UTC+8)"""
    if as_of_date:
        s = str(as_of_date).replace("-", "")
        return s, f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    now = datetime.now(timezone(timedelta(hours=8)))
    return now.strftime("%Y%m%d"), now.strftime("%Y-%m-%d")


def save_raw_snapshot(
    market_breadth: dict = None,
    sectors: list = None,
    futures: dict = None,
    flows: dict = None,
    portfolio_stocks: dict = None,
    as_of_date: str = None,
    indices: dict = None,
    backfilled: bool = False,
    note: str = None,
) -> str:
    """保存原始市场快照

    所有数据来自 API，不做二次加工。用于 Phase II 回放验证。
    当 backfilled=True 时，数据来自历史重建(见 backfill.py)，部分字段可能为 null。
    """
    ymd, iso = _date_parts(as_of_date)
    snapshot = {
        "date": iso,
        "timestamp": _tz_now(),
        "version": "v2.19",
        "backfilled": backfilled,
        "note": note,
        "market": market_breadth or {},
        "sectors": sectors or [],
        "futures": futures or {},
        "flows": flows or {},
        "indices": indices or {},
        "portfolio": portfolio_stocks or {},
    }

    os.makedirs(os.path.join(ROOT, "rotation", "archive", "raw"), exist_ok=True)
    path = os.path.join(ROOT, "rotation", "archive", "raw", f"{ymd}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)

    size = os.path.getsize(path)
    print(f"  📦 raw snapshot: {os.path.basename(path)} ({size:,} bytes)"
          f"{' [回填]' if backfilled else ''}")
    return path

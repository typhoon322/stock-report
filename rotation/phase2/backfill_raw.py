"""
backfill_raw.py — 用 history_cache 中的历史数据批量生成 archive/raw/*.json

数据来源:
  history_cache/sector_history.json — 61天行业涨跌+资金流
  history_cache/index_history.json  — 60天四大指数日线

输出:
  rotation/archive/raw/YYYY-MM-DD.json — 每个交易日一份快照

运行: python -m rotation.phase2.backfill_raw
"""
import json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def backfill():
    cache = os.path.join(ROOT, "history_cache")
    archive = os.path.join(ROOT, "rotation", "archive", "raw")

    # ── Load historical data ──
    sector_path = os.path.join(cache, "sector_history.json")
    index_path = os.path.join(cache, "index_history.json")

    if not os.path.exists(sector_path):
        print("❌ sector_history.json not found. Run collect_history.py first.")
        return

    with open(sector_path) as f:
        sectors_all = json.load(f)

    with open(index_path) as f:
        indices_all = json.load(f) if os.path.exists(index_path) else []

    # ── Group by date ──
    sector_by_date = defaultdict(list)
    for r in sectors_all:
        sector_by_date[r["date"]].append(r)

    index_by_date = defaultdict(list)
    for r in indices_all:
        index_by_date[r["date"]].append(r)

    # Load portfolio
    pf_path = os.path.join(ROOT, "portfolio.json")
    portfolio = []
    if os.path.exists(pf_path):
        try:
            with open(pf_path) as f:
                pf_data = json.load(f)
            if isinstance(pf_data, list):
                portfolio = pf_data
            elif isinstance(pf_data, dict):
                portfolio = [
                    {"code": k, "name": v if isinstance(v, str) else v.get("name", ""),
                     "focus": v.get("focus", False) if isinstance(v, dict) else False,
                     "cost": v.get("cost") if isinstance(v, dict) else None,
                     "note": v.get("note", "") if isinstance(v, dict) else ""}
                    for k, v in pf_data.items()
                ]
        except Exception:
            portfolio = [
                {"code": "600487", "name": "亨通光电", "focus": True, "cost": 78, "note": "光纤龙头"},
                {"code": "600522", "name": "中天科技", "focus": True, "cost": 44, "note": "光纤通信"},
                {"code": "002745", "name": "木林森", "focus": False, "cost": 12.5, "note": "LED"},
                {"code": "600733", "name": "北汽蓝谷", "focus": True, "cost": 16.5, "note": "新能源车"},
                {"code": "513060", "name": "恒生医疗ETF", "focus": False, "cost": 1.14, "note": "港股医疗"},
                {"code": "512170", "name": "医疗ETF", "focus": False, "cost": 0.58, "note": "境内医疗"},
                {"code": "515790", "name": "光伏ETF", "focus": False, "cost": 1.0, "note": "光伏"},
            ]

    # ── Generate snapshots ──
    all_dates = sorted(set(
        list(sector_by_date.keys()) + list(index_by_date.keys())
    ))
    # Filter: keep dates that have BOTH sector and index data
    valid_dates = [d for d in all_dates if d in sector_by_date and d in index_by_date]

    os.makedirs(archive, exist_ok=True)
    created = 0
    skipped = 0

    for date_str in valid_dates:
        out_path = os.path.join(archive, f"{date_str}.json")
        if os.path.exists(out_path):
            skipped += 1
            continue

        sectors = sector_by_date[date_str]
        indices = index_by_date[date_str]

        # Sort sectors by change_pct descending
        sectors_sorted = sorted(sectors, key=lambda s: s.get("change_pct", 0) or 0, reverse=True)

        # Build sector list (keep top + bottom for completeness)
        sector_list = []
        for s in sectors_sorted[:10]:  # top 10
            sector_list.append({
                "name": s["sector"],
                "bsi": 0,  # backfill: no BSI available
                "chg": round(s.get("change_pct", 0) or 0, 2),
                "flow": round(s.get("net_flow", 0) or 0, 2),
            })

        # Estimate market breadth from sector data
        # (rough approximation: % of sectors with positive change)
        up_sectors = sum(1 for s in sectors if (s.get("change_pct") or 0) > 0)
        dn_sectors = sum(1 for s in sectors if (s.get("change_pct") or 0) < 0)
        total_sectors = len(sectors)
        breadth = up_sectors / total_sectors if total_sectors > 0 else 0.5

        # Build index summary
        index_close = {}
        for idx in indices:
            name = idx.get("index", "")
            if name:
                index_close[name] = idx.get("close")

        snapshot = {
            "date": date_str,
            "timestamp": f"{date_str} 00:00:00",
            "version": "v2.22-backfill",
            "source": "backfill",
            "market": {
                "total_stocks": 5527,  # approx, stable across recent months
                "up": round(breadth * 5527),
                "down": round((1 - breadth) * 5527),
                "limit_up": 0,   # no historical limit-up data
                "fall_limit": 0,
                "breadth": round(breadth, 4),
                "note": "backfill: breadth estimated from sector change ratio",
            },
            "sectors": sector_list,
            "futures": {},  # backfill: no historical futures
            "flows": {},
            "index_close": index_close,
            "portfolio": {"stocks": portfolio},
        }

        with open(out_path, "w") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        created += 1

    print(f"✅ Backfill complete: {created} created, {skipped} skipped (already exist)")
    print(f"   Dates: {valid_dates[0]} ~ {valid_dates[-1]}" if valid_dates else "   No valid dates")
    print(f"   Output: {archive}/")


if __name__ == "__main__":
    backfill()

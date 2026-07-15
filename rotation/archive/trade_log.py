"""
Shadow Trade Log — 影子交易记录

产出: rotation/archive/trade/YYYY-MM-DD.json
模拟从信号→仓位→执行的完整链路，Phase II 用于验证策略收益。

支持历史回填: as_of_date + backfilled 标记。
"""
import json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tz_now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _date_parts(as_of_date=None):
    if as_of_date:
        s = str(as_of_date).replace("-", "")
        return s, f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    now = datetime.now(timezone(timedelta(hours=8)))
    return now.strftime("%Y%m%d"), now.strftime("%Y-%m-%d")


def save_trade_log(
    meta_result: dict = None,
    position_result: dict = None,
    execution_result: dict = None,
    portfolio: dict = None,
    as_of_date: str = None,
    backfilled: bool = False,
    note: str = None,
) -> str:
    """保存影子交易日志"""
    ymd, iso = _date_parts(as_of_date)
    doc = {
        "date": iso,
        "timestamp": _tz_now(),
        "backfilled": backfilled,
        "note": note,
        "status": "shadow",
        "pipeline": {
            "meta": {
                "decision": (meta_result or {}).get("decision", "HOLD"),
                "score": (meta_result or {}).get("score", 0),
                "confidence": (meta_result or {}).get("confidence", 0),
            },
            "position": {
                "direction": (position_result or {}).get("direction"),
                "size": (position_result or {}).get("position_size"),
                "level": (position_result or {}).get("position_level"),
            },
            "execution": {
                "slippage_pct": (execution_result or {}).get("slippage", {}).get("estimated_slippage_pct"),
                "realized_position": (execution_result or {}).get("realized_position"),
            },
        },
        "portfolio": {},
        "simulated_pnl": {"entry_price": None, "exit_price": None, "pnl_pct": None,
                          "note": "Phase I shadow — Phase II backfill with real prices"},
    }

    if portfolio and isinstance(portfolio, dict):
        doc["portfolio"] = {
            k: {"name": v.get("name", "") if isinstance(v, dict) else v,
                "focus": v.get("focus", False) if isinstance(v, dict) else False}
            for k, v in list(portfolio.items())[:10]
        }

    os.makedirs(os.path.join(ROOT, "rotation", "archive", "trade"), exist_ok=True)
    path = os.path.join(ROOT, "rotation", "archive", "trade", f"{ymd}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, default=str)

    print(f"  📋 trade log: {os.path.basename(path)}"
          f"{' [回填]' if backfilled else ''}")
    return path

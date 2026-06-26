"""
Signal Snapshot — 每日策略输出快照

产出: rotation/archive/signal/YYYY-MM-DD.json
包含所有子系统信号、Meta Score、权重版本。是 weight learning 的核心输入。
"""
import json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tz_now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")


def save_signal_snapshot(
    signals: dict = None,
    meta: dict = None,
    position: dict = None,
    weights: dict = None,
    regime: str = "",
) -> str:
    """保存每日信号快照"""
    doc = {
        "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "timestamp": _tz_now(),
        "version": "v2.19",
        "signals": signals or {},
        "meta": {
            "score": meta.get("score", 0) if meta else 0,
            "decision": meta.get("decision", "HOLD") if meta else "HOLD",
            "confidence": meta.get("confidence", 0) if meta else 0,
        },
        "position": position or {},
        "weights": weights or {},
        "regime": regime,
    }
    
    os.makedirs(os.path.join(ROOT, "rotation", "archive", "signal"), exist_ok=True)
    path = os.path.join(ROOT, "rotation", "archive", "signal", f"{_today()}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"  📡 signal snapshot: {os.path.basename(path)}")
    return path

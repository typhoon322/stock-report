"""
rotation/weight_learning/signal_tracker.py — 信号→收益记录

每一笔交易记录: 当时各模块信号 + Meta Score + 最终PnL
"""
import json, os
from datetime import datetime
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(ROOT, "rotation", "weight_learning", "trade_records.json")


def record_trade(signals: Dict[str, float], meta_score: float, pnl: float) -> Dict:
    """记录一笔交易"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "signals": {k: round(v, 4) for k, v in signals.items()},
        "meta_score": round(meta_score, 4),
        "pnl": round(pnl, 4),
    }
    
    records = load_records()
    records.append(record)
    
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'w') as f:
        json.dump(records, f, indent=2, default=str)
    
    return record


def load_records() -> List[Dict]:
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            return json.load(f)
    return []


def get_recent_records(n: int = 20) -> List[Dict]:
    records = load_records()
    return records[-n:]


def get_signal_performance() -> Dict[str, Dict]:
    """计算每个信号的历史表现"""
    records = load_records()
    if not records:
        return {}
    
    performance = {}
    for module in records[0]["signals"]:
        wins = sum(1 for r in records if r["signals"][module] > 0.3 and r["pnl"] > 0)
        total = sum(1 for r in records if r["signals"][module] > 0.3)
        avg_pnl = sum(r["pnl"] for r in records if r["signals"][module] > 0.3) / max(total, 1)
        
        performance[module] = {
            "signal_count": total,
            "win_rate": round(wins / max(total, 1), 3),
            "avg_pnl": round(avg_pnl, 4),
        }
    
    return performance

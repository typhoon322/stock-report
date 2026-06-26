"""
Signal Snapshot — 每日将全部子系统信号写入快照文件
"""
import json, os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _now_str() -> str:
    """返回北京时间字符串"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y%m%d")


def save_signal_snapshot(signals: dict, meta: dict = None, weights: dict = None) -> str:
    """保存每日信号快照
    
    Args:
        signals: {模块名: {信号值, 来源状态}}
        meta: Meta Score 结果
        weights: 当期权重
    Returns:
        文件路径
    """
    snapshot = {
        "timestamp": _now_str(),
        "version": "v2.19",
        "signals": signals,
        "meta": meta or {},
        "weights": weights or {},
    }
    
    path = os.path.join(ROOT, "rotation", "shadow", "snapshots", f"signal_{_today_str()}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    
    return path

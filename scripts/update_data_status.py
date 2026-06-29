#!/usr/bin/env python3
"""
update_data_status.py — 统计归档数据并写入 docs/data_status.json

每次成功生成报告后调用，更新首页显示的数据收集天数。
"""
import json, os, glob
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def update():
    archive = os.path.join(ROOT, "rotation", "archive")

    # Count signal snapshots (each represents a complete daily pipeline run)
    sig_dir = os.path.join(archive, "signal")
    sig_files = sorted(glob.glob(os.path.join(sig_dir, "*.json")))
    signal_days = len(sig_files)

    # Count raw snapshots
    raw_dir = os.path.join(archive, "raw")
    raw_files = glob.glob(os.path.join(raw_dir, "*.json"))
    raw_days = len(raw_files)

    # Count trade logs
    trade_dir = os.path.join(archive, "trade")
    trade_files = glob.glob(os.path.join(trade_dir, "*.json"))
    trade_days = len(trade_files)

    # Find date range
    dates = sorted([os.path.basename(f).replace(".json", "") for f in sig_files])
    start_date = dates[0] if dates else datetime.now(BJT).strftime("%Y-%m-%d")
    last_date = dates[-1] if dates else start_date

    # Target: 30 trading days for Phase II trigger
    target = 30
    progress_pct = min(100, round(signal_days / target * 100))

    status = {
        "signal_days": signal_days,          # 完整策略运行天数
        "raw_days": raw_days,                # 市场快照天数
        "trade_days": trade_days,            # 交易日志天数
        "start_date": start_date,
        "last_date": last_date,
        "target_days": target,
        "progress_pct": progress_pct,
        "phase": "Phase I" if signal_days < target else "Phase II",
        "updated_at": datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
    }

    out_path = os.path.join(ROOT, "docs", "data_status.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"📊 数据状态: {signal_days}/{target} 天 ({progress_pct}%) → {out_path}")
    return status


if __name__ == "__main__":
    update()

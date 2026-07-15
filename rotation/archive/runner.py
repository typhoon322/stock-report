"""
Daily Archive Runner — 自动化每日入口

执行:
  1. 归档"今日"快照 (Robust Daily Archive)
     —— 以主要指数历史(index_zh_a_hist)为可靠主干, 板块/实时广度尽力而为,
        即便网络抖动也能保证当天有一份有效快照。
  2. 自检缺口, 自动回填缺失交易日 (Gap Auto-Backfill)
     —— 复用同一套指数主干重建缺失日, 保证"每天都能同步到数据"。

历史回填基于 akshare 历史接口重建, 所有回填条目标记 backfilled=True。
"""
import glob
import json
import os
import traceback
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _today8():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")


def _load_portfolio():
    try:
        with open(os.path.join(ROOT, "portfolio.json"), 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _archived_signal_dates():
    sig_dir = os.path.join(ROOT, "rotation", "archive", "signal")
    return sorted(os.path.basename(f).replace(".json", "")
                  for f in glob.glob(os.path.join(sig_dir, "*.json")))


def run_daily_archive():
    """主入口(今日): 以指数主干稳健归档当日 raw/signal/trade 快照"""
    print(f"📦 Daily Archive (今日稳健归档) — {_now()}")
    results = {"status": "ok", "files": [], "errors": [], "timestamp": _now()}
    try:
        from rotation.archive import backfill

        today = _today8()
        portfolio = _load_portfolio()
        archived = _archived_signal_dates()
        window_start = min(archived) if archived else today

        # 主干: 指数历史 (覆盖今日 + 缺口窗口, 一次拉取)
        index_data = backfill.fetch_major_indices(window_start, today)
        # 尽力: 板块历史 + 实时广度
        board_data = backfill.fetch_board_window_best_effort(window_start, today)
        live_breadth = backfill.try_live_breadth()

        if not index_data:
            results["errors"].append("index_backbone: 全部指数历史拉取失败")

        fs = backfill.archive_day(
            today, board_data, index_data, portfolio,
            backfilled=False, live_breadth=live_breadth)
        results["files"].extend(fs)
    except Exception as e:
        results["errors"].append(f"daily_archive: {e}")
        traceback.print_exc()

    err_count = len(results["errors"])
    status = "✅" if err_count == 0 else "⚠️"
    print(f"\n{status} 今日归档: {len(results['files'])} files, {err_count} errors")
    for e in results["errors"]:
        print(f"   {e}")
    return results


def run():
    """完整入口: 今日稳健归档 + 缺口自动回填"""
    print(f"📦 Daily Archive (含缺口回填) — {_now()} (UTC+8)")
    results = {"status": "ok", "files": [], "errors": [], "timestamp": _now(), "backfilled": []}

    # 0. 预备: 拉取主干(今日与缺口共用)
    try:
        from rotation.archive import backfill
        today = _today8()
        portfolio = _load_portfolio()
        archived = _archived_signal_dates()
        window_start = min(archived) if archived else today
        index_data = backfill.fetch_major_indices(window_start, today)
        board_data = backfill.fetch_board_window_best_effort(window_start, today)
    except Exception as e:
        results["errors"].append(f"prepare_backbone: {e}")
        traceback.print_exc()
        index_data, board_data = {}, {}

    # 1. 今日稳健归档
    try:
        from rotation.archive import backfill
        live_breadth = backfill.try_live_breadth()
        today = _today8()
        portfolio = _load_portfolio()
        fs = backfill.archive_day(
            today, board_data, index_data, portfolio,
            backfilled=False, live_breadth=live_breadth)
        results["files"].extend(fs)
    except Exception as e:
        results["errors"].append(f"today: {e}")
        traceback.print_exc()

    # 2. 缺口回填 (复用已拉取的主干, 不重复请求)
    try:
        from rotation.archive import backfill
        archived = _archived_signal_dates()
        portfolio = _load_portfolio()
        today = _today8()
        bf = backfill.backfill_gap(archived, today, portfolio,
                                   board_data=board_data, index_data=index_data)
        results["backfilled"] = bf
        results["files"].extend(bf)
    except Exception as e:
        results["errors"].append(f"backfill: {e}")
        traceback.print_exc()

    err_count = len(results["errors"])
    status = "✅" if err_count == 0 else "⚠️"
    n_bf = len(results.get("backfilled", []))
    print(f"\n{status} 归档完成: {len(results['files'])} files "
          f"({n_bf} 来自回填), {err_count} errors")
    for e in results["errors"]:
        print(f"   {e}")
    return results


if __name__ == "__main__":
    run()

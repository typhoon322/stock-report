"""
backfill.py — 缺口自动回填 + 稳健每日归档 (Gap Auto-Backfill & Robust Daily Archive)

问题背景:
  原 daily runner 只抓取"当日"实时快照, 且依赖大量实时接口
  (stock_zh_a_spot / fetch_industry_sectors / run_mtf_check),
  一旦某交易日因网络抖动 / 调度失败而漏采, 该日数据永久缺失, 且没有任何补回机制。

设计原则 (稳健优先, 每天必同步):
  1. 主骨架 = 主要指数历史 (index_zh_a_hist): 仅 5 次接口调用, 覆盖任意历史日期,
     是整个流水线的"可靠主干"。即使板块/实时接口全挂, 相位(phase)与多周期(mtf)
     仍能从指数历史推导, 保证每一天都有一份有效快照。
  2. 板块 = 尽力而为 (best-effort): 行业板块列表 + 每板块历史K线, 失败则留空, 不阻塞。
  3. 实时广度 (涨跌家数) = 尽力而为: 仅在今日实时归档时尝试, 失败则回退到指数推导广度。
  4. 全部回填条目统一标记 backfilled=True, 下游(Phase II)可据此区分实时与重建数据。

这样即便某天漏采, 下一次成功运行会自动补齐缺口, 真正做到"每天都能同步到数据"。
"""
import os
import time
import traceback
from datetime import datetime, timezone, timedelta

import akshare as ak
import pandas as pd

from rotation.bsi import compute_bsi
from rotation.phase import detect_phase, get_position_advice
from rotation.models import Sector, MarketSentiment
from rotation.archive.raw_snapshot import save_raw_snapshot
from rotation.archive.signal_snapshot import save_signal_snapshot
from rotation.archive.trade_log import save_trade_log

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 主要指数: 名称 -> (Sina 代码, Eastmoney 代码)
# Sina 接口 (stock_zh_index_daily) 在网络抖动/东财被限流时通常仍可用, 作为主干首选。
MAJOR_INDICES = {
    "上证指数": ("sh000001", "000001"),
    "深证成指": ("sz399001", "399001"),
    "创业板指": ("sz399006", "399006"),
    "沪深300": ("sh000300", "000300"),
    "中证500": ("sh000905", "000905"),
}


def _norm_em(df):
    return df[['日期', '收盘', '涨跌幅']].copy()


def _norm_sina(df):
    df = df.copy()
    df['日期'] = df['date'].astype(str)
    df['收盘'] = df['close']
    df = df.sort_values('日期')
    df['涨跌幅'] = df['收盘'].pct_change() * 100
    df['涨跌幅'] = df['涨跌幅'].fillna(0)
    return df[['日期', '收盘', '涨跌幅']]


# ── 网络重试 (应对 akshare 间歇性 ConnectionError) ──
def ak_retry(fn, *a, tries=4, base=2, **k):
    last = None
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(base + i * 2)
    raise last


def iso(d8: str) -> str:
    s = str(d8).replace("-", "")
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def trade_dates_between(start8: str, end8: str):
    """返回 [start8, end8] 内的交易日列表(YYYYMMDD)"""
    cal = ak_retry(ak.tool_trade_date_hist_sina)
    ds = set(cal['trade_date'].astype(str).tolist())
    out = []
    d = datetime.strptime(start8, "%Y%m%d").date()
    e = datetime.strptime(end8, "%Y%m%d").date()
    while d <= e:
        if d.strftime("%Y-%m-%d") in ds:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


# ── 指数主干 (mandatory, 可靠) ──
def fetch_major_indices(start8: str, end8: str) -> dict:
    """一次拉取窗口内全部主要指数日K, 返回 {指数名: 标准化DataFrame[日期,收盘,涨跌幅]}

    数据源策略: 先 Sina (stock_zh_index_daily), 失败再回退 Eastmoney (index_zh_a_hist)。
    两者任一可用即可重建相位/MTF, 保证每天都有有效快照。
    """
    res = {}
    for name, (sina_sym, em_sym) in MAJOR_INDICES.items():
        df = None
        # 1) Sina 主干
        try:
            d = ak_retry(ak.stock_zh_index_daily, symbol=sina_sym)
            if d is not None and len(d):
                df = _norm_sina(d)
        except Exception:
            df = None
        # 2) Eastmoney 回退
        if df is None:
            try:
                d = ak_retry(ak.index_zh_a_hist, symbol=em_sym, period="daily",
                             start_date=start8, end_date=end8)
                if d is not None and len(d):
                    df = _norm_em(d)
            except Exception:
                df = None
        if df is not None:
            df = df[df['日期'] >= iso(start8)]
            if len(df):
                res[name] = df
    return res


# ── 板块 (best-effort) ──
_board_map = None


def _industry_boards_best_effort():
    global _board_map
    if _board_map is not None:
        return _board_map
    df = None
    for src in (ak.stock_board_industry_name_em, ak.stock_board_industry_name_ths):
        try:
            df = ak_retry(src, tries=3)
            if df is not None and len(df):
                break
        except Exception:
            df = None
    if df is None or len(df) == 0:
        _board_map = {}
        return _board_map
    code_col = '板块代码' if '板块代码' in df.columns else df.columns[1]
    name_col = '板块名称' if '板块名称' in df.columns else df.columns[0]
    _board_map = {str(r[name_col]): str(r[code_col]).strip() for _, r in df.iterrows()}
    return _board_map


def fetch_board_window_best_effort(start8: str, end8: str, max_boards: int = 40) -> dict:
    """尽力抓取行业板块历史K线; 单个板块失败不影响整体。"""
    codes = _industry_boards_best_effort()
    res = {}
    for name, code in list(codes.items())[:max_boards]:
        try:
            df = ak_retry(ak.stock_board_industry_hist_em, symbol=code, period="日k",
                          start_date=start8, end_date=end8, adjust="", tries=2)
            if df is not None and len(df):
                res[name] = df
        except Exception:
            pass
    return res


# ── 实时广度 (best-effort, 仅今日) ──
def try_live_breadth():
    """尝试用实时全市场行情计算涨跌广度; 失败返回 None。"""
    try:
        df = ak_retry(ak.stock_zh_a_spot, tries=3)
        if df is None or len(df) == 0:
            return None
        total = len(df)
        up = len(df[df['涨跌幅'] > 0])
        limit_up = len(df[df['涨跌幅'] >= 9.5])
        fall_limit = len(df[df['涨跌幅'] <= -9.5])
        return {"total_stocks": total, "up": up, "down": total - up,
                "limit_up": limit_up, "fall_limit": fall_limit,
                "breadth": round(up / total, 4) if total > 0 else 0.5,
                "source": "live_spot"}
    except Exception:
        return None


def _change_n(df, d8, n):
    """截至 d8 的最近 n 个交易日累计涨跌幅(近似 n 日收益率)"""
    if df is None or len(df) == 0:
        return 0.0
    sub = df[df['日期'] <= iso(d8)].sort_values('日期')
    if len(sub) == 0:
        return 0.0
    tail = sub.tail(n)
    col = '涨跌幅' if '涨跌幅' in tail.columns else None
    if col is None:
        return 0.0
    return float(pd.to_numeric(tail[col], errors='coerce').fillna(0).sum())


def _idx_changes_on(d8, index_data):
    out = {}
    closes = {}
    for nm, df in index_data.items():
        row = df[df['日期'] == iso(d8)]
        if len(row):
            r = row.iloc[0]
            out[nm] = float(pd.to_numeric(r.get('涨跌幅', 0), errors='coerce') or 0)
            closes[nm] = float(pd.to_numeric(r.get('收盘', 0), errors='coerce') or 0)
    return out, closes


def _approx_mtf(d8, index_data):
    """从主要指数的 1d/3d/5d 涨跌对齐近似 MTF 分数 (范围 -3 .. +3)。"""
    scores = []
    for name, df in index_data.items():
        c1 = _change_n(df, d8, 1)
        c3 = _change_n(df, d8, 3)
        c5 = _change_n(df, d8, 5)
        sc = (1 if c1 > 0 else -1) + (1 if c3 > 0 else -1) + (1 if c5 > 0 else -1)
        scores.append(sc)
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def reconstruct(d8, board_data, index_data):
    """返回 (sectors, top, phase, advice, idx_chg, breadth, mtf)"""
    # 板块 (best-effort)
    sectors = []
    for name, df in board_data.items():
        row = df[df['日期'] == iso(d8)]
        if len(row) == 0:
            continue
        chg = float(pd.to_numeric(row.iloc[0].get('涨跌幅', 0), errors='coerce') or 0)
        c3 = _change_n(df, d8, 3)
        c5 = _change_n(df, d8, 5)
        sectors.append(Sector(name=name, change_1d=chg, change_3d=c3, change_5d=c5,
                              volume_change=1.0, num_limit_up=0, net_money_flow=0.0))
    for s in sectors:
        s.bsi_score = compute_bsi(s, sectors)
    top = sorted(sectors, key=lambda s: s.bsi_score, reverse=True)[:5]

    # 指数主干 → 相位/MTF (可靠)
    idx_chg, idx_close = _idx_changes_on(d8, index_data)
    if idx_chg:
        up = sum(1 for c in idx_chg.values() if c > 0)
        breadth = up / len(idx_chg)
        sent = MarketSentiment(market_breadth=breadth, limit_up_count=0,
                               fall_limit_count=0, consecutive_board=0)
        phase = detect_phase(sent)
        mtf = _approx_mtf(d8, index_data)
        idx = {nm: {"change": c, "close": idx_close.get(nm)} for nm, c in idx_chg.items()}
    else:
        # 网络全挂的兜底: 仍写一份可用快照, 缺口不会"消失"
        breadth = 0.5
        phase = "🔄 轮动期"
        mtf = 0.0
        idx = {}
    advice = get_position_advice(phase)
    return sectors, top, phase, advice, idx, breadth, mtf


def archive_day(d8, board_data, index_data, portfolio, backfilled=False,
                live_breadth=None, note=None):
    """归档单日 raw/signal/trade 三件套。today 与回填日共用本函数。"""
    sectors, top, phase, advice, idx, breadth, mtf = reconstruct(d8, board_data, index_data)

    sectors_list = [{"name": s.name, "bsi": s.bsi_score,
                     "chg": round(float(s.change_1d), 3), "flow": None}
                    for s in sectors[:10]]

    if live_breadth and not backfilled:
        mb = live_breadth
    else:
        mb = {"backfilled": backfilled,
              "note": "全市场涨跌家数无法从历史接口重建" if backfilled else "指数推导广度",
              "breadth": round(breadth, 4)}

    raw_path = save_raw_snapshot(
        market_breadth=mb, sectors=sectors_list, futures={}, flows={},
        portfolio_stocks=portfolio, as_of_date=d8, indices=idx,
        backfilled=backfilled,
        note=note or ("从历史指数/板块K线重建 (index_zh_a_hist / stock_board_industry_hist_em)"
                      if backfilled else "主要指数历史 + 实时广度(尽力)"))

    signals = {
        "bsi": {"top": len(top), "names": [s.name for s in top], "backfilled": backfilled},
        "phase": {"phase": phase, "advice": advice, "backfilled": backfilled},
        "mtf": {"score": mtf, "backfilled": backfilled},
    }
    sig_path = save_signal_snapshot(
        signals=signals, regime=phase, as_of_date=d8, backfilled=backfilled,
        note=note or ("信号由指数历史推导的相位(BSI/phase)与多周期(MTF)重建"
                      if backfilled else "信号由主要指数历史推导 (phase/mtf)"))
    trade_path = save_trade_log(
        portfolio=portfolio, as_of_date=d8, backfilled=backfilled,
        note="影子交易日志(每日, 无实时执行)" if not backfilled
        else "影子交易日志(历史日级, 无实时执行)")
    return [raw_path, sig_path, trade_path]


def backfill_gap(archived_dates, today8, portfolio,
                 board_data=None, index_data=None):
    """检测 archived_dates 与 today8 之间缺失的交易日并回填。返回生成的文件路径列表。"""
    if not archived_dates:
        start8 = today8
    else:
        start8 = min(archived_dates)
    present = set(archived_dates)
    missing = [d for d in trade_dates_between(start8, today8)
               if d not in present and d <= today8]

    if not missing:
        print("✅ 无缺失交易日, 无需回填")
        return []

    print(f"🔧 检测到 {len(missing)} 个缺失交易日: {missing}")
    window_start = min(missing)
    if index_data is None:
        index_data = fetch_major_indices(window_start, today8)
    if board_data is None:
        board_data = fetch_board_window_best_effort(window_start, today8)
    print(f"   指数主干覆盖: {list(index_data.keys())} | 板块覆盖: {len(board_data)} 个")

    if not index_data:
        print("⚠ 指数历史拉取全部失败, 无法重建相位/MTF, 保留缺口待下次重试")
        return []

    files = []
    for d in missing:
        try:
            fs = archive_day(d, board_data, index_data, portfolio, backfilled=True)
            files.extend(fs)
            print(f"   ✅ 回填 {d}")
        except Exception as e:
            print(f"   ⚠ 回填 {d} 失败: {e}")
            traceback.print_exc()
    return files

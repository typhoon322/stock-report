#!/usr/bin/env python3
"""数据采集脚本 — 逐段执行，每段保存"""
import akshare as ak
import pandas as pd
import numpy as np
import json, time, sys, warnings
from datetime import datetime

warnings.filterwarnings('ignore')
def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

TODAY = datetime.now().strftime("%Y%m%d")
TODAY_FMT = datetime.now().strftime("%Y-%m-%d")
PORTFOLIO = [
    {"code": "600487", "name": "亨通光电", "cost": 78, "market": "sh"},
    {"code": "600522", "name": "中天科技", "cost": 44, "market": "sh"},
    {"code": "002745", "name": "木林森",     "cost": 12.5, "market": "sz"},
    {"code": "600733", "name": "北汽蓝谷",   "cost": 16.5, "market": "sh"},
    {"code": "513060", "name": "恒生医疗ETF", "cost": 1.14, "is_etf": True},
    {"code": "512170", "name": "医疗ETF",    "cost": 0.58, "is_etf": True},
    {"code": "515790", "name": "光伏ETF",    "cost": 0.99, "is_etf": True},
]

all_data = {'date': TODAY_FMT, 'timestamp': datetime.now().isoformat(), 'results': {}, 'errors': {}}

def save():
    with open('docs/limit_up_analysis_data.json', 'w') as f:
        json.dump(all_data, f, ensure_ascii=False, default=str)

def try_call(fn, name, **kw):
    try:
        r = fn(**kw)
        if r is not None and isinstance(r, pd.DataFrame) and len(r) > 0:
            log(f"  [OK] {name}: {len(r)} rows")
            return r
        log(f"  [EMPTY] {name}")
        return None
    except Exception as e:
        log(f"  [FAIL] {name}: {e}")
        return None

# ===== STEP 1: ZT Pool =====
log(">>> STEP 1: ZT Pool")
zt = try_call(ak.stock_zt_pool_em, "ZT Pool", date=TODAY)
if zt is not None:
    all_data['results']['zt_pool'] = zt.to_dict(orient='records')
save()

# ===== STEP 2: Fund Flows =====
log(">>> STEP 2: Fund Flows")
ffc = try_call(ak.stock_fund_flow_concept, "Concept Flow", symbol='即时')
if ffc is not None:
    all_data['results']['fund_flow_concept'] = ffc.to_dict(orient='records')
ffi = try_call(ak.stock_fund_flow_industry, "Industry Flow", symbol='即时')
if ffi is not None:
    all_data['results']['fund_flow_industry'] = ffi.to_dict(orient='records')
save()

# ===== STEP 3: Spot Data (Stocks) =====
log(">>> STEP 3: Stock Spot")
try:
    spot = ak.stock_zh_a_spot_em()
    all_data['results']['spot_name_map'] = dict(zip(spot['代码'], spot['名称']))
    holding_codes = ['600487', '600522', '002745', '600733']
    sh = spot[spot['代码'].isin(holding_codes)]
    all_data['results']['spot_holdings'] = sh.to_dict(orient='records')
    log(f"  [OK] Spot: {len(spot)} stocks, {len(sh)} holdings")
except Exception as e:
    log(f"  [FAIL] Spot: {e}")
save()

# ===== STEP 4: ETF Spot =====
log(">>> STEP 4: ETF Spot")
es = try_call(ak.fund_etf_spot_em, "ETF Spot")
if es is not None:
    ec = ['513060', '512170', '515790']
    eh = es[es['代码'].isin(ec)]
    all_data['results']['etf_spot'] = eh.to_dict(orient='records')
save()

# ===== STEP 5: Holdings History =====
log(">>> STEP 5: Holdings History")
holdings = {}
for pos in PORTFOLIO:
    c = pos['code']
    log(f"  {c} {pos['name']}")
    hd = {'code': c, 'name': pos['name'], 'cost': pos['cost']}

    # History
    if pos.get('is_etf'):
        hist = try_call(ak.fund_etf_hist_em, f"{c} history", symbol=c, period='daily',
                        start_date='20260101', end_date=TODAY_FMT, adjust='qfq')
    else:
        hist = try_call(ak.stock_zh_a_hist, f"{c} history", symbol=c, period='daily',
                        start_date='20260101', end_date=TODAY_FMT, adjust='qfq')
    if hist is not None:
        hd['history'] = hist.tail(120).to_dict(orient='records')

    # Fund flow (stocks only)
    if not pos.get('is_etf'):
        flow = try_call(ak.stock_individual_fund_flow, f"{c} flow", stock=c, market=pos['market'])
        if flow is not None:
            hd['fund_flow'] = flow.head(5).to_dict(orient='records')

    # Financial (stocks only)
    if not pos.get('is_etf'):
        fin = try_call(ak.stock_financial_abstract_ths, f"{c} financial", symbol=c, indicator='按报告期')
        if fin is not None:
            hd['financial'] = fin.head(6).to_dict(orient='records')

    # Northbound (stocks only)
    if not pos.get('is_etf'):
        nb = try_call(ak.stock_hsgt_individual_em, f"{c} northbound", stock=c)
        if nb is not None:
            hd['northbound'] = nb.head(10).to_dict(orient='records')

    # Valuation (stocks only)
    if not pos.get('is_etf'):
        prefix = "SH" if pos['market'] == 'sh' else "SZ"
        val = try_call(ak.stock_zh_valuation_comparison_em, f"{c} valuation", symbol=f"{prefix}{c}")
        if val is not None:
            hd['valuation_comp'] = val.head(10).to_dict(orient='records')

    # Growth (stocks only)
    if not pos.get('is_etf'):
        growth = try_call(ak.stock_zh_growth_comparison_em, f"{c} growth", symbol=f"{prefix}{c}")
        if growth is not None:
            hd['growth_comp'] = growth.head(10).to_dict(orient='records')

    # News
    if not pos.get('is_etf'):
        news = try_call(ak.stock_news_em, f"{c} news", symbol=c)
        if news is not None:
            hd['news'] = news.head(5).to_dict(orient='records')

    holdings[c] = hd

all_data['results']['holdings'] = holdings
save()
log(">>> Complete!")

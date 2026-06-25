#!/usr/bin/env python3
"""
cloud_weekly.py — 周五周报数据采集
采集本周5个交易日完整数据，供 LLM 深度分析使用
"""
import akshare as ak
import pandas as pd
import requests
import json, os, sys, time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TO = datetime.now()
DAYS = [(TO - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 0, -1)]
DAYS = [d for d in DAYS if d <= TO.strftime("%Y-%m-%d")][-5:]  # 最近5个交易日

def to_f(v): 
    try: return float(v)
    except: return None

def try_fetch(func, name):
    try:
        s = time.time(); r = func()
        print(f"  ✅ [{name}] {len(r) if hasattr(r,'__len__') else 'N/A'}行 ({time.time()-s:.1f}s)")
        return r
    except Exception as e:
        print(f"  ⚠ [{name}] {str(e)[:80]}")
        return None

data = {
    "title": f"A股周报 — 截至{TO.strftime('%Y-%m-%d')}",
    "period": f"{DAYS[0]} 至 {DAYS[-1]}",
    "generated_at": TO.isoformat(),
    "daily_indices": {},
    "sector_flows_weekly": {},
    "portfolio_weekly": {},
    "futures_weekly": {},
    "fx_weekly": {},
    "news_digest": [],
}

print(f"📊 周报数据采集 — {data['period']}")
print(f"   交易日: {len(DAYS)}天")

# ── 1. 美股三大指数本周趋势 ──
print("\n[1] 美股本周...")
for name, sym in [("标普500",".INX"),("道琼斯",".DJI"),("纳斯达克",".IXIC")]:
    try:
        df = ak.index_us_stock_sina(symbol=sym)
        week_data = []
        for d in DAYS:
            row = df[df['date'].astype(str) == d]
            if len(row) > 0:
                r = row.iloc[0]
                week_data.append({"date":d,"open":to_f(r['open']),"close":to_f(r['close']),
                                   "high":to_f(r['high']),"low":to_f(r['low']),"vol":int(to_f(r['volume'],0))})
        if week_data:
            w0, w1 = week_data[0], week_data[-1]
            wchg = round((w1['close']-w0['close'])/w0['close']*100,2) if w0['close'] else None
            data["daily_indices"][name] = {"weekly_chg":wchg, "daily":week_data}
            print(f"   {name}: {w1['close']:,.0f} 周涨跌{wchg:+.2f}%")
    except: pass

# ── 2. A股指数本周 ──
print("\n[2] A股本周...")
try:
    for idx_name in ["上证指数","深证成指","创业板指","科创50"]:
        try:
            df = ak.index_zh_a_hist(symbol=idx_name, period="daily",
                                     start_date=DAYS[0].replace("-",""),
                                     end_date=DAYS[-1].replace("-",""))
            if len(df) >= 2:
                daily = []
                for _,r in df.iterrows():
                    daily.append({"date":str(r['日期']),"open":to_f(r['开盘']),
                                  "close":to_f(r['收盘']),"high":to_f(r['最高']),
                                  "low":to_f(r['最低']),"chg":to_f(r['涨跌幅']),
                                  "vol":to_f(r.get('成交量',0))})
                wchg = round((daily[-1]['close']-daily[0]['open'])/daily[0]['open']*100,2) if daily else None
                data["daily_indices"][f"A股-{idx_name}"] = {"weekly_chg":wchg, "daily":daily}
                print(f"   {idx_name}: {daily[-1]['close']:,.0f} 周涨跌{wchg:+.2f}%")
        except: pass
except: pass

# ── 3. 行业资金流向汇总 ──
print("\n[3] 行业资金本周...")
try:
    df_ind = try_fetch(lambda: ak.stock_fund_flow_industry(symbol='即时'), "行业板块")
    if df_ind is not None:
        top5 = df_ind.nlargest(5,'净额')
        bot5 = df_ind.nsmallest(5,'净额')
        data["sector_flows_weekly"] = {
            "top_inflow": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in top5.iterrows()],
            "top_outflow": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in bot5.iterrows()],
        }
except: pass

# ── 4. 概念资金本周 ──
print("\n[4] 概念资金...")
try:
    df_c = try_fetch(lambda: ak.stock_fund_flow_concept(symbol='即时'), "概念资金")
    if df_c is not None:
        top5c = df_c.nlargest(5,'净额')
        data["concept_flows_weekly"] = {
            "top": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in top5c.iterrows()],
        }
except: pass

# ── 5. 商品期货本周 ──
print("\n[5] 期货本周...")
try:
    df_f = ak.futures_global_spot_em()
    for pre, label in [(["GC"],"黄金"),(["CL"],"原油"),(["HG"],"铜"),(["SI"],"白银"),(["CN00Y","CN26N"],"A50")]:
        m = pd.Series(False,index=df_f.index)
        for p in pre: m |= df_f['代码'].str.startswith(p,na=False)
        c = df_f[m & df_f['最新价'].notna()]
        if len(c)>0:
            r = c.iloc[0]
            data["futures_weekly"][label] = {"price":to_f(r['最新价']),"chg":to_f(r['涨跌幅'])}
            print(f"   {label}: {r['最新价']} ({r['涨跌幅']}%)")
except: pass

# ── 6. 外汇 ──
print("\n[6] 外汇...")
try:
    df_fx = ak.currency_boc_sina()
    data["fx_weekly"]["USD_CNY"] = to_f(df_fx.iloc[-1]['央行中间价'])
except: pass

# ── 7. 本周重大新闻摘要 ──
print("\n[7] 本周新闻...")
news_all = []
for attempt in range(2):
    try:
        df_n = ak.stock_info_global_sina()
        news_all = [str(r.get('内容',''))[:200] for _,r in df_n.head(30).iterrows()]
        break
    except: pass
data["news_digest"] = news_all

# ── 8. 读取持仓配置 ──
print("\n[8] 持仓...")
try:
    with open(os.path.join(ROOT, "portfolio.json")) as f:
        pf = json.load(f)
        data["portfolio_config"] = pf["stocks"]
        print(f"   {len(pf['stocks'])}只")
except: pass

# ── 保存 ──
path = os.path.join(ROOT, "docs", "weekly_data.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, default=str)

print(f"\n✅ 周报数据保存: docs/weekly_data.json ({len(json.dumps(data))}字符)")
print(f"   覆盖: 美股{len(data.get('daily_indices',{}))}项, A股, 行业, 概念, 期货, 外汇, 新闻{len(news_all)}条")

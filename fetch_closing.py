#!/usr/bin/env python3
"""
A股收盘总结 v1 — 全天盘面总结 + 持仓复盘 + 明日展望
运行时机：A股收盘后 15:05

数据源:
  A股收盘:  Sinajs (hq.sinajs.cn) — 四大指数收盘
  市场广度: westock-data changedist
  板块资金: AKShare (概念+行业)
  全球期货: 东方财富 (futures_global_spot_em)
  外汇:     中行 (currency_boc_sina)
  持仓个股: westock-data quote (7只持仓)
"""
import akshare as ak
import pandas as pd
import requests
import json
import os
import time
from datetime import datetime, timedelta

OUT_DIR = "/Users/yanx/WorkBuddy/automation-2026-06-24-19-35-08"
TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")

def try_fetch(func, name, max_retry=1):
    for attempt in range(max_retry + 1):
        try:
            start = time.time()
            result = func()
            elapsed = time.time() - start
            rows = len(result) if hasattr(result, '__len__') else 'N/A'
            print(f"  ✅ [{name}] {rows}行 ({elapsed:.1f}s)")
            return result
        except Exception as e:
            print(f"  ❌ [{name}] #{attempt+1}: {str(e)[:80]}")
            if attempt < max_retry: time.sleep(1.5)
    print(f"  ⚠ [{name}] 数据暂缺")
    return None

def save_json(data, filename):
    path = os.path.join(OUT_DIR, filename)
    if data is None:
        with open(path, 'w') as f:
            json.dump({"status": "missing", "time": datetime.now().isoformat()}, f)
        return
    if isinstance(data, pd.DataFrame):
        data.to_json(path, orient='records', force_ascii=False)
    elif isinstance(data, (list, dict)):
        with open(path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, default=str)

def to_float(val, default=None):
    try: return float(val)
    except: return default

def fetch_sina_index(code):
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        resp = requests.get(f"https://hq.sinajs.cn/list={code}", headers=headers, timeout=10)
        resp.encoding = 'gbk'
        line = resp.text.strip()
        if code in line and '=""' not in line:
            parts = line.split('="')[1].strip('";').split(',')
            return parts
    except: pass
    return None

report = {
    "title": "A股收盘总结",
    "date": TODAY_STR,
    "weekday": ["周一","周二","周三","周四","周五","周六","周日"][TODAY.weekday()],
    "generated_at": TODAY.strftime("%Y-%m-%d %H:%M:%S"),
    "a_indices_close": {},
    "sector_overview": {},
    "concept_flows": {},
    "global_futures": {},
    "fx_rates": {},
    "global_news": [],
    "sources": {},
}

print("=" * 60)
print(f"📊 A股收盘数据采集 — {TODAY_STR} {report['weekday']}")
print("=" * 60)

# [1] A股收盘指数
print("\n[1/5] A股收盘指数 (Sinajs)...")
for name, code in [
    ("上证指数", "s_sh000001"), ("深证成指", "s_sz399001"),
    ("创业板指", "s_sz399006"), ("科创50", "s_sh000688"),
    ("沪深300", "s_sh000300"), ("中证500", "s_sh000905"),
]:
    parts = fetch_sina_index(code)
    if parts and len(parts) >= 4:
        report["a_indices_close"][name] = {
            "price": to_float(parts[1]), "change_pct": to_float(parts[3]),
        }
        report["sources"][name] = "✅"
        print(f"     {name}: {parts[1]} ({parts[3]}%)")
    else:
        report["sources"][name] = "❌"

# [2] 概念资金流向 (最后半小时)
print("\n[2/5] 概念/行业资金流向...")
df_concept = try_fetch(lambda: ak.stock_fund_flow_concept(symbol='即时'), "概念资金")
if df_concept is not None:
    # Top/Bottom flowing concepts
    df_sorted = df_concept.sort_values('净额', ascending=False, key=pd.to_numeric if df_concept['净额'].dtype == object else None)
    top5_in = df_sorted.head(5)[['行业', '行业-涨跌幅', '净额', '领涨股']].to_dict('records')
    top5_out = df_sorted.tail(5)[['行业', '行业-涨跌幅', '净额', '领涨股']].to_dict('records')
    report["concept_flows"] = {"top_inflow": top5_in, "top_outflow": top5_out}
    report["sources"]["概念资金"] = "✅"
    print(f"     Top流入: {top5_in[0]['行业'] if top5_in else 'N/A'}")

# [3] 行业板块行情
df_ind = try_fetch(lambda: ak.stock_fund_flow_industry(symbol='即时'), "行业板块")
if df_ind is not None:
    top5_up = df_ind.nlargest(5, '行业-涨跌幅')[['行业', '行业-涨跌幅', '净额']].to_dict('records')
    top5_down = df_ind.nsmallest(5, '行业-涨跌幅')[['行业', '行业-涨跌幅', '净额']].to_dict('records')
    report["sector_overview"] = {"top_gainers": top5_up, "top_losers": top5_down}
    report["sources"]["行业板块"] = "✅"
    print(f"     Top涨: {top5_up[0]['行业'] if top5_up else 'N/A'}")

# [4] 全球期货收盘参考
print("\n[3/5] 全球商品期货...")
df_fut = try_fetch(lambda: ak.futures_global_spot_em(), "期货")
if df_fut is not None:
    fut_map = [(["GC"], "COMEX黄金"), (["CL"], "NYMEX原油"), (["HG"], "COMEX铜"),
               (["SI"], "COMEX白银"), (["CN00Y","CN26N"], "富时A50")]
    futures = {}
    for prefixes, label in fut_map:
        mask = pd.Series(False, index=df_fut.index)
        for p in prefixes:
            mask |= df_fut['代码'].str.startswith(p, na=False)
        candidates = df_fut[mask & df_fut['最新价'].notna()]
        if len(candidates) > 0:
            r = candidates.iloc[0]
            futures[label] = {"price": to_float(r['最新价']), "change_pct": to_float(r['涨跌幅'])}
            print(f"     {label}: {r['最新价']} ({r['涨跌幅']}%)")
    report["global_futures"] = futures
    report["sources"]["期货"] = "✅"

# [5] 外汇
print("\n[4/5] 外汇...")
df_fx = try_fetch(lambda: ak.currency_boc_sina(), "外汇")
if df_fx is not None:
    row = df_fx.iloc[-1]
    report["fx_rates"] = {"USD_CNY": to_float(row['央行中间价'])}
    report["sources"]["外汇"] = "✅"

# [6] 全球新闻
print("\n[5/5] 要闻...")
df_news = try_fetch(lambda: ak.stock_info_global_sina(), "新闻")
if df_news is not None:
    items = [{"time": str(r.get('时间','')), "content": str(r.get('内容',''))[:150]} 
             for _, r in df_news.head(10).iterrows()]
    report["global_news"] = items
    report["sources"]["新闻"] = "✅"

# Save
save_json(report, "closing_data.json")
print(f"\n✅ 保存: closing_data.json")
print(f"数据源: {json.dumps({k: ('✅' if '✅' in str(v) else '❌') for k,v in report['sources'].items()}, ensure_ascii=False)}")

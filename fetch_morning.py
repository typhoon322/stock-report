#!/usr/bin/env python3
"""
A股早盘报告 v3 — 美股收盘 + 亚太开盘 + 商品外汇 + 重大新闻
运行时机：A股开盘前 8:00-8:45 AM

数据源：
  美股三大指数:  Sina (index_us_stock_sina)
  A股/港股指数:   Sina 实时 (hq.sinajs.cn)
  日经225:       Sina 实时 (int_nikkei)
  KOSPI:         yfinance 备选
  全球商品期货:  东方财富 (futures_global_spot_em) — 代码修正版
  外汇牌价:      中行 (currency_boc_sina)
  全球要闻:      新浪 (stock_info_global_sina)

修复记录:
  v3: 期货代码GC/CL/CN+非NaN过滤, 日经使用int_nikkei, A股使用Sinajs
  v2: 多源架构, yfinance备选
  v1: 初始版本
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

# ============================================================
# Utils
# ============================================================
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
            short = str(e)[:80]
            print(f"  ❌ [{name}] #{attempt+1}: {short}")
            if attempt < max_retry:
                time.sleep(1.5)
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
    """从 Sina hq.sinajs.cn 获取单只指数实时行情"""
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        resp = requests.get(f"https://hq.sinajs.cn/list={code}", headers=headers, timeout=10)
        resp.encoding = 'gbk'
        line = resp.text.strip()
        if code in line and '=""' not in line:
            parts = line.split('="')[1].strip('";').split(',')
            return parts
    except:
        pass
    return None

def pick_best_future(df, code_prefixes, name_keywords):
    """从期货列表中选最佳活跃合约: 按代码前缀匹配 + 非NaN + 选最新价的"""
    mask = pd.Series(False, index=df.index)
    for prefix in code_prefixes:
        mask |= df['代码'].str.startswith(prefix, na=False)
    candidates = df[mask & df['最新价'].notna()]
    if len(candidates) == 0:
        # fallback to name matching
        for kw in name_keywords:
            mask2 = df['名称'].str.contains(kw, case=False, na=False)
            candidates = df[mask2 & df['最新价'].notna()]
            if len(candidates) > 0:
                break
    if len(candidates) > 0:
        # Prefer candidates with non-NaN change%
        with_chg = candidates[candidates['涨跌幅'].notna()]
        if len(with_chg) > 0:
            return with_chg.iloc[0]
        return candidates.iloc[0]
    return None

# ============================================================
# Build Report
# ============================================================
report = {
    "title": "A股早盘报告",
    "date": TODAY_STR,
    "weekday": ["周一","周二","周三","周四","周五","周六","周日"][TODAY.weekday()],
    "generated_at": TODAY.strftime("%Y-%m-%d %H:%M:%S"),
    "us_market": {},
    "asia_market": {},
    "a_indices": {},
    "global_futures": {},
    "fx_rates": {},
    "global_news": [],
    "sources": {},
}

print("=" * 60)
print(f"📊 A股早盘数据采集 v3 — {TODAY_STR} {report['weekday']}")
print("=" * 60)

# ============================================================
# [1] 美股三大指数收盘
# ============================================================
print("\n[1/7] 美股三大指数收盘...")
US_INDICES = {"标普500": ".INX", "道琼斯": ".DJI", "纳斯达克": ".IXIC"}
for name, sym in US_INDICES.items():
    df = try_fetch(lambda s=sym: ak.index_us_stock_sina(symbol=s), f"美股-{name}")
    if df is not None and len(df) >= 2:
        last, prev = df.iloc[-1], df.iloc[-2]
        close = to_float(last['close'])
        prev_c = to_float(prev['close'])
        chg = round((close - prev_c) / prev_c * 100, 2) if prev_c else None
        chg5 = None
        if len(df) >= 5:
            f5 = to_float(df.iloc[-5]['close'])
            if f5: chg5 = round((close - f5) / f5 * 100, 2)
        report["us_market"][name] = {
            "close": close, "change_pct": chg,
            "high": to_float(last['high']), "low": to_float(last['low']),
            "volume": int(to_float(last.get('volume', 0), 0)),
            "date": str(last['date']), "chg_5d": chg5,
        }
        report["sources"][f"美股-{name}"] = "✅"
        print(f"     {name}: {close:,.0f} ({chg:+.2f}%) | 5日{chg5:+.2f}%")
    else:
        report["sources"][f"美股-{name}"] = "❌"

# ============================================================
# [2] A股前日收盘 (Sinajs — 稳定)
# ============================================================
print("\n[2/7] A股前日收盘 (Sinajs)...")
a_idx_codes = {
    "上证指数": "s_sh000001",
    "深证成指": "s_sz399001",
    "创业板指": "s_sz399006",
    "科创50": "s_sh000688",
}
a_indices = {}
for name, code in a_idx_codes.items():
    parts = fetch_sina_index(code)
    if parts and len(parts) >= 4:
        price = to_float(parts[1])
        chg_pct = to_float(parts[3])
        a_indices[name] = {"price": price, "change_pct": chg_pct}
        report["sources"][f"A股-{name}"] = "✅"
        print(f"     {name}: {price:,.0f} ({chg_pct:+.2f}%)")
    else:
        report["sources"][f"A股-{name}"] = "❌"
report["a_indices"] = a_indices

# ============================================================
# [3] 亚太市场 (恒生 + 日经 via Sinajs, KOSPI via yfinance)
# ============================================================
print("\n[3/7] 亚太市场...")
asia_data = {}

# 恒生指数
parts = fetch_sina_index("int_hangseng")
if parts and len(parts) >= 4:
    asia_data["恒生指数"] = {
        "price": to_float(parts[1]),
        "change_pct": to_float(parts[3]),
        "change_val": to_float(parts[2]),
    }
    report["sources"]["恒生指数"] = "✅ Sina实时"
    print(f"     恒生指数: {parts[1]} ({parts[3]}%)")

# 日经225 — 用 int_nikkei（不是 int_nikkei225!）
parts = fetch_sina_index("int_nikkei")
if parts and len(parts) >= 4:
    asia_data["日经225"] = {
        "price": to_float(parts[1]),
        "change_pct": to_float(parts[3]),
        "change_val": to_float(parts[2]),
    }
    report["sources"]["日经225"] = "✅ Sina实时"
    print(f"     日经225: {parts[1]} ({parts[3]}%)")
else:
    report["sources"]["日经225"] = "❌"

# KOSPI — yfinance备选
try:
    import yfinance as yf
    ticker = yf.Ticker("^KS11")
    hist = ticker.history(period="3d")
    if len(hist) >= 2:
        last = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = to_float(last['Close'])
        chg = round((close - to_float(prev['Close'])) / to_float(prev['Close']) * 100, 2) if prev is not None else None
        asia_data["韩国KOSPI"] = {"price": close, "change_pct": chg}
        report["sources"]["韩国KOSPI"] = "✅ yfinance"
        print(f"     韩国KOSPI: {close:,.0f} ({chg:+.2f}%)")
except Exception as e:
    report["sources"]["韩国KOSPI"] = f"⚠ ({str(e)[:30]})"

report["asia_market"] = asia_data

# ============================================================
# [4] 全球商品期货 (代码修正版)
# ============================================================
print("\n[4/7] 全球商品期货...")
df_fut = try_fetch(lambda: ak.futures_global_spot_em(), "全球期货")
futures_data = {}

if df_fut is not None:
    # 修正后的代码映射: (代码前缀列表, 名称关键词列表, 品种标签)
    FUTURE_MAP = [
        (["GC"],      ["COMEX黄金", "黄金"],     "COMEX黄金"),
        (["CL"],      ["NYMEX原油", "WTI原油"],   "NYMEX原油"),
        (["B"],       ["布伦特原油"],              "布伦特原油"),
        (["HG"],      ["COMEX铜"],                "COMEX铜"),
        (["SI"],      ["COMEX白银"],              "COMEX白银"),
        (["NG"],      ["天然气"],                  "天然气"),
        (["CN00Y","CN26N","CN26M"], ["A50当月连续","A50"], "富时A50期货"),
    ]
    
    for prefixes, name_kws, label in FUTURE_MAP:
        row = pick_best_future(df_fut, prefixes, name_kws)
        if row is not None:
            p = to_float(row['最新价'])
            c = to_float(row['涨跌幅'])
            futures_data[label] = {
                "price": p, "change_pct": c,
                "code": str(row['代码']), "name": str(row['名称']),
            }
            print(f"     {label} ({row['代码']} {row['名称']}): {p} ({c:+.2f}%)" if c else f"     {label} ({row['代码']} {row['名称']}): {p}")
        else:
            print(f"     {label}: 未找到活跃合约")
    
    report["global_futures"] = futures_data
    report["sources"]["全球期货"] = "✅"
else:
    report["sources"]["全球期货"] = "❌"

# ============================================================
# [5] 外汇牌价
# ============================================================
print("\n[5/7] 外汇牌价...")
df_fx = try_fetch(lambda: ak.currency_boc_sina(), "外汇")
if df_fx is not None:
    fx_data = {}
    latest_date = df_fx['日期'].max()
    usd = df_fx[df_fx['日期'] == latest_date]
    if len(usd) > 0:
        row = usd.iloc[0]
        fx_data["USD_CNY"] = {
            "date": str(latest_date),
            "central_parity": to_float(row['央行中间价']),
            "buy": to_float(row['中行汇买价']),
            "sell": to_float(row['中行钞卖价/汇卖价']),
        }
        print(f"     USD/CNY 中间价: {fx_data['USD_CNY']['central_parity']}")
    report["fx_rates"] = fx_data
    report["sources"]["外汇"] = "✅"
else:
    report["sources"]["外汇"] = "❌"

# ============================================================
# [6] 全球重要新闻
# ============================================================
print("\n[6/7] 全球要闻...")
df_news = try_fetch(lambda: ak.stock_info_global_sina(), "全球新闻")
if df_news is not None:
    important_kw = [
        "美联储", "加息", "降息", "CPI", "GDP", "非农", "PMI",
        "关税", "制裁", "芯片", "半导体", "AI", "人工智能",
        "央行", "LPR", "降准", "汇率", "地缘", "冲突",
        "美股", "A股", "港股", "日经", "韩国",
        "原油", "黄金", "铜", "稀土",
        "华为", "苹果", "特斯拉", "英伟达", "台积电",
        "政策", "监管", "改革", "突破", "禁令",
        "大涨", "暴跌", "创", "新高", "新低",
        "OPEC", "欧元", "美元", "人民币",
    ]
    news_items = []
    for _, row in df_news.iterrows():
        content = str(row.get('内容', ''))[:200]
        ts = str(row.get('时间', ''))
        score = sum(1 for kw in important_kw if kw in content)
        news_items.append({
            "time": ts, "content": content,
            "importance": "🔴" if score >= 2 else ("🟡" if score >= 1 else ""),
            "score": score,
        })
    news_items.sort(key=lambda x: x['score'], reverse=True)
    report["global_news"] = news_items[:15]
    high = sum(1 for n in news_items[:15] if n['score'] >= 1)
    print(f"     共{len(df_news)}条 → 高相关{high}条/总计15条")
    report["sources"]["全球新闻"] = "✅"
else:
    report["sources"]["全球新闻"] = "❌"

# ============================================================
# [7] 数据源汇总
# ============================================================
print(f"\n{'='*60}")
print("数据源汇总:")
all_ok = True
for k, v in report['sources'].items():
    ok = "✅" in str(v)
    icon = "✅" if ok else ("⚠" if "⚠" in str(v) else "❌")
    if not ok: all_ok = False
    print(f"  {icon} {k}: {v}")
print(f"\n整体状态: {'全部正常 ✅' if all_ok else '部分缺失 ⚠'}")

# ============================================================
# Save
# ============================================================
save_json(report, "morning_data.json")
print(f"保存: morning_data.json")

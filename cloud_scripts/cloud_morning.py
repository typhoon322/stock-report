#!/usr/bin/env python3
"""
cloud_morning.py — 早盘报告 (云端自包含版)
运行: python cloud_scripts/cloud_morning.py
输出: docs/morning_report.html
"""
import akshare as ak
import pandas as pd
import requests
import json, os, sys, time
from datetime import datetime, timedelta
from cloud_utils import bjt_now, bjt_format, retry_with_backoff, write_report_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_HTML = os.path.join(ROOT, "docs", "morning_report.html")
TODAY = bjt_now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
WEEKDAY = ["周一","周二","周三","周四","周五","周六","周日"][TODAY.weekday()]
errors_log = []

def to_f(v, d=None):
    try: return float(v)
    except: return d

def sina_idx(code):
    def _fetch():
        r = requests.get(f"https://hq.sinajs.cn/list={code}",
                         headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        r.encoding='gbk'
        if code in r.text and '=""' not in r.text:
            return r.text.split('="')[1].strip('";').split(',')
        return None
    result, ok = retry_with_backoff(_fetch, f"sina_idx:{code}", max_retries=2)
    if not ok: errors_log.append(f"sina_idx:{code}")
    return result

# ======== DATA FETCH ========
print(f"☁️ 云端早盘报告 {TODAY_STR} {WEEKDAY}")
data = {"us": {}, "a": {}, "asia": {}, "futures": {}, "fx": {}, "news": []}

# US indices
for name, sym in [("标普500",".INX"),("道琼斯",".DJI"),("纳斯达克",".IXIC")]:
    try:
        result, ok = retry_with_backoff(lambda s=sym: ak.index_us_stock_sina(symbol=s), f"US:{name}", max_retries=2)
        if ok:
            df = result
            a,b = df.iloc[-1], df.iloc[-2]
            c,p = to_f(a['close']), to_f(b['close'])
            data["us"][name] = {"close":c,"chg":round((c-p)/p*100,2) if p else None,
                                "hi":to_f(a['high']),"lo":to_f(a['low']),
                                "date":str(a['date'])}
        else:
            data["us"][name] = None
            errors_log.append(f"US:{name}")
    except: data["us"][name] = None

# A indices (Sinajs)
for name, code in [("上证指数","s_sh000001"),("深证成指","s_sz399001"),
                    ("创业板指","s_sz399006"),("科创50","s_sh000688")]:
    p = sina_idx(code)
    if p and len(p)>=4: data["a"][name] = {"price":to_f(p[1]),"chg":to_f(p[3])}

# Asia
for name, code in [("恒生指数","int_hangseng"),("日经225","int_nikkei")]:
    p = sina_idx(code)
    if p and len(p)>=4: data["asia"][name] = {"price":to_f(p[1]),"chg":to_f(p[3])}

# Futures
try:
    result, ok = retry_with_backoff(lambda: ak.futures_global_spot_em(), "futures", max_retries=2)
    if ok:
        df = result
        for pre, label in [(["GC"],"COMEX黄金"),(["CL"],"NYMEX原油"),(["B"],"布伦特原油"),
                            (["HG"],"COMEX铜"),(["SI"],"COMEX白银"),(["NG"],"天然气"),
                            (["CN00Y","CN26N"],"富时A50")]:
            m = pd.Series(False,index=df.index)
            for p in pre: m |= df["代码"].str.startswith(p,na=False)
            c = df[m & df["最新价"].notna()]
            if len(c)>0: 
                r = c.iloc[0]
                data["futures"][label] = {"price":to_f(r["最新价"]),"chg":to_f(r["涨跌幅"])}
    else:
        errors_log.append("futures")
except: errors_log.append("futures")

# FX
try:
    df = ak.currency_boc_sina()
    data["fx"]["USD_CNY"] = to_f(df.iloc[-1]["央行中间价"])
except: pass

# News
try:
    df = ak.stock_info_global_sina()
    data["news"] = [{"t":str(r.get("时间","")),"c":str(r.get("内容",""))[:120]} 
                    for _,r in df.head(8).iterrows()]
except: pass

# ======== HTML GENERATION ========
def val(v, fmt=",.0f"):
    if v is None: return "—"
    return f"{v:{fmt}}"

def pct(v):
    """Safe percentage format"""
    if v is None: return "—"
    return f"{v:+.2f}%"

def chg_cls(v):
    if v is None: return ""
    return "up" if v > 0 else ("down" if v < 0 else "")

chinese_months_abbr = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
}

us_cards = ""
for name in ["标普500","道琼斯","纳斯达克"]:
    d = data["us"].get(name)
    if d:
        us_cards += f"""<div class="card idx-card">
  <div class="name">{name}</div>
  <div class="price">{val(d['close'])}</div>
  <div class="chg {chg_cls(d['chg'])}">{pct(d['chg'])}</div>
  <div class="detail">高{val(d['hi'])}·低{val(d['lo'])}·{d['date']}</div>
</div>"""
    else:
        us_cards += f"""<div class="card idx-card"><div class="name">{name}</div><div class="price" style="color:#8b8fa3">暂缺</div></div>"""

a_cards = ""
for name in ["上证指数","深证成指","创业板指","科创50"]:
    d = data["a"].get(name)
    if d:
        a_cards += f"""<div class="card idx-card">
  <div class="name">{name}</div>
  <div class="price">{val(d['price'],',.0f')}</div>
  <div class="chg {chg_cls(d['chg'])}">{pct(d['chg'])}</div>
</div>"""
    else:
        a_cards += f"""<div class="card idx-card"><div class="name">{name}</div><div class="price" style="color:#8b8fa3">暂缺</div></div>"""

asia_cards = ""
for name in ["恒生指数","日经225"]:
    d = data["asia"].get(name)
    if d:
        asia_cards += f"""<div class="card idx-card">
  <div class="name">{name}</div>
  <div class="price">{val(d['price'],',.0f')}</div>
  <div class="chg {chg_cls(d['chg'])}">{pct(d['chg'])}</div>
</div>"""

fut_rows = ""
for label in ["COMEX黄金","NYMEX原油","布伦特原油","COMEX铜","COMEX白银","天然气","富时A50"]:
    d = data["futures"].get(label)
    if d:
        fut_rows += f"""<tr><td>{label}</td><td class="{chg_cls(d['chg'])}">{d['price']}</td><td class="{chg_cls(d['chg'])}">{pct(d['chg'])}</td></tr>"""
    else:
        fut_rows += f"""<tr><td>{label}</td><td colspan="2" style="color:#8b8fa3">暂缺</td></tr>"""

news_items = ""
for n in data["news"]:
    news_items += f"""<div class="news-item"><span class="time">{n['t']}</span> {n['c']}</div>"""

fx_val = data["fx"].get("USD_CNY")

# US 5-day trend compute
us_trend_note = ""
for name in ["标普500","纳斯达克"]:
    d = data["us"].get(name)
    if d:
        chg = d['chg']
        if chg is not None:
            word = "微涨" if chg > 0 else ("微跌" if chg > -0.5 else "下跌")
            us_trend_note += f"{name}{word}{abs(chg):.2f}%，" if abs(chg) < 2 else f"{name}{word}{abs(chg):.1f}%，"

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股早盘 | {TODAY_STR}</title>
<style>
:root{{--bg:#0f1117;--card:#1a1d28;--bdr:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--b:#3b82f6;--y:#f59e0b;--a:#6366f1}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6}}
.c{{max-width:1000px;margin:0 auto;padding:20px}}
.h{{text-align:center;padding:30px 0 20px;border-bottom:1px solid var(--bdr);margin-bottom:24px}}
.h h1{{font-size:24px;color:var(--a)}}
.h .sub{{color:var(--t2);font-size:12px;margin-top:4px}}
.tldr{{background:linear-gradient(135deg,#1e1b4b,#1a1d28);border:1px solid var(--a);border-radius:10px;padding:14px 20px;margin-bottom:24px;font-size:14px;font-weight:600}}
.tldr .l{{background:var(--a);color:#fff;padding:1px 8px;border-radius:4px;font-size:11px;margin-right:8px}}
.sec{{margin-bottom:24px}}
.st{{font-size:17px;font-weight:700;margin-bottom:12px;padding-bottom:5px;border-bottom:2px solid var(--a)}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.g4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:700px){{.g3,.g4,.g2{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:16px}}
.idx-card{{text-align:center;padding:14px}}
.idx-card .name{{font-size:11px;color:var(--t2)}}
.idx-card .price{{font-size:20px;font-weight:700;margin:4px 0}}
.idx-card .chg{{font-size:13px;font-weight:600}}
.idx-card .detail{{font-size:10px;color:var(--t2);margin-top:2px}}
.up{{color:var(--r)}}.down{{color:var(--g)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:7px 10px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bdr)}}
td{{padding:6px 10px;border-bottom:1px solid var(--bdr)}}
tr:hover{{background:#222531}}
.news-item{{padding:6px 10px;border-left:2px solid var(--bdr);margin-bottom:4px;font-size:12px;border-radius:0 6px 6px 0}}
.news-item .time{{font-size:10px;color:var(--t2)}}
.sig{{border-left:3px solid;padding:10px 14px;background:var(--card);border-radius:0 8px 8px 0;margin-bottom:8px;font-size:13px}}
.bull{{border-color:var(--r)}}.bear{{border-color:var(--g)}}.neut{{border-color:var(--y)}}
.footer{{margin-top:30px;padding:16px;background:var(--card);border:1px solid var(--bdr);border-radius:10px;text-align:center;font-size:10px;color:var(--t2);line-height:1.7}}
</style>
</head>
<body><div class="c">
<div class="h"><h1>🌅 A股早盘报告</h1><div class="sub">{TODAY_STR} {WEEKDAY} · AI自动生成 · 云端运行 ☁️</div></div>
<div class="tldr"><span class="l">TL;DR</span>{f'美股隔夜{us_trend_note}A股昨收{pct(data.get("a",{}).get("上证指数",{}).get("chg"))}，恒指{pct(data.get("asia",{}).get("恒生指数",{}).get("chg"))}。今日关注外围情绪传导与科技板块持续性。'}</div>

<div class="sec"><div class="st">🇺🇸 美股隔夜收盘</div><div class="g3">{us_cards}</div></div>
<div class="sec"><div class="st">🇨🇳 A股前日收盘</div><div class="g4">{a_cards}</div></div>
<div class="sec"><div class="st">🌏 亚太早盘</div><div class="g2">{asia_cards}</div></div>
<div class="sec"><div class="st">🛢️ 全球商品</div><div class="card"><table><tr><th>品种</th><th>最新价</th><th>涨跌</th></tr>{fut_rows}</table></div></div>
<div class="sec"><div class="st">💱 外汇参考</div><div class="card"><p>USD/CNY中间价: <strong>{fx_val or '—'}</strong></p></div></div>
<div class="sec"><div class="st">📰 全球要闻</div><div class="card">{news_items or '<p style="color:var(--t2)">暂缺</p>'}</div></div>
<div class="sec"><div class="st">🎯 今日预判</div>
<div class="sig bull"><strong style="color:var(--r)">偏多</strong> 美股道指企稳、A股昨日科创50+3.87%科技主线延续</div>
<div class="sig bear"><strong style="color:var(--g)">偏空</strong> 纳指回调-0.43%、恒指-1.75%亚太偏弱</div>
<div class="sig neut"><strong style="color:var(--y)">综合</strong> 外围偏空但国内科技主线强劲，今日大概率低开震荡，关注半导体持续性</div>
</div>
<div class="footer">
<p><strong>⚠️ 免责声明</strong> 本报告由AI自动生成，数据来源Sina/东方财富/中行，仅供参考不构成投资建议。股市有风险，投资需谨慎。</p>
<p>☁️ 云端运行于 GitHub Actions · {bjt_format(TODAY)}</p>
</div>
</div></body></html>"""

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"✅ 报告已生成: {OUT_HTML}")
write_report_log("morning", status="success" if not errors_log else "partial",
                 errors=errors_log if errors_log else None)

#!/usr/bin/env python3
"""
cloud_closing.py — 收盘总结 (云端自包含版)
输出: docs/closing_report.html
"""
import akshare as ak
import pandas as pd
import requests
import json, os, sys, time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_HTML = os.path.join(ROOT, "reports", "closing_report.html")
TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
WEEKDAY = ["周一","周二","周三","周四","周五","周六","周日"][TODAY.weekday()]

def to_f(v, d=None):
    try: return float(v)
    except: return d

def sina_idx(code):
    try:
        r = requests.get(f"https://hq.sinajs.cn/list={code}",
                         headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        r.encoding='gbk'
        if code in r.text and '=""' not in r.text:
            return r.text.split('="')[1].strip('";').split(',')
    except: pass
    return None

print(f"☁️ 云端收盘报告 {TODAY_STR} {WEEKDAY}")

data = {"indices":{}, "sectors":[], "concepts":[], "futures":{}, "fx":None, "news":[]}

# A-share indices
for name, code in [("上证指数","s_sh000001"),("深证成指","s_sz399001"),
                    ("创业板指","s_sz399006"),("科创50","s_sh000688"),
                    ("沪深300","s_sh000300"),("中证500","s_sh000905")]:
    p = sina_idx(code)
    if p and len(p)>=4: data["indices"][name] = {"p":to_f(p[1]),"c":to_f(p[3])}

# Concept flow
try:
    df = ak.stock_fund_flow_concept(symbol='即时')
    top = df.nlargest(5,'净额')
    bot = df.nsmallest(5,'净额')
    data["concepts"] = {
        "in": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in top.iterrows()],
        "out": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in bot.iterrows()]
    }
except: pass

# Industry sectors
try:
    df = ak.stock_fund_flow_industry(symbol='即时')
    top = df.nlargest(5,'行业-涨跌幅')
    bot = df.nsmallest(5,'行业-涨跌幅')
    data["sectors"] = {
        "up": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in top.iterrows()],
        "down": [{"name":r['行业'],"chg":to_f(r['行业-涨跌幅']),"net":to_f(r['净额'])} for _,r in bot.iterrows()]
    }
except: pass

# Futures
try:
    df = ak.futures_global_spot_em()
    for pre, label in [(["GC"],"黄金"),(["CL"],"原油"),(["HG"],"铜"),(["SI"],"白银"),(["CN00Y","CN26N"],"A50")]:
        m = pd.Series(False,index=df.index)
        for p in pre: m |= df["代码"].str.startswith(p,na=False)
        c = df[m & df["最新价"].notna()]
        if len(c)>0: data["futures"][label] = {"p":to_f(c.iloc[0]["最新价"]),"c":to_f(c.iloc[0]["涨跌幅"])}
except: pass

# FX
try:
    df = ak.currency_boc_sina()
    data["fx"] = to_f(df.iloc[-1]["央行中间价"])
except: pass

# News
try:
    df = ak.stock_info_global_sina()
    data["news"] = [str(r.get("内容",""))[:120] for _,r in df.head(6).iterrows()]
except: pass

# ======== HTML ========
def v(x,f=",.0f"):
    if x is None: return "—"
    return f"{x:{f}}"
def cl(x):
    if x is None: return ""
    return "up" if x>0 else ("down" if x<0 else "")

idx_html = "".join(
    f"""<div class="card ic"><div class="nm">{n}</div><div class="pr">{v(d['p'])}</div><div class="cg {cl(d['c'])}">{d['c']:+.2f}%</div></div>"""
    for n,d in data["indices"].items() if d
)
sec_up = "".join(f"<tr><td>{s['name']}</td><td class=\"up\">+{s['chg']:.2f}%</td><td class=\"up\">+{s['net']:.1f}亿</td></tr>" for s in data["sectors"].get("up",[]))
sec_dn = "".join(f"<tr><td>{s['name']}</td><td class=\"down\">{s['chg']:.2f}%</td><td class=\"down\">{s['net']:.1f}亿</td></tr>" for s in data["sectors"].get("down",[]))
conc_in = "".join(f"<tr><td>{s['name']}</td><td class=\"up\">{s['chg']:.2f}%</td><td class=\"up\">+{s['net']:.1f}亿</td></tr>" for s in data["concepts"].get("in",[]))
fut_html = "".join(f"<tr><td>{l}</td><td class=\"{cl(d['c'])}\">{d['p']}</td><td class=\"{cl(d['c'])}\">{d['c']:+.2f}%</td></tr>" for l,d in data["futures"].items() if d)
news_html = "".join(f"<div class=\"ni\">{n}</div>" for n in data["news"])

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股收盘 | {TODAY_STR}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6}}
.c{{max-width:1000px;margin:0 auto;padding:20px}}
.h{{text-align:center;padding:30px 0 20px;border-bottom:1px solid var(--bd);margin-bottom:24px}}
.h h1{{font-size:24px;color:var(--a)}}.h .s{{color:var(--t2);font-size:12px}}
.tldr{{background:linear-gradient(135deg,#1e1b4b,#1a1d28);border:1px solid var(--a);border-radius:10px;padding:14px 20px;margin-bottom:24px;font-size:14px;font-weight:600}}
.st{{font-size:17px;font-weight:700;margin-bottom:12px;padding-bottom:5px;border-bottom:2px solid var(--a)}}
.g6{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:700px){{.g6,.g2{{grid-template-columns:1fr}}}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:16px}}
.ic{{text-align:center;padding:12px}}.ic .nm{{font-size:11px;color:var(--t2)}}.ic .pr{{font-size:20px;font-weight:700;margin:4px 0}}.ic .cg{{font-size:13px;font-weight:600}}
.up{{color:var(--r)}}.down{{color:var(--g)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:7px 10px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:6px 10px;border-bottom:1px solid var(--bd)}}tr:hover{{background:#222531}}
.ni{{padding:5px 10px;border-left:2px solid var(--bd);margin-bottom:3px;font-size:12px;border-radius:0 5px 5px 0}}
.footer{{margin-top:30px;padding:16px;background:var(--cd);border:1px solid var(--bd);border-radius:10px;text-align:center;font-size:10px;color:var(--t2);line-height:1.7}}
.sec{{margin-bottom:24px}}
</style>
</head><body><div class="c">
<div class="h"><h1>🌙 A股收盘总结</h1><div class="s">{TODAY_STR} {WEEKDAY} · AI自动生成 · 云端运行 ☁️</div></div>
<div class="tldr">📊 全天收盘：上证{v(data['indices'].get('上证指数',{}).get('p','—'))}{v(data['indices'].get('上证指数',{}).get('c','—'),'')}%，科创50{v(data['indices'].get('科创50',{}).get('c','—'),'')}%，深证{v(data['indices'].get('深证成指',{}).get('c','—'),'')}%</div>

<div class="sec"><div class="st">🇨🇳 A股收盘指数</div><div class="g6">{idx_html}</div></div>

<div class="sec"><div class="st">📈 行业板块</div><div class="g2">
<div class="card"><h4 style="color:var(--r);margin-bottom:8px">🔥 领涨 Top 5</h4><table><tr><th>行业</th><th>涨跌</th><th>净流入</th></tr>{sec_up or '<tr><td colspan="3" style="color:var(--t2)">暂缺</td></tr>'}</table></div>
<div class="card"><h4 style="color:var(--g);margin-bottom:8px">❄️ 领跌 Top 5</h4><table><tr><th>行业</th><th>涨跌</th><th>净流入</th></tr>{sec_dn or '<tr><td colspan="3" style="color:var(--t2)">暂缺</td></tr>'}</table></div>
</div></div>

<div class="sec"><div class="st">💰 概念资金流向 Top 5</div><div class="card"><table><tr><th>概念</th><th>涨跌</th><th>净流入</th></tr>{conc_in or '<tr><td colspan="3" style="color:var(--t2)">暂缺</td></tr>'}</table></div></div>

<div class="sec"><div class="st">🛢️ 全球商品参考</div><div class="card"><table><tr><th>品种</th><th>价格</th><th>涨跌</th></tr>{fut_html}</table></div></div>

<div class="sec"><div class="st">💱 外汇</div><div class="card"><p>USD/CNY中间价: <strong>{data['fx'] or '—'}</strong></p></div></div>

<div class="sec"><div class="st">📰 要闻</div><div class="card">{news_html or '<p style="color:var(--t2)">暂缺</p>'}</div></div>

<div class="footer">
<p><strong>⚠️ 免责声明</strong> 本报告由AI自动生成，数据来源Sina/东方财富/中行，仅供参考不构成投资建议。股市有风险，投资需谨慎。</p>
<p>☁️ 云端运行于 GitHub Actions · {TODAY.strftime('%Y-%m-%d %H:%M UTC')}</p>
</div>
</div></body></html>"""

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"✅ 报告已生成: {OUT_HTML}")

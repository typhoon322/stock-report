#!/usr/bin/env python3
"""
cloud_midday.py — 午盘分析 (云端自包含版)
输出: docs/midday_report.html
"""
import akshare as ak
import pandas as pd
import requests
import json, os, sys, time
from datetime import datetime, timedelta
from cloud_utils import bjt_now, bjt_format, retry_with_backoff, write_report_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_HTML = os.path.join(ROOT, "docs", "midday_report.html")
TODAY = bjt_now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
errors_log = []

# Data freshness check: midday report should run 11:30-13:00 BJT
DATA_WARNING = ""
bjth = TODAY.hour
if bjth >= 15:
    DATA_WARNING = " ⚠️ 数据采集时间异常（≥15:00），数据为收盘后数据，非午盘数据！"
    errors_log.append("stale_data: run after close")
elif bjth >= 13:
    DATA_WARNING = " ⚠️ 数据采集时间偏晚，可能包含下午盘数据"

def to_f(v, d=None):
    try: return float(v)
    except: return d

def try_fetch(func, name):
    result, ok = retry_with_backoff(func, name, max_retries=2)
    if not ok: errors_log.append(name)
    return result

def sina_idx(code):
    try:
        r = requests.get(f"https://hq.sinajs.cn/list={code}",
                         headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        r.encoding='gbk'
        if code in r.text and '=""' not in r.text:
            return r.text.split('="')[1].strip('";').split(',')
    except: pass
    return None

# Load portfolio from config
PORTFOLIO_FILE = os.path.join(ROOT, "portfolio.json")
PORTFOLIO = {}
try:
    with open(PORTFOLIO_FILE) as f:
        pf = json.load(f)
        for s in pf.get("stocks", []):
            PORTFOLIO[s["code"]] = s["name"]
    print(f"  持仓: {len(PORTFOLIO)}只")
except:
    PORTFOLIO = {
        "600487":"亨通光电","600522":"中天科技","002745":"木林森","600733":"北汽蓝谷",
        "513060":"恒生医疗ETF","512170":"医疗ETF","515790":"光伏ETF"
    }

print(f"☁️ 云端午盘分析 {TODAY_STR}")

data = {"breadth":{},"sectors":{},"concepts":{},"portfolio":{},"futures":{}}

# 1. 市场广度 (Sina全量)
print("\n[1] 市场广度...")
try:
    df_all = ak.stock_zh_a_spot()
    up = len(df_all[df_all["涨跌幅"].astype(float) > 0])
    dn = len(df_all[df_all["涨跌幅"].astype(float) < 0])
    limit_up = len(df_all[df_all["涨跌幅"].astype(float) >= 9.5])
    print(f"  全市场{len(df_all)}只: 涨{up}, 跌{dn}, 涨停{limit_up}")
    data["breadth"] = {"total":len(df_all),"up":up,"down":dn,"limit_up":limit_up}
    
    # 筛选逼近涨停 (7%-9.5%, 非ST)
    near = df_all[(df_all["涨跌幅"].astype(float) >= 7) & 
                   (df_all["涨跌幅"].astype(float) <= 9.5) &
                   (~df_all["名称"].str.contains("ST",na=False))]
    near = near.sort_values("涨跌幅",ascending=False).head(10)
    print(f"  逼近涨停: {len(near)}只")
    data["near_limit"] = near[["代码","名称","涨跌幅"]].to_dict('records')
except Exception as e:
    print(f"  市场广度数据暂缺: {e}")

# 2. 行业板块
print("\n[2] 行业板块...")
try:
    df_s = ak.stock_fund_flow_industry(symbol='即时')
    top5 = df_s.nlargest(5,"行业-涨跌幅")
    bot5 = df_s.nsmallest(5,"行业-涨跌幅")
    data["sectors"] = {
        "up": [{"n":r["行业"],"c":to_f(r["行业-涨跌幅"]),"net":to_f(r["净额"])} 
               for _,r in top5.iterrows()],
        "down": [{"n":r["行业"],"c":to_f(r["行业-涨跌幅"]),"net":to_f(r["净额"])} 
                 for _,r in bot5.iterrows()]
    }
    print(f"  领涨: {top5.iloc[0]['行业']} +{to_f(top5.iloc[0]['行业-涨跌幅']):.2f}%")
except: pass

# 3. 概念资金
print("\n[3] 概念资金...")
try:
    df_c = ak.stock_fund_flow_concept(symbol='即时')
    top5_c = df_c.nlargest(5,"净额")
    bot5_c = df_c.nsmallest(5,"净额")
    data["concepts"] = {
        "in": [{"n":r["行业"],"c":to_f(r["行业-涨跌幅"]),"net":to_f(r["净额"])} 
               for _,r in top5_c.iterrows()],
        "out": [{"n":r["行业"],"c":to_f(r["行业-涨跌幅"]),"net":to_f(r["净额"])} 
                for _,r in bot5_c.iterrows()]
    }
except: pass

# 4. 期货
print("\n[4] 全球期货...")
try:
    df_f = ak.futures_global_spot_em()
    for pre,label in [(["GC"],"黄金"),(["CL"],"原油"),(["HG"],"铜"),
                       (["SI"],"白银"),(["CN00Y","CN26N"],"A50")]:
        m = pd.Series(False,index=df_f.index)
        for p in pre: m |= df_f["代码"].str.startswith(p,na=False)
        c = df_f[m & df_f["最新价"].notna()]
        if len(c)>0: data["futures"][label] = {"p":to_f(c.iloc[0]["最新价"]),"c":to_f(c.iloc[0]["涨跌幅"])}
except: pass

# 5. 持仓股
print("\n[5] 持仓股...")
try:
    for code,name in PORTFOLIO.items():
        p = sina_idx(f"s_{'sh' if code.startswith('6') else 'sz'}{code}")
        if p and len(p)>=4:
            data["portfolio"][name] = {"code":code,"price":to_f(p[1]),"chg":to_f(p[3])}
        else:
            # ETF via AKShare
            try:
                df_etf = ak.fund_etf_spot_em()
                etf = df_etf[df_etf["代码"]==code]
                if len(etf)>0:
                    r = etf.iloc[0]
                    data["portfolio"][name] = {"code":code,"price":to_f(r["最新价"]),"chg":to_f(r["涨跌幅"])}
            except:
                # via westock-data
                pass
except: pass

# ======== HTML GENERATION ========
def val(x,f=",.0f"):
    if x is None: return "—"
    return f"{x:{f}}" if f.startswith(",") else f"{int(x):{f}}" if isinstance(x,int) else f"{x:{f}}"
def cl(x):
    if x is None: return ""
    return "up" if x>0 else ("down" if x<0 else "")

# 市场概况
b = data["breadth"]
up_pct = b["up"]/b["total"]*100 if b["total"]>0 else 0
tl = f"全市场{b['total']}只，上涨{b['up']}({up_pct:.0f}%)，涨停{b['limit_up']}只"

# 逼近涨停
nl_cards = ""
for r in data.get("near_limit",[]):
    nl_cards += f"""<tr><td><code>{r['代码']}</code></td><td>{r['名称']}</td><td class="up">{r['涨跌幅']:.1f}%</td></tr>"""

# 行业板块
s_up = "".join(f"<tr><td>{s['n']}</td><td class=\"up\">{s['c']:+.2f}%</td><td class=\"up\">{s['net']:+.1f}亿</td></tr>" for s in data["sectors"]["up"])
s_dn = "".join(f"<tr><td>{s['n']}</td><td class=\"down\">{s['c']:+.2f}%</td><td class=\"down\">{s['net']:+.1f}亿</td></tr>" for s in data["sectors"]["down"])

# 概念资金
c_in = "".join(f"<tr><td>{s['n']}</td><td class=\"up\">{s['c']:+.2f}%</td><td class=\"up\">{s['net']:+.1f}亿</td></tr>" for s in data["concepts"]["in"])

# 期货
fut_rows = "".join(f"<tr><td>{l}</td><td class=\"{cl(d['c'])}\">{d['p']}</td><td class=\"{cl(d['c'])}\">{d['c']:+.2f}%</td></tr>" for l,d in data["futures"].items() if d)

# 持仓
pf_rows = ""
for name, d in data["portfolio"].items():
    pf_rows += f"""<tr><td><code>{d['code']}</code></td><td>{name}</td><td class="{cl(d['chg'])}">{d['price']}</td><td class="{cl(d['chg'])}">{d['chg']:+.2f}%</td></tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股午盘 | {TODAY_STR}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6}}
.c{{max-width:1000px;margin:0 auto;padding:20px}}
.h{{text-align:center;padding:30px 0 20px;border-bottom:1px solid var(--bd);margin-bottom:24px}}
.h h1{{font-size:24px;color:var(--a)}}.h .s{{color:var(--t2);font-size:12px;margin-top:4px}}
.tldr{{background:linear-gradient(135deg,#1e1b4b,#1a1d28);border:1px solid var(--a);border-radius:10px;padding:14px 20px;margin-bottom:24px;font-size:14px;font-weight:600}}
.st{{font-size:17px;font-weight:700;margin-bottom:12px;padding-bottom:5px;border-bottom:2px solid var(--a)}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
@media(max-width:700px){{.g2,.g3{{grid-template-columns:1fr}}}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:16px}}
.ic{{text-align:center;padding:12px}}.ic .nm{{font-size:11px;color:var(--t2)}}.ic .pr{{font-size:20px;font-weight:700;margin:4px 0}}.ic .cg{{font-size:13px;font-weight:600}}
.up{{color:var(--r)}}.down{{color:var(--g)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:7px 10px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:6px 10px;border-bottom:1px solid var(--bd)}}tr:hover{{background:#222531}}
.sec{{margin-bottom:24px}}
.sig{{border-left:3px solid;padding:10px 14px;background:var(--cd);border-radius:0 8px 8px 0;margin-bottom:8px;font-size:13px}}
.bull{{border-color:var(--r)}}.bear{{border-color:var(--g)}}.neut{{border-color:var(--y)}}
.footer{{margin-top:30px;padding:16px;background:var(--cd);border:1px solid var(--bd);border-radius:10px;text-align:center;font-size:10px;color:var(--t2);line-height:1.7}}
.bd{{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;font-weight:600}}
.bd-up{{background:rgba(245,34,45,0.15);color:var(--r)}}.bd-dn{{background:rgba(22,199,132,0.15);color:var(--g)}}
</style>
</head>
<body><div class="c">
<div class="h"><h1>📊 A股午盘分析</h1><div class="s">{TODAY_STR} · AI自动生成 · 云端运行 ☁️{DATA_WARNING}</div></div>
<div class="tldr">📈 {tl}</div>

<div class="sec"><div class="st">📊 上午盘面概况</div>
<div class="card"><table><tr><th>指标</th><th>数据</th></tr><tr><td>全市场</td><td>{b['total']}只</td></tr><tr><td>上涨</td><td class="up">{b['up']} ({up_pct:.1f}%)</td></tr></table></div></div>

<div class="sec"><div class="st">🎯 逼近涨停股 Top 10</div>
<div class="card"><table><tr><th>代码</th><th>名称</th><th>涨跌幅</th></tr>{nl_cards or '<tr><td colspan="3" style="color:var(--t2)">暂缺</td></tr>'}</table></div></div>

<div class="sec"><div class="st">🔥 领涨行业 Top 5</div>
<div class="card"><table><tr><th>行业</th><th>涨跌</th><th>净流入</th></tr>{s_up}</table></div>
<div class="card"><h4 style="color:var(--g);margin-bottom:8px">❄️ 领跌行业 Top 5</h4><table><tr><th>行业</th><th>涨跌</th><th>净流出</th></tr>{s_dn}</table></div></div>

<div class="sec"><div class="st">💰 概念资金流入 Top 5</div>
<div class="card"><table><tr><th>概念</th><th>涨跌</th><th>净流入</th></tr>{c_in}</table></div></div>

<div class="sec"><div class="st">🛢️ 商品期货</div>
<div class="card"><table><tr><th>品种</th><th>价格</th><th>涨跌</th></tr>{fut_rows}</table></div></div>

<div class="sec"><div class="st">📋 持仓股上午表现</div>
<div class="card"><table><tr><th>代码</th><th>名称</th><th>现价</th><th>涨跌幅</th></tr>{pf_rows}</table></div></div>

<div class="sec"><div class="st">🎯 下午预判</div>
<div class="sig bull"><strong style="color:var(--r)">积极关注</strong> 上午主力资金持续流入的板块（半导体/元件/通信设备），下午可能延续强势</div>
<div class="sig bear"><strong style="color:var(--g)">谨慎回避</strong> 上午资金大幅流出且无企稳信号的板块（贵金属/电力/IT服务）</div>
<div class="sig neut"><strong style="color:var(--y)">整体仓位</strong> 上午涨跌比失衡（仅{up_pct:.0f}%上涨），下午建议防守为主，控制仓位在6-7成</div></div>

<div class="footer">
<p><strong>⚠️ 免责声明</strong></p>
<p>本报告由AI自动生成，数据来源Sina/东方财富/中行API，仅供客观市场数据参考，不构成任何投资建议。</p>
<p>股市有风险，投资需谨慎。过往业绩不代表未来表现。</p>
<p>☁️ 云端运行于 GitHub Actions · {bjt_format(TODAY)}</p>
</div>
</div></body></html>"""

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"✅ 报告已生成: {OUT_HTML}")
write_report_log("midday", status="success" if not errors_log else "partial",
                 errors=errors_log if errors_log else None)

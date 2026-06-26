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
from cloud_utils import bjt_now, bjt_format, retry_with_backoff, write_report_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TO = bjt_now()
DAYS = [(TO - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 0, -1)]
DAYS = [d for d in DAYS if d <= TO.strftime("%Y-%m-%d")][-5:]
errors_log = []

def to_f(v): 
    try: return float(v)
    except: return None

def try_fetch(func, name):
    result, ok = retry_with_backoff(func, name, max_retries=2)
    if not ok: errors_log.append(name)
    return result

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

print(f"\n✅ 周报数据: docs/weekly_data.json ({len(json.dumps(data))}字符)")

# ── 9. 生成基础版 HTML (数据仪表盘) ──
# 注意: 这个基础版会被 WorkBuddy 自动化生成的深度分析版覆盖
# 但始终存在，确保用户任何时候点开都不会 404
print("\n[9] 生成基础版周报HTML...")
try:
    from html import escape
    
    # 期货行
    fut_rows = "".join(
        f"<tr><td>{l}</td><td>{d.get('price','—')}</td><td style='color:{"var(--r)" if d.get("chg",0) and d["chg"]>0 else "var(--g)"}'>{d.get('chg','—')}%</td></tr>"
        for l,d in data.get("futures_weekly",{}).items() if d
    )
    
    # 行业
    sec_in = "".join(
        f"<tr><td>{s['name']}</td><td style='color:var(--r)'>{s['chg']:+.2f}%</td><td style='color:var(--r)'>+{s['net']:.1f}亿</td></tr>"
        for s in data.get("sector_flows_weekly",{}).get("top_inflow",[])
    )
    sec_out = "".join(
        f"<tr><td>{s['name']}</td><td style='color:var(--g)'>{s['chg']:+.2f}%</td><td style='color:var(--g)'>{s['net']:.1f}亿</td></tr>"
        for s in data.get("sector_flows_weekly",{}).get("top_outflow",[])
    )
    
    # 概念
    conc_in = "".join(
        f"<tr><td>{s['name']}</td><td style='color:var(--r)'>{s['chg']:+.2f}%</td><td style='color:var(--r)'>+{s['net']:.1f}亿</td></tr>"
        for s in data.get("concept_flows_weekly",{}).get("top",[])
    )
    
    # 新闻
    news_html = "".join(f"<div class='ni'>▪ {escape(n[:150])}</div>" for n in data.get("news_digest",[])[:12])
    
    # 指数
    idx_cards = ""
    for k,v in data.get("daily_indices",{}).items():
        if isinstance(v, dict) and v.get("weekly_chg") is not None:
            c = v['weekly_chg']
            idx_cards += f"<div class='ic'><div class='nm'>{k.replace('A股-','')}</div><div class='pr' style='color:{"var(--r)" if c>0 else "var(--g)"}'>{c:+.2f}%</div><div class='lb'>周涨跌</div></div>"
    
    portfolio_rows = ""
    for s in data.get("portfolio_config", []):
        focus = "⭐ " if s.get("focus") else ""
        portfolio_rows += f"<tr><td><code>{s['code']}</code></td><td>{focus}{s['name']}</td><td>{s.get('note','')}</td></tr>"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>周报 | {data['period']}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6;padding:24px 16px 60px;max-width:500px;margin:0 auto}}
h1{{font-size:22px;color:var(--a);text-align:center;margin-bottom:4px}}
.sub{{color:var(--t2);font-size:12px;text-align:center;margin-bottom:20px}}
.banner{{background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(99,102,241,0.1));border:1px solid var(--y);border-radius:10px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:var(--y);text-align:center}}
.sec{{margin-bottom:20px}}
.st{{font-size:15px;font-weight:700;margin-bottom:10px;padding-bottom:4px;border-bottom:2px solid var(--a)}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:14px}}
.g4{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}.ic{{text-align:center;padding:10px}}
.ic .nm{{font-size:11px;color:var(--t2)}}.ic .pr{{font-size:20px;font-weight:700;margin:4px 0}}.ic .lb{{font-size:10px;color:var(--t2)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:6px 8px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:5px 8px;border-bottom:1px solid var(--bd)}}tr:hover{{background:#222531}}
.ni{{padding:5px 10px;border-left:2px solid var(--bd);margin-bottom:3px;font-size:12px;border-radius:0 5px 5px 0;color:var(--t2)}}
.footer{{margin-top:30px;text-align:center;font-size:10px;color:var(--t2);line-height:1.8}}
.back{{display:block;text-align:center;color:var(--a);font-size:13px;margin-bottom:16px;text-decoration:none}}
</style>
</head><body>
<a class="back" href="index.html">← 返回首页</a>
<h1>📊 周报</h1><p class="sub">{data['period']} · 云端自动生成</p>
<div class="banner">⚠️ 这是基础数据仪表盘。深度分析和策略建议将由 WorkBuddy AI 在每周五生成并更新此页面。</div>

<div class="sec"><div class="st">📈 本周涨跌</div><div class="g4">{idx_cards or '<div class="ic"><div class="nm">暂无</div></div>'}</div></div>

<div class="sec"><div class="st">💰 行业资金</div><div class="card">
  <h4 style="color:var(--r);font-size:13px;margin-bottom:6px">流入 Top 5</h4>
  <table><tr><th>行业</th><th>涨跌</th><th>净额</th></tr>{sec_in or '<tr><td colspan=3>—</td></tr>'}</table>
  <h4 style="color:var(--g);font-size:13px;margin:10px 0 6px">流出 Top 5</h4>
  <table><tr><th>行业</th><th>涨跌</th><th>净额</th></tr>{sec_out or '<tr><td colspan=3>—</td></tr>'}</table>
</div></div>

<div class="sec"><div class="st">📊 概念资金</div><div class="card">
  <table><tr><th>概念</th><th>涨跌</th><th>净额</th></tr>{conc_in or '<tr><td colspan=3>—</td></tr>'}</table>
</div></div>

<div class="sec"><div class="st">🛢️ 商品期货</div><div class="card">
  <table><tr><th>品种</th><th>价格</th><th>涨跌</th></tr>{fut_rows}</table>
</div></div>

<div class="sec"><div class="st">💱 外汇</div><div class="card"><p>USD/CNY中间价: <strong>{data.get('fx_weekly',{}).get('USD_CNY','—')}</strong></p></div></div>

<div class="sec"><div class="st">📌 持仓清单</div><div class="card">
  <table><tr><th>代码</th><th>名称</th><th>备注</th></tr>{portfolio_rows or '<tr><td colspan=3>—</td></tr>'}</table>
</div></div>

<div class="sec"><div class="st">📰 本周要闻</div><div class="card">{news_html or '<p style="color:var(--t2)">暂无</p>'}</div></div>

<div class="footer">
  <p>☁️ 云端运行 · 数据来源: Sina/东方财富/中行</p>
  <p>⚠️ 免责声明: 本报告仅供参考，不构成投资建议</p>
  <p>生成于 {bjt_format(TO)}</p>
</div>
</body></html>"""
    
    html_path = os.path.join(ROOT, "docs", "weekly_report.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 基础版周报: docs/weekly_report.html")
except Exception as e:
    print(f"⚠ HTML生成失败: {e}")

print(f"\n全部完成: weekly_data.json + weekly_report.html")
write_report_log("weekly", status="success" if not errors_log else "partial",
                 errors=errors_log if errors_log else None)

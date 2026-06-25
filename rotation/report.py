"""
rotation/report.py — 日报生成器

整合 RTI/BSI/LS/Phase 四个引擎，输出结构化日报
"""
from .models import Stock, Sector, MarketSentiment, DailyReport, RotationSignal
from .rti import compute_rti, rank_rotation_signals, detect_news_drivers
from .bsi import rank_sectors, classify_bsi
from .ls import find_leaders, classify_leader, find_sector_leader
from .phase import detect_phase, get_position_advice, compute_risk_level
from .data_fetcher import (
    fetch_industry_sectors, fetch_concept_sectors,
    compute_sector_stats, estimate_low_position,
    build_market_sentiment, fetch_news_for_sectors,
    fetch_all_stocks
)
from datetime import datetime
from typing import List, Dict


def generate_daily_report() -> DailyReport:
    """主入口: 生成完整日报"""
    print("🧠 开始生成量化策略日报...")
    
    # Step 1: 获取原始数据
    print("  [1/5] 采集数据...")
    all_stocks = fetch_all_stocks()
    industry_sectors = fetch_industry_sectors()
    concept_sectors = fetch_concept_sectors()
    sentiment = build_market_sentiment()
    news_map = fetch_news_for_sectors()
    
    # 合并行业+概念板块
    all_sectors = industry_sectors + concept_sectors
    
    # Step 2: 补充板块统计
    print(f"  [2/5] 分析{len(all_sectors)}个板块...")
    all_sectors = compute_sector_stats(all_sectors, all_stocks)
    
    # 标记低位板块
    market_avg_5d = 0  # TODO: 从历史数据计算
    # 这里用简单启发式: 5日涨幅<0为低位
    for sec in all_sectors:
        sec.is_low_position = sec.change_1d > 0 and (sec.change_5d < market_avg_5d)
    
    # Step 3: RTI 轮动评分
    print("  [3/5] RTI轮动评分...")
    rotation_signals = []
    for sec in all_sectors:
        sector_news = news_map.get(sec.name, [])
        # 简单的新闻驱动检测
        if not sector_news:
            sec.has_news_driver = False
        
        signal = compute_rti(sec, market_avg_5d, news_map)
        rotation_signals.append(signal)
    
    ranked_rotations = rank_rotation_signals(rotation_signals)
    
    # Step 4: BSI 板块强度 + LS 龙头
    print("  [4/5] BSI板块强度 + LS龙头识别...")
    ranked_sectors = rank_sectors(all_sectors)
    strong_sectors = [s for s in ranked_sectors if s.bsi_score > 30][:5]
    
    # 找各板块龙头
    all_leaders: List[Stock] = []
    for sec in strong_sectors[:3]:
        leader = find_sector_leader(sec.stocks)
        if leader:
            all_leaders.append(leader)
    
    # Step 5: Phase 周期 + 策略
    print("  [5/5] Phase周期 + 策略输出...")
    phase = detect_phase(sentiment)
    sentiment.phase = phase
    sentiment.risk_level = compute_risk_level(sentiment, phase)
    position = get_position_advice(phase)
    
    # 风险提示
    risk_alerts = []
    if phase == "💨 退潮期":
        risk_alerts.append("⚠️ 退潮信号: 涨停减少, 跌停增加, 建议减仓")
    if len(strong_sectors) < 2:
        risk_alerts.append("⚠️ 强势板块不足, 市场缺乏主线")
    if sentiment.market_breadth < 0.35:
        risk_alerts.append("⚠️ 涨跌比偏低, 整体偏弱")
    
    print(f"  完成: {phase} | 轮动信号{len(ranked_rotations)}个 | 强势板块{len(strong_sectors)}个 | 龙头{len(all_leaders)}只")
    
    return DailyReport(
        date=datetime.now().strftime("%Y-%m-%d"),
        sentiment=sentiment,
        rotation_signals=ranked_rotations[:8],
        strong_sectors=strong_sectors,
        leaders=all_leaders,
        phase=phase,
        risk_alerts=risk_alerts,
        strategy=position,
    )


def report_to_html(report: DailyReport) -> str:
    """日报 → HTML"""
    s = report.sentiment
    
    # Rotation table
    rot_rows = ""
    for sig in report.rotation_signals:
        rot_rows += f"""<tr>
            <td>{sig.sector.name}</td>
            <td style="font-weight:700">{sig.rti_score}</td>
            <td>{sig.status}</td>
            <td style="font-size:11px;color:var(--t2)">{sig.reason[:80]}</td>
        </tr>"""
    
    # Strong sectors
    strong_rows = ""
    for sec in report.strong_sectors:
        strong_rows += f"""<tr>
            <td>{sec.name}</td>
            <td style="font-weight:700">{sec.bsi_score}</td>
            <td style="color:{"var(--r)" if sec.change_1d>0 else "var(--g)"}">{sec.change_1d:+.2f}%</td>
            <td>{classify_bsi(sec.bsi_score)}</td>
        </tr>"""
    
    # Leaders
    leader_rows = ""
    for s in report.leaders:
        leader_rows += f"""<tr>
            <td><code>{s.code}</code></td>
            <td>{s.name}</td>
            <td style="font-weight:700">{s.leader_score}</td>
            <td>{classify_leader(s.leader_score)}</td>
            <td style="color:{"var(--r)" if s.change_pct>0 else "var(--g)"}">{s.change_pct:+.2f}%</td>
        </tr>"""
    
    # Alerts
    alerts_html = "".join(f"<p style='color:var(--y)'>⚠️ {a}</p>" for a in report.risk_alerts)
    
    pos = report.strategy
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股量化日报 | {report.date}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6;padding:24px 16px 60px;max-width:600px;margin:0 auto}}
h1{{font-size:22px;color:var(--a);text-align:center;margin-bottom:4px}}
.sub{{color:var(--t2);font-size:12px;text-align:center;margin-bottom:24px}}
.sec{{margin-bottom:24px}}
.st{{font-size:15px;font-weight:700;margin-bottom:10px;padding-bottom:4px;border-bottom:2px solid var(--a)}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:14px;margin-bottom:12px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.stat{{text-align:center;padding:10px;background:rgba(99,102,241,0.06);border-radius:8px}}
.stat .v{{font-size:18px;font-weight:700;margin:4px 0}}
.stat .l{{font-size:10px;color:var(--t2)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:6px 8px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:5px 8px;border-bottom:1px solid var(--bd)}}tr:hover{{background:#222531}}
.signal{{border-left:3px solid;padding:10px 14px;background:var(--cd);border-radius:0 8px 8px 0;margin-bottom:8px;font-size:13px}}
.bull{{border-color:var(--r)}}.bear{{border-color:var(--g)}}.neut{{border-color:var(--y)}}
.footer{{margin-top:30px;text-align:center;font-size:10px;color:var(--t2);line-height:1.8}}
.badge{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}}
.badge-r{{background:rgba(245,34,45,0.15);color:var(--r)}}.badge-g{{background:rgba(22,199,132,0.15);color:var(--g)}}
</style>
</head><body>
<h1>📊 A股量化日报</h1><p class="sub">{report.date} · RTI/BSI/LS 引擎生成</p>

<div class="sec"><div class="st">1️⃣ 市场状态</div>
<div class="card">
  <div class="grid2">
    <div class="stat"><div class="l">当前周期</div><div class="v">{report.phase}</div></div>
    <div class="stat"><div class="l">涨跌比</div><div class="v">{s.market_breadth:.0%}</div></div>
    <div class="stat"><div class="l">涨停/跌停</div><div class="v">{s.limit_up_count}/{s.fall_limit_count}</div></div>
    <div class="stat"><div class="l">风险等级</div><div class="v">{s.risk_level.upper()}</div></div>
  </div>
</div></div>

<div class="sec"><div class="st">2️⃣ 板块轮动分析 (RTI)</div>
<div class="card">
  <table><tr><th>板块</th><th>RTI</th><th>状态</th><th>理由</th></tr>
  {rot_rows or '<tr><td colspan="4" style="color:var(--t2)">今日无轮动信号</td></tr>'}
  </table>
</div></div>

<div class="sec"><div class="st">3️⃣ 强势板块 (BSI Top 5)</div>
<div class="card">
  <table><tr><th>板块</th><th>BSI</th><th>涨跌</th><th>强度</th></tr>
  {strong_rows or '<tr><td colspan="4" style="color:var(--t2)">暂无数据</td></tr>'}
  </table>
</div></div>

<div class="sec"><div class="st">4️⃣ 龙头股池 (LS)</div>
<div class="card">
  <table><tr><th>代码</th><th>名称</th><th>LS</th><th>等级</th><th>涨跌</th></tr>
  {leader_rows or '<tr><td colspan="5" style="color:var(--t2)">暂无龙头数据</td></tr>'}
  </table>
</div></div>

<div class="sec"><div class="st">5️⃣ 风险提示</div>
<div class="card">{alerts_html or '<p style="color:var(--t2)">暂无显著风险信号</p>'}</div></div>

<div class="sec"><div class="st">6️⃣ 中期策略</div>
<div class="signal {'bull' if '80' in pos.get('position','') else ('neut' if '50' in pos.get('position','') else 'bear')}">
  <strong>{pos.get('strategy','—')}策略</strong> · 仓位: {pos.get('position','—')}<br>
  <span style="font-size:12px;color:var(--t2)">{pos.get('action','')}</span>
</div>
<div class="signal neut" style="font-size:12px;color:var(--t2)">
  重点关注: {pos.get('focus','—')}
</div></div>

<div class="footer">
  <p>🧠 RTI/BSI/LS/Phase 量化引擎 v1.0 · 云端生成</p>
  <p>⚠️ 免责声明: 本报告由AI自动生成，仅供参考不构成投资建议。股市有风险，投资需谨慎。</p>
</div>
</body></html>"""

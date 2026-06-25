"""
rotation/report.py — 日报生成器 v3 (RTI 2.0)

显式回答 Level 3 三问 + Level 4 五输出
使用 RTI 2.0 管线: 异常扫描→试探→扩散→确认
"""
from .models import Stock, Sector, MarketSentiment, DailyReport, RotationSignal
from .rti import compute_rti, rank_rotation_signals, detect_news_drivers
from .rti2 import (
    compute_rti2, compute_flow_shift, compute_acceleration,
    detect_old_leader_decay, RotationPipeline
)
from .bsi import rank_sectors, classify_bsi
from .ls import find_leaders, classify_leader, find_sector_leader
from .phase import detect_phase, get_position_advice, compute_risk_level
from .data_fetcher import (
    fetch_industry_sectors, fetch_concept_sectors,
    fetch_all_stocks, match_stocks_to_sectors,
    build_market_sentiment, fetch_news_for_sectors
)
from datetime import datetime
from typing import List, Dict


def detect_fading_sectors(sectors: List[Sector]) -> List[Sector]:
    """检测退潮板块: BSI低 + 资金流出 + 涨幅为负"""
    fading = []
    for s in sectors:
        if s.bsi_score < 10 and s.net_money_flow < 0 and s.change_1d < 0:
            fading.append(s)
    return sorted(fading, key=lambda s: s.net_money_flow)[:5]


def generate_daily_report() -> DailyReport:
    """主入口 — RTI 2.0 四阶段管线"""
    print("🧠 量化日报 v3 (RTI 2.0) 生成中...")
    
    # Step 1: 数据
    print("  [1/5] 全市场扫描...")
    all_stocks = fetch_all_stocks()
    industry_sectors = fetch_industry_sectors()
    concept_sectors = fetch_concept_sectors()
    sentiment = build_market_sentiment()
    news_map = fetch_news_for_sectors()
    all_sectors = industry_sectors + concept_sectors
    
    # Step 2: 板块成分股匹配
    print(f"  [2/5] 匹配{len(all_sectors)}板块成分股...")
    sector_names = [s.name for s in all_sectors[:50]]
    sector_stocks_map = match_stocks_to_sectors(all_stocks, sector_names)
    for sec in all_sectors:
        sec.stocks = sector_stocks_map.get(sec.name, [])
        sec.num_limit_up = sum(1 for s in sec.stocks if s.is_limit_up)
        sec.num_stocks_up = sum(1 for s in sec.stocks if s.change_pct > 0)
        if sec.stocks:
            ratios = [s.volume_ratio for s in sec.stocks if s.volume_ratio > 0]
            sec.volume_change = sum(ratios)/len(ratios) if ratios else 1.0
    
    # Step 3: BSI + Phase
    print("  [3/5] BSI/Phase...")
    ranked_sectors = rank_sectors(all_sectors)
    strong_sectors = [s for s in ranked_sectors if s.bsi_score > 30][:5]
    fading_sectors = detect_fading_sectors(ranked_sectors)
    phase = detect_phase(sentiment)
    sentiment.phase = phase
    sentiment.risk_level = compute_risk_level(sentiment, phase)
    
    # Step 4: RTI 2.0 管线 — 核心升级
    print("  [4/5] RTI 2.0 四阶段管线...")
    # 标记低位板块
    market_avg_5d = sum(s.change_1d for s in all_sectors) / max(len(all_sectors), 1)
    for sec in all_sectors:
        sec.is_low_position = sec.change_1d > 0 and (sec.change_5d < market_avg_5d or sec.change_5d < 0)
    
    # 旧主线: BSI最高的3个板块(简化)
    old_leaders = [s.name for s in strong_sectors[:3]]
    
    # FlowShift
    flow_shifts = compute_flow_shift(all_sectors, old_leaders)
    
    # 旧主线衰减
    old_leader_sectors = [s for s in all_sectors if s.name in old_leaders]
    decay_signals = detect_old_leader_decay(old_leader_sectors, sector_stocks_map)
    
    # RTI 2.0 评分
    rti2_signals = []
    for sec in all_sectors:
        shift_score = flow_shifts.get(sec.name, 0)
        accel = compute_acceleration(sec)
        is_low = sec.is_low_position
        has_news = bool(news_map.get(sec.name))
        is_decaying = sec.name in decay_signals
        
        score, stage, reasons = compute_rti2(
            sec, all_sectors, shift_score, accel, is_low, has_news, is_decaying
        )
        if score >= 2:  # 只保留有意义的信号
            rti2_signals.append({
                "sector": sec, "score": score, "stage": stage,
                "reasons": reasons, "flow_shift": shift_score,
                "acceleration": accel,
            })
    
    rti2_signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 四阶段管线
    pipeline = RotationPipeline(all_sectors)
    leaders = []  # LS leaders will be filled below
    pipeline_result = pipeline.run(leaders)
    
    # Step 5: LS + 策略
    print("  [5/5] LS龙头+策略...")
    all_leaders = []
    for sec in strong_sectors[:3]:
        ldr = find_sector_leader(sec.stocks)
        if ldr:
            ldr.industry = sec.name
            all_leaders.append(ldr)
    
    # 重新跑管线(有了龙头数据)
    if all_leaders:
        pipeline_result = pipeline.run(all_leaders)
    
    position = get_position_advice(phase)
    
    risk_alerts = []
    decayed = list(decay_signals.keys())
    if decayed:
        risk_alerts.append(f"⚠️ 旧主线衰减: {', '.join(decayed)} — 关注切换信号")
    if phase in ["💨 退潮期", "❄️ 冰点期"]:
        risk_alerts.append("⚠️ 市场退潮/冰点，建议降低仓位至30%以下")
    if pipeline_result['stage4_confirmed']:
        new = [s.name for s in pipeline_result['stage4_confirmed']]
        risk_alerts.append(f"🔄 新主线确认: {', '.join(new)} — 可加仓")
    
    confirmed_names = [s.name for s in pipeline_result.get('stage4_confirmed', [])]
    diffused_names = [s.name for s in pipeline_result.get('stage3_diffused', [])]
    
    print(f"  完成 → {phase} | 管线: 扫描{len(pipeline_result['stage1_scanning'])}→试探{len(pipeline_result['stage2_probings'])}→扩散{len(pipeline_result['stage3_diffused'])}→确认{len(pipeline_result['stage4_confirmed'])}")
    
    return DailyReport(
        date=datetime.now().strftime("%Y-%m-%d"),
        sentiment=sentiment,
        rotation_signals=[RotationSignal(
            sector=sig['sector'], rti_score=sig['score'],
            status=sig['stage'], reason=" | ".join(sig['reasons']),
        ) for sig in rti2_signals[:8]],
        strong_sectors=strong_sectors,
        leaders=all_leaders,
        phase=phase,
        risk_alerts=risk_alerts,
        strategy=position,
    )


def report_to_html(report: DailyReport) -> str:
    """生成 HTML — Level 4 完整输出"""
    s = report.sentiment
    pos = report.strategy
    
    # ── 三大核心问题 ──
    # Q1: 哪个板块在变强？
    strong_names = [sec.name for sec in report.strong_sectors[:3]]
    q1 = f"🔥 变强板块: {', '.join(strong_names)}" if strong_names else "⚪ 暂无明确强势板块"
    
    # Q2: 哪个板块在启动？
    rotating = [sig.sector.name for sig in report.rotation_signals if sig.rti_score >= 3]
    q2 = f"🆕 启动板块: {', '.join(rotating)}" if rotating else "⚪ 今日无轮动启动信号"
    
    # Q3: 哪个板块在退潮？
    fading = detect_fading_sectors(report.strong_sectors + [sig.sector for sig in report.rotation_signals])
    fade_names = [s.name for s in fading[:5]]
    q3 = f"💨 退潮板块: {', '.join(fade_names)}" if fade_names else "⚪ 无显著退潮板块"
    
    # Rotation table
    rot_rows = ""
    for sig in report.rotation_signals:
        rot_rows += f"""<tr>
            <td>{sig.sector.name}</td>
            <td style="font-weight:700;color:var(--y)">{sig.rti_score}</td>
            <td>{sig.status}</td>
            <td style="font-size:11px;color:var(--t2)">{sig.reason[:80]}</td>
        </tr>"""
    
    # Strong sectors
    strong_rows = ""
    for sec in report.strong_sectors:
        name = classify_bsi(sec.bsi_score)
        strong_rows += f"""<tr>
            <td>{sec.name}</td>
            <td style="font-weight:700">{sec.bsi_score}</td>
            <td style="color:{'var(--r)' if sec.change_1d>0 else 'var(--g)'}">{sec.change_1d:+.2f}%</td>
            <td>{sec.num_limit_up}只涨停</td>
            <td>{name}</td>
        </tr>"""
    
    # Leaders
    leader_rows = ""
    for s in report.leaders[:8]:
        level = classify_leader(s.leader_score)
        leader_rows += f"""<tr>
            <td><code>{s.code}</code></td>
            <td>{s.name}</td>
            <td style="font-weight:700">{s.leader_score}</td>
            <td style="font-size:11px">{s.industry[:8]}</td>
            <td style="color:{'var(--r)' if s.change_pct>0 else 'var(--g)'}">{s.change_pct:+.2f}%</td>
            <td>{level}</td>
        </tr>"""
    
    # Fading sectors
    fade_rows = ""
    for sec in fading[:5]:
        fade_rows += f"""<tr>
            <td>{sec.name}</td>
            <td style="color:var(--g)">{sec.change_1d:+.2f}%</td>
            <td style="color:var(--g)">{sec.net_money_flow:.1f}亿</td>
            <td>{sec.bsi_score}</td>
        </tr>"""
    
    # Alerts
    alerts_html = "".join(f"<p style='color:var(--y);margin:4px 0'>⚠️ {a}</p>" for a in report.risk_alerts)
    
    # 主线切换检测
    switch_html = ""
    if len(report.strong_sectors) >= 2 and len(fading) >= 1:
        switch_html = f"<p style='color:var(--y)'>🔄 注意: {fading[0].name}正在退潮，{report.strong_sectors[0].name}可能成为新主线。关注切换信号。</p>"
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化日报 | {report.date}</title>
<style>
:root{{--bg:#0f1117;--cd:#1a1d28;--bd:#2a2d3a;--tx:#e4e6ed;--t2:#8b8fa3;--r:#f5222d;--g:#16c784;--a:#6366f1;--y:#f59e0b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--tx);line-height:1.6;padding:24px 16px 60px;max-width:600px;margin:0 auto}}
h1{{font-size:22px;color:var(--a);text-align:center;margin-bottom:4px}}
.sub{{color:var(--t2);font-size:11px;text-align:center;margin-bottom:20px}}
.verdict{{background:linear-gradient(135deg,rgba(99,102,241,0.2),rgba(245,158,11,0.1));border:1px solid var(--a);border-radius:12px;padding:16px 18px;margin-bottom:20px}}
.verdict .big{{font-size:20px;font-weight:700;color:var(--a);text-align:center;margin-bottom:10px}}
.verdict .line{{font-size:13px;padding:4px 0;border-bottom:1px solid var(--bd)}}
.verdict .line:last-child{{border-bottom:none}}
.sec{{margin-bottom:24px}}
.st{{font-size:15px;font-weight:700;margin-bottom:10px;padding-bottom:4px;border-bottom:2px solid var(--a)}}
.card{{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:14px;margin-bottom:10px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.stat{{text-align:center;padding:10px;background:rgba(99,102,241,0.06);border-radius:8px}}
.stat .v{{font-size:16px;font-weight:700;margin:4px 0}}.stat .l{{font-size:10px;color:var(--t2)}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#222531;padding:6px 8px;text-align:left;color:var(--t2);border-bottom:2px solid var(--bd)}}
td{{padding:5px 8px;border-bottom:1px solid var(--bd)}}tr:hover{{background:#222531}}
.sig{{border-left:3px solid;padding:10px 14px;background:var(--cd);border-radius:0 8px 8px 0;margin-bottom:8px;font-size:13px}}
.bull{{border-color:var(--r)}}.bear{{border-color:var(--g)}}.neut{{border-color:var(--y)}}
.footer{{margin-top:30px;text-align:center;font-size:10px;color:var(--t2);line-height:1.8}}
</style>
</head><body>
<h1>🧠 A股量化日报</h1><p class="sub">{report.date} · RTI 2.0 四引擎 · 资金迁移+轮动管线</p>

<!-- VERDICT -->
<div class="verdict">
  <div class="big">{report.phase} · 仓位{pos.get('position','?')}</div>
  <div class="line">📊 {q1}</div>
  <div class="line">🔄 {q2}</div>
  <div class="line">📉 {q3}</div>
</div>

<!-- 市场状态 -->
<div class="sec"><div class="st">🏛️ 市场状态</div>
<div class="card">
  <div class="grid4">
    <div class="stat"><div class="l">当前周期</div><div class="v">{report.phase}</div></div>
    <div class="stat"><div class="l">涨跌比</div><div class="v">{s.market_breadth:.0%}</div></div>
    <div class="stat"><div class="l">涨停</div><div class="v" style="color:var(--r)">{s.limit_up_count}</div></div>
    <div class="stat"><div class="l">风险</div><div class="v">{s.risk_level.upper()}</div></div>
  </div>
</div></div>

<!-- 板块轮动 RTI -->
<div class="sec"><div class="st">🔄 板块轮动 (RTI引擎)</div>
<div class="card">
  {rot_rows if rot_rows else '<p style="color:var(--t2);text-align:center;padding:12px">今日无RTI轮动信号<br><small>无低位+放量+无新闻驱动的板块异动</small></p>'}
  {f'<table><tr><th>板块</th><th>RTI</th><th>状态</th><th>理由</th></tr>{rot_rows}</table>' if rot_rows else ''}
</div></div>

<!-- 强势板块 BSI -->
<div class="sec"><div class="st">📈 强势板块 (BSI)</div>
<div class="card">
  {f'<table><tr><th>板块</th><th>BSI</th><th>涨跌</th><th>涨停</th><th>强度</th></tr>{strong_rows}</table>' if strong_rows else '<p style="color:var(--t2)">暂无BSI>30的强势板块</p>'}
</div></div>

<!-- 龙头 LS -->
<div class="sec"><div class="st">🏆 龙头股池 (LS)</div>
<div class="card">
  {f'<table><tr><th>代码</th><th>名称</th><th>LS</th><th>板块</th><th>涨跌</th><th>等级</th></tr>{leader_rows}</table>' if leader_rows else '<p style="color:var(--t2);text-align:center;padding:12px">暂无LS≥5的龙头/跟随股<br><small>需要板块内有个股突破前高+量比>2+涨幅领先</small></p>'}
</div></div>

<!-- 退潮板块 -->
<div class="sec"><div class="st">💨 退潮板块</div>
<div class="card">
  {f'<table><tr><th>板块</th><th>涨跌</th><th>资金流出</th><th>BSI</th></tr>{fade_rows}</table>' if fade_rows else '<p style="color:var(--t2)">无显著退潮板块</p>'}
</div></div>

<!-- 主线切换 -->
{"<div class='sec'><div class='st'>🔄 主线切换</div><div class='card'>"+switch_html+"</div></div>" if switch_html else ""}

<!-- 风险 -->
<div class="sec"><div class="st">⚠️ 风险提示</div>
<div class="card">{alerts_html or '<p style="color:var(--t2)">无显著风险</p>'}</div></div>

<!-- 策略 -->
<div class="sec"><div class="st">🎯 交易策略</div>
<div class="sig {'bull' if '80' in pos.get('position','') else ('neut' if '50' in pos.get('position','') else 'bear')}">
  <strong>{pos.get('strategy','—')}策略</strong><br>
  <span style="font-size:13px">仓位: {pos.get('position','—')} · {pos.get('action','')}</span><br>
  <span style="font-size:11px;color:var(--t2)">重点关注: {pos.get('focus','—')}</span>
</div></div>

<div class="footer">
  <p>🧠 RTI 2.0 / BSI / LS / Phase 量化引擎 · GitHub Actions 云端运行</p>
  <p>⚠️ 免责声明: AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。</p>
</div>
</body></html>"""


# 用于report模块级别的fading检测
def detect_fading_sectors(sectors: List[Sector]) -> List[Sector]:
    """检测退潮板块: BSI低 + 资金流出 + 涨幅为负"""
    fading = []
    for s in sectors:
        if s.bsi_score < 10 and s.net_money_flow < 0 and s.change_1d < 0:
            fading.append(s)
    return sorted(fading, key=lambda s: s.net_money_flow)[:5]

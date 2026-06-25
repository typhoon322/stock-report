"""
rotation/audit.py — 审计与自检引擎

每天生成两个文件:
  1. docs/audit_bundle.json   — 完整审计数据 (市场/板块/龙头/信号/回测追踪)
  2. docs/self_check_YYYYMMDD.json — 自检报告 (信号密度/滞後/过拟合风险)

闭环: 信号生成 → 审计记录 → 自检验证 → 人工复盘 → 参数优化
"""
import json, os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .models import Stock, Sector, MarketSentiment, DailyReport

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(ROOT, "docs")

# ─────────────────────────────────────────────
# 审计数据生成
# ─────────────────────────────────────────────

def generate_audit_bundle(report: DailyReport) -> Dict:
    """
    生成审计包
    
    包含:
      1. 市场状态 (market_state)
      2. 板块数据 (sectors_top)
      3. 龙头数据 (leaders)
      4. 信号记录 (signals)
      5. 历史表现追踪 (performance_track, 如果有历史audit)
    """
    s = report.sentiment
    today = report.date
    
    bundle = {
        "version": "3.0",
        "generated_at": datetime.now().isoformat(),
        "date": today,
        "market_state": {
            "date": today,
            "market_phase": report.phase,
            "risk_level": s.risk_level,
            "index_trend": "震荡偏强" if s.market_breadth > 0.5 else ("震荡偏弱" if s.market_breadth > 0.35 else "偏弱"),
            "advance_decline_ratio": s.up_down_ratio,
            "limit_up_count": s.limit_up_count,
            "fall_limit_count": s.fall_limit_count,
            "market_breadth": s.market_breadth,
        },
        "sectors_top": [],
        "leaders": [],
        "rotation_signals": [],
        "performance_track": [],
        "strategy": {
            "position": report.strategy.get("position", "?"),
            "action": report.strategy.get("action", "?"),
            "focus": report.strategy.get("focus", "?"),
        },
    }
    
    # 板块数据 (BSI + RTI)
    for sec in report.strong_sectors[:8]:
        bundle["sectors_top"].append({
            "sector": sec.name,
            "BSI": sec.bsi_score,
            "change_1d": round(sec.change_1d, 2),
            "net_money_flow": sec.net_money_flow,
            "num_limit_up": sec.num_limit_up,
            "num_stocks_up": sec.num_stocks_up,
            "status": "强势板块" if sec.bsi_score > 30 else "中等轮动",
        })
    
    # 轮动信号
    for sig in report.rotation_signals:
        bundle["rotation_signals"].append({
            "date": today,
            "sector": sig.sector.name,
            "RTI": sig.rti_score,
            "BSI": sig.sector.bsi_score,
            "signal_type": "rotation_entry" if sig.rti_score >= 3 else "scanning",
            "status": sig.status,
            "reason": sig.reason[:120],
        })
    
    # 龙头数据
    for ldr in report.leaders:
        bundle["leaders"].append({
            "sector": getattr(ldr, 'industry', ''),
            "stock": ldr.code,
            "name": ldr.name,
            "LS": ldr.leader_score,
            "change_pct": round(ldr.change_pct, 2),
            "volume_ratio": round(ldr.volume_ratio, 2),
            "entry_signal": ldr.leader_score >= 7,
            "is_leader": ldr.leader_score >= 7,
        })
    
    # 历史表现追踪: 加载旧audit, 计算之前信号的后续收益
    perf_track = _compute_performance_track(bundle)
    bundle["performance_track"] = perf_track
    
    return bundle


def _compute_performance_track(current: Dict) -> List[Dict]:
    """从历史audit计算信号后续收益"""
    # 加载前几天的audit
    tracks = []
    for days_back in [5, 10, 20]:
        prev_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        prev_path = os.path.join(AUDIT_DIR, f"audit_{prev_date}.json")
        if os.path.exists(prev_path):
            try:
                with open(prev_path) as f:
                    prev = json.load(f)
                for sig in prev.get("rotation_signals", []):
                    # 查找该板块在当天数据中的涨幅
                    for sec in current.get("sectors_top", []):
                        if sec["sector"] == sig["sector"]:
                            tracks.append({
                                "signal_date": sig["date"],
                                "sector": sig["sector"],
                                "signal_rti": sig["RTI"],
                                "return_since": sec["change_1d"],
                                "days_elapsed": days_back,
                                "benchmark_return": 0,  # TODO: 沪深300同期
                            })
            except: pass
    
    return tracks[:20]  # 最多20条


def save_audit_bundle(bundle: Dict):
    """保存审计文件 (每日版本 + 最新版)"""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    
    date = bundle["date"]
    
    # 每日版本
    daily_path = os.path.join(AUDIT_DIR, f"audit_{date}.json")
    with open(daily_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, default=str, indent=2)
    
    # 最新版本 (方便外部读取)
    latest_path = os.path.join(AUDIT_DIR, "audit_bundle.json")
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, default=str, indent=2)
    
    print(f"  ✅ audit_{date}.json + audit_bundle.json")
    return daily_path


# ─────────────────────────────────────────────
# 自检模块
# ─────────────────────────────────────────────

def generate_self_check(bundle: Dict) -> Dict:
    """
    系统自检
    
    检查项:
      1. RTI有效性 — 信号是否过于集中在某个区间
      2. 信号密度 — 是否信号过多(噪音)或过少(不灵敏)
      3. 滞后风险 — 龙头是否"已经涨完"
      4. 过拟合风险 — 信号成功率是否异常高(>90%→可能过拟合)
    """
    signals = bundle.get("rotation_signals", [])
    leaders = bundle.get("leaders", [])
    market = bundle.get("market_state", {})
    
    check = {
        "date": bundle["date"],
        "generated_at": datetime.now().isoformat(),
        "checks": {},
    }
    
    # 1. RTI有效性
    if not signals:
        check["checks"]["RTI_validity"] = "PASS (无信号日, 退潮/冰点期正常)"
    else:
        rti_scores = [s.get("RTI", 0) for s in signals]
        avg_rti = sum(rti_scores) / len(rti_scores) if rti_scores else 0
        high_count = sum(1 for r in rti_scores if r >= 4.5)
        if avg_rti > 4 and high_count > len(signals) * 0.5:
            check["checks"]["RTI_validity"] = "WARN — 信号评分偏高, 可能阈值过低"
        elif avg_rti < 2:
            check["checks"]["RTI_validity"] = "WARN — 信号评分偏低, 阈值可能过高"
        else:
            check["checks"]["RTI_validity"] = "PASS"
    
    # 2. 信号密度
    total_sectors = len(bundle.get("sectors_top", []))
    signal_ratio = len(signals) / max(total_sectors, 1)
    if signal_ratio > 0.5:
        check["checks"]["signal_density"] = "too_high — 超过50%板块有信号, 噪音"
    elif signal_ratio == 0:
        check["checks"]["signal_density"] = "normal — 退潮期无信号"
    elif signal_ratio < 0.1:
        check["checks"]["signal_density"] = "too_low — 信号稀疏, 可能不灵敏"
    else:
        check["checks"]["signal_density"] = "normal"
    
    # 3. 假信号率估算
    # 简化: 如果龙头LS<5 但 RTI≥3 → 假信号
    leader_stocks = {l["stock"] for l in leaders if l.get("is_leader")}
    false_count = 0
    for sig in signals:
        sector = sig.get("sector", "")
        has_leader = any(l.get("sector") == sector for l in leaders if l.get("is_leader"))
        if sig.get("RTI", 0) >= 3 and not has_leader:
            false_count += 1
    
    false_rate = false_count / max(len(signals), 1)
    check["checks"]["false_signal_rate_estimate"] = round(false_rate, 2)
    
    # 4. 龙头滞后风险
    # 龙头涨幅>9.5% (已涨停) → 可能已经涨完
    late_leaders = sum(1 for l in leaders if l.get("change_pct", 0) >= 9.5)
    if late_leaders > len(leaders) * 0.5 and len(leaders) > 0:
        check["checks"]["leader_delay_risk"] = "high — 多数龙头已涨停, 可能滞后"
    elif late_leaders > 0:
        check["checks"]["leader_delay_risk"] = "medium"
    else:
        check["checks"]["leader_delay_risk"] = "low"
    
    # 5. 过拟合风险
    # 如果历史信号成功率>90% → 可能过拟合
    perf = bundle.get("performance_track", [])
    if perf:
        wins = sum(1 for p in perf if p.get("return_since", 0) > 0)
        win_rate = wins / max(len(perf), 1)
        if win_rate > 0.9:
            check["checks"]["overfitting_risk"] = "high — 历史胜率>90%, 可能过拟合"
        elif win_rate > 0.7:
            check["checks"]["overfitting_risk"] = "medium"
        else:
            check["checks"]["overfitting_risk"] = "low"
    else:
        check["checks"]["overfitting_risk"] = "low (数据不足)"
    
    # 汇总
    warn_count = sum(1 for v in check["checks"].values() if "WARN" in str(v) or "high" in str(v) or "too_high" in str(v))
    check["summary"] = {
        "total_checks": len(check["checks"]),
        "warnings": warn_count,
        "overall": "PASS" if warn_count == 0 else ("WARN" if warn_count <= 2 else "FAIL"),
    }
    
    return check


def save_self_check(check: Dict):
    """保存自检报告"""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    date = check["date"]
    
    path = os.path.join(AUDIT_DIR, f"self_check_{date}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(check, f, ensure_ascii=False, default=str, indent=2)
    
    # 简化摘要打印
    summary = check.get("summary", {})
    checks = check.get("checks", {})
    print(f"  ✅ self_check_{date}.json")
    print(f"     总体: {summary.get('overall','?')} | 警告: {summary.get('warnings',0)}/{summary.get('total_checks',0)}")
    for k, v in checks.items():
        icon = "✅" if "PASS" in str(v) else "⚠️"
        print(f"     {icon} {k}: {v}")


def run_audit_and_check(report: DailyReport):
    """一站式: 生成审计 + 自检"""
    print("\n📋 审计与自检...")
    bundle = generate_audit_bundle(report)
    save_audit_bundle(bundle)
    check = generate_self_check(bundle)
    save_self_check(check)
    return bundle, check

"""
Shadow Trade Log — 模拟交易记录（含滑点+执行模拟）
"""
import json, os
from datetime import datetime, timezone, timedelta


def _now_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _today_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y%m%d")


def save_shadow_trades(
    meta_result: dict = None,
    position_result: dict = None,
    execution_result: dict = None,
    portfolio: list = None,
) -> str:
    """保存影子交易日志
    
    模拟从 Meta Score → Position Sizing → Execution 的完整交易链路
    """
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    trades = {
        "timestamp": _now_str(),
        "date": today,
        "status": "shadow",  # 标记为模拟交易
        "pipeline": {},
    }
    
    # Meta
    if meta_result:
        trades["pipeline"]["meta"] = {
            "decision": meta_result.get("decision", "HOLD"),
            "score": meta_result.get("score", 0),
            "confidence": meta_result.get("confidence", 0),
        }
    
    # Position
    if position_result:
        trades["pipeline"]["position"] = {
            "direction": position_result.get("direction"),
            "size": position_result.get("position_size"),
            "level": position_result.get("position_level"),
        }
    
    # Execution
    if execution_result:
        trades["pipeline"]["execution"] = {
            "slippage": execution_result.get("slippage", {}).get("estimated_slippage_pct"),
            "realized_position": execution_result.get("realized_position"),
            "impact_cost": execution_result.get("impact", {}).get("impact_cost_pct"),
        }
    
    # Portfolio
    if portfolio:
        if isinstance(portfolio, list):
            trades["portfolio"] = [
                {"code": p.get("code","") if isinstance(p, dict) else str(p), 
                 "name": p.get("name","") if isinstance(p, dict) else "",
                 "focus": p.get("focus", False) if isinstance(p, dict) else False}
                for p in portfolio[:10]
            ]
        elif isinstance(portfolio, dict):
            trades["portfolio"] = [
                {"code": k, "name": v.get("name",""), "focus": v.get("focus", False)}
                for k, v in portfolio.items()
            ][:10]
    
    # Simulated PnL placeholder (to be backfilled in Phase II)
    trades["simulated_pnl"] = {
        "entry_price": None,
        "exit_price": None,
        "pnl_pct": None,
        "note": "Phase I shadow only — real PnL backfilled in Phase II",
    }
    
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "rotation", "shadow", "trades", f"shadow_trades_{_today_str()}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2, default=str)
    
    return path

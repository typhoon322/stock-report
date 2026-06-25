"""
rotation/execution/execution_engine.py — 主执行引擎 + 报告

完整管线: 信号 → 流动性检查 → 拆单 → 滑点估算 → 真实成本
"""
from typing import Dict
from .liquidity_estimator import estimate_liquidity
from .slippage_model import estimate_slippage
from .order_sizer import split_orders


def simulate_execution(
    direction: str,
    position_size: float,
    daily_volume: float = 5.0,
    turnover_rate: float = 3.0,
    volatility: float = 0.02,
    market_cap: float = 100,
    spread_pct: float = 0.001,
) -> Dict:
    """
    主入口: 模拟一笔交易的真实执行
    
    Args:
        direction: LONG / HOLD / SHORT
        position_size: 仓位比例 (0-1)
        daily_volume: 日成交额 (亿)
        turnover_rate: 换手率 (%)
        volatility: 波动率
        market_cap: 市值 (亿)
    """
    if direction == "HOLD" or position_size <= 0:
        return {
            "direction": "HOLD",
            "executed": False,
            "reason": "no_trade_signal",
        }
    
    # Step 1: 流动性
    liquidity = estimate_liquidity(daily_volume, turnover_rate, volatility, market_cap)
    
    # Step 2: 拆单
    orders = split_orders(position_size, liquidity["classification"], liquidity["max_single_order_pct"])
    
    # Step 3: 滑点
    slippage = estimate_slippage(
        volatility, position_size, liquidity["liquidity_score"],
        orders["execution_style"], spread_pct,
    )
    
    # Step 4: 真实成本 → 收益影响
    expected_return_drag = slippage["estimated_slippage_pct"] / 100  # to decimal
    realized_position = position_size * (1 - expected_return_drag)
    
    return {
        "direction": direction,
        "executed": True,
        "position_size": position_size,
        "realized_position": round(realized_position, 4),
        "expected_cost_pct": round(expected_return_drag * 100, 3),
        "liquidity": liquidity,
        "orders": orders,
        "slippage": slippage,
        "execution_risk": "low" if slippage["severity"] == "low" else ("medium" if slippage["severity"] == "medium" else "high"),
    }


def get_execution_report(result: Dict) -> str:
    """生成执行报告"""
    if not result.get("executed"):
        return f"# 📋 Execution Report\n\n## Status\n👉 HOLD — no trade\n\n**Reason**: {result.get('reason', 'N/A')}"
    
    liq = result.get("liquidity", {})
    orders = result.get("orders", {})
    slip = result.get("slippage", {})
    
    lines = [
        f"# 📋 Execution Report",
        f"",
        f"## Intended Position",
        f"👉 **{result['direction']}** | {result['position_size']:.0%}",
        f"",
        f"## Liquidity",
        f"- Score: {liq.get('liquidity_score', 0):.2f} ({liq.get('classification', '?')})",
        f"- Method: {liq.get('recommended_method', '?')}",
        f"",
        f"## Order Split",
        f"- Style: {orders.get('execution_style', '?')} ({orders.get('total_orders', 0)} batches)",
        f"- Duration: {orders.get('expected_duration', '?')}",
        f"",
        f"## Slippage Estimate",
        f"👉 **{slip.get('estimated_slippage_pct', 0):.3f}%** ({slip.get('severity', '?')})",
        f"- Base: {slip.get('base_slippage', 0):.3f}% | Impact: {slip.get('impact_cost', 0):.3f}% | Spread: {slip.get('spread_cost', 0):.3f}%",
        f"",
        f"## Realized Cost",
        f"👉 Expected return drag: **{result.get('expected_cost_pct', 0):.3f}%**",
        f"👉 Realized position: **{result.get('realized_position', 0):.1%}** (from {result['position_size']:.0%})",
        f"",
        f"## Execution Risk",
        f"👉 **{result.get('execution_risk', '?')}**",
    ]
    
    return "\n".join(lines)

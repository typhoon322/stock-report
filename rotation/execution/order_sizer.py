"""
rotation/execution/order_sizer.py — 分批拆单

根据流动性将仓位拆分为多笔订单
"""
from typing import Dict, List


def split_orders(
    position_size: float,
    liquidity_class: str,       # high / medium / low
    max_single_pct: float = 0.15,
) -> Dict:
    """
    将仓位拆分为执行批次
    
    Returns: list of orders + summary
    """
    remaining = position_size
    orders = []
    
    if liquidity_class == "high":
        # 直接市价成交
        orders.append({"type": "market", "pct": min(remaining, max_single_pct)})
        remaining -= orders[-1]["pct"]
    
    elif liquidity_class == "medium":
        # TWAP: 分3-5笔
        n_batches = 4
        batch_size = min(position_size / n_batches, max_single_pct)
        for i in range(n_batches):
            if remaining <= 0:
                break
            size = min(batch_size, remaining)
            orders.append({"type": "TWAP", "batch": i+1, "pct": round(size, 4)})
            remaining -= size
    
    elif liquidity_class == "low":
        # VWAP + limit: 更小批次
        n_batches = 8
        batch_size = min(position_size / n_batches, max_single_pct)
        for i in range(n_batches):
            if remaining <= 0:
                break
            size = min(batch_size, remaining)
            orders.append({"type": "limit", "batch": i+1, "pct": round(size, 4)})
            remaining -= size
    
    # 如果有剩余，加一笔
    if remaining > 0.001:
        orders.append({"type": "limit", "batch": "final", "pct": round(remaining, 4)})
    
    return {
        "total_orders": len(orders),
        "orders": orders,
        "execution_style": "single" if len(orders) == 1 else ("TWAP" if len(orders) <= 5 else "VWAP_limit"),
        "expected_duration": f"{len(orders) * 15} min" if len(orders) > 1 else "instant",
    }

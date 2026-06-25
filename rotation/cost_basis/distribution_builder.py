"""
rotation/cost_basis/distribution_builder.py — Volume Profile / 成交分布重建

把价格分桶 → 统计每个区间的成交量 → 形成"成交量山峰"
"""
from typing import Dict, List, Tuple
import numpy as np


def build_volume_profile(
    prices: List[float],       # 收盘价序列 (N天)
    volumes: List[float],      # 成交量序列
    highs: List[float] = None,
    lows: List[float] = None,
    n_bins: int = 20,
) -> Dict:
    """
    构建成交量分布 (Volume Profile)
    
    核心算法: 价格分桶 → 每桶累加成交量 → 识别密集区
    
    Returns:
        {
            "bins": [{"price_low": x, "price_high": y, "volume": v, "density": d}, ...],
            "price_range": [min, max],
            "max_density_zone": {...},   # 最密集区间
            "current_price_zone": {...}, # 当前价格所在区间
            "weighted_avg_cost": float,   # 加权平均成本
        }
    """
    n = len(prices)
    if n < 5:
        return _empty_profile()
    
    prices = np.array(prices)
    volumes = np.array(volumes)
    
    # 确定价格范围
    if highs and lows:
        p_min = float(np.min(lows))
        p_max = float(np.max(highs))
    else:
        p_min = float(np.min(prices))
        p_max = float(np.max(prices))
    
    price_range = p_max - p_min
    if price_range == 0:
        price_range = p_min * 0.05 or 0.1
    
    # 分桶
    bin_width = price_range / n_bins
    bins = []
    
    for i in range(n_bins):
        bin_low = round(p_min + i * bin_width, 2)
        bin_high = round(p_min + (i + 1) * bin_width, 2)
        
        # 统计此区间总成交量
        bin_vol = 0.0
        for j in range(n):
            p = prices[j]
            if bin_low <= p < bin_high or (i == n_bins - 1 and bin_low <= p <= bin_high):
                bin_vol += volumes[j]
        
        density = round(bin_vol / max(sum(volumes), 1), 4)
        
        bins.append({
            "index": i,
            "price_low": bin_low,
            "price_high": bin_high,
            "mid_price": round((bin_low + bin_high) / 2, 2),
            "volume": round(bin_vol, 2),
            "density": density,
        })
    
    # 找到最密集区间
    max_bin = max(bins, key=lambda b: b["density"])
    
    # 当前价格所在区间
    current_price = float(prices[-1])
    current_bin = None
    for b in bins:
        if b["price_low"] <= current_price <= b["price_high"]:
            current_bin = b
            break
    if not current_bin:
        current_bin = bins[-1] if current_price > p_max else bins[0]
    
    # 加权平均成本 (VWAP)
    total_vol = sum(volumes)
    vwap = sum(prices[i] * volumes[i] for i in range(n)) / max(total_vol, 1)
    
    # 识别密集区: density > 均值*1.5
    avg_density = sum(b["density"] for b in bins) / n_bins
    dense_zones = [b for b in bins if b["density"] > avg_density * 1.5]
    
    return {
        "bins": bins,
        "price_range": [round(p_min, 2), round(p_max, 2)],
        "n_bins": n_bins,
        "max_density_zone": max_bin,
        "dense_zones": dense_zones,
        "current_price_zone": current_bin,
        "current_price": round(current_price, 2),
        "weighted_avg_cost": round(vwap, 2),
        "total_volume": round(total_vol, 2),
    }


def find_cost_concentration(profile: Dict) -> Dict:
    """从 Volume Profile 找筹码集中价格带"""
    bins = profile.get("bins", [])
    if not bins:
        return {"zone": None, "support": None, "resistance": None}
    
    sorted_by_density = sorted(bins, key=lambda b: b["density"], reverse=True)
    current_idx = profile["current_price_zone"]["index"]
    
    # 主力成本区: density top 30% + 在当前价附近
    top30 = sorted_by_density[:max(1, len(bins) // 3)]
    
    # 支撑: 当前价下方最密集的区间
    below = [b for b in bins if b["index"] < current_idx]
    support = max(below, key=lambda b: b["density"]) if below else None
    
    # 阻力: 当前价上方最密集的区间
    above = [b for b in bins if b["index"] > current_idx]
    resistance = max(above, key=lambda b: b["density"]) if above else None
    
    return {
        "cost_dense_zone": {
            "low": round(min(b["price_low"] for b in top30), 2),
            "high": round(max(b["price_high"] for b in top30), 2),
            "total_density": round(sum(b["density"] for b in top30), 3),
        },
        "support": support,
        "resistance": resistance,
    }


def _empty_profile() -> Dict:
    return {
        "bins": [], "price_range": [0, 0], "n_bins": 0,
        "max_density_zone": {}, "dense_zones": [],
        "current_price_zone": {}, "current_price": 0,
        "weighted_avg_cost": 0, "total_volume": 0,
    }

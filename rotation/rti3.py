"""
rotation/rti3.py — RTI v3 加权轮动模型

RTI = w1*FlowShift + w2*Acceleration + w3*LowBaseBreakout 
    + w4*SectorExpansion + w5*NewsDecoupling + w6*OldSectorDecay

默认权重: [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
"""
from typing import List, Dict, Tuple

# 默认权重 (可通过优化器调整)
DEFAULT_WEIGHTS = {
    "w1_flow_shift": 0.25,
    "w2_acceleration": 0.20,
    "w3_low_base": 0.20,
    "w4_expansion": 0.15,
    "w5_news_decouple": 0.10,
    "w6_old_decay": 0.10,
}

# 阈值
RTI_THRESHOLD_MAINLINE = 4.5
RTI_THRESHOLD_PROBING = 3.0


def normalize(v: float, vmin: float = 0, vmax: float = 10) -> float:
    """归一化到 0-10 区间"""
    if vmax == vmin:
        return 5.0
    return max(0, min(10, (v - vmin) / (vmax - vmin) * 10))


def compute_flow_shift(
    sector_flow: float,
    old_leader_flows: List[float],
) -> float:
    """
    资金迁移强度 (0-10)
    
    FlowShift = (新板块流入 + 旧主线流出绝对值) / max(总流动, 1)
    """
    old_outflow = abs(sum(f for f in old_leader_flows if f < 0))
    total_movement = sector_flow + old_outflow
    if total_movement <= 0:
        return 0
    return normalize(total_movement / 1e8, 0, 20)


def compute_acceleration(
    today_flow: float,
    yesterday_flow: float,
) -> float:
    """资金加速度 (0-10)"""
    accel = today_flow - yesterday_flow
    return normalize(accel / 1e8, -5, 10)


def compute_low_base_breakout(
    change_1d: float,
    change_5d: float,
    market_avg: float,
    has_news: bool,
) -> float:
    """低位突破 + 无新闻解耦 (0-10)"""
    score = 0
    
    # 低位: 5日涨幅 < 大盘
    if change_5d < market_avg and change_1d > 1.5:
        score += 5
    elif change_5d < 0 and change_1d > 0:
        score += 3
    
    # 无新闻驱动
    if not has_news:
        score += 5
    
    return score


def compute_sector_expansion(
    num_up: int,
    num_limit: int,
    total_stocks: int,
) -> float:
    """板块扩散能力 (0-10)"""
    if total_stocks == 0:
        return 0
    up_ratio = num_up / total_stocks
    score = up_ratio * 6  # 上涨比例
    score += min(num_limit, 5) * 0.8  # 涨停加分
    return min(10, score)


def compute_old_sector_decay(
    old_chg: float,
    old_vol_ratio: float,
    old_limit_count: int,
) -> float:
    """旧主线衰减 (0-10)"""
    score = 0
    
    # 龙头滞涨
    if old_chg < 0:
        score += 4
    elif old_chg < 1:
        score += 2
    
    # 量能萎缩
    if old_vol_ratio < 0.8:
        score += 3
    elif old_vol_ratio < 1.0:
        score += 1
    
    # 涨停断档
    if old_limit_count == 0:
        score += 3
    
    return min(10, score)


def compute_rti3(
    # 新板块数据
    sector_flow: float,
    change_1d: float,
    change_5d: float,
    num_up: int,
    num_limit: int,
    total_stocks: int,
    has_news: bool,
    prev_day_flow: float = 0,
    # 旧主线数据
    old_leader_flows: List[float] = None,
    old_chg: float = 0,
    old_vol_ratio: float = 1.0,
    old_limit_count: int = 0,
    # 市场基准
    market_avg: float = 0,
    # 权重
    weights: Dict[str, float] = None,
) -> Tuple[float, str, Dict[str, float]]:
    """
    RTI v3 加权评分
    
    Returns: (rti_score, signal_type, component_scores)
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    if old_leader_flows is None:
        old_leader_flows = []
    
    scores = {}
    
    # 各组件评分
    scores["flow_shift"] = compute_flow_shift(sector_flow, old_leader_flows)
    scores["acceleration"] = compute_acceleration(sector_flow, prev_day_flow)
    scores["low_base"] = compute_low_base_breakout(change_1d, change_5d, market_avg, has_news)
    scores["expansion"] = compute_sector_expansion(num_up, num_limit, total_stocks)
    scores["news_decouple"] = 10.0 if not has_news else 2.0
    scores["old_decay"] = compute_old_sector_decay(old_chg, old_vol_ratio, old_limit_count)
    
    # 加权求和
    rti = (
        scores["flow_shift"] * weights["w1_flow_shift"] +
        scores["acceleration"] * weights["w2_acceleration"] +
        scores["low_base"] * weights["w3_low_base"] +
        scores["expansion"] * weights["w4_expansion"] +
        scores["news_decouple"] * weights["w5_news_decouple"] +
        scores["old_decay"] * weights["w6_old_decay"]
    )
    
    # 判定
    if rti >= RTI_THRESHOLD_MAINLINE:
        signal = "new_mainline"
    elif rti >= RTI_THRESHOLD_PROBING:
        signal = "rotation_probing"
    else:
        signal = "no_rotation"
    
    return round(rti, 2), signal, scores

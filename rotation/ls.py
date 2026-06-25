"""
rotation/ls.py — Leader Score (龙头识别模型)

永远不推荐后排股。找板块内最强个股。
"""
from .models import Stock
from typing import List

def compute_leader_score(stock: Stock, all_stocks_in_sector: List[Stock]) -> int:
    """
    计算龙头评分 LS
    
    公式:
    LS = Σ(最早启动 + 突破前高 + 放量上涨 + 板块第一 + 资金集中)
    
    Returns: LS score (0-8)
    """
    score = 0
    
    # 1. 板块内最早启动 (0-2分)
    # 判断标准: 前3日涨幅是否在板块内领先
    if stock.is_early_starter:
        score += 2
    
    # 2. 突破前高 (0-2分)
    if stock.is_breakout:
        score += 2
    
    # 3. 放量上涨 (0-1分)
    if stock.volume_ratio > 2.0 and stock.change_pct > 0:
        score += 1
    
    # 4. 板块内涨幅第一 (0-2分)
    if all_stocks_in_sector:
        max_chg = max(s.change_pct for s in all_stocks_in_sector)
        if stock.change_pct >= max_chg * 0.95:  # 接近第一也算
            score += 2
    
    # 5. 资金流入集中度 (0-1分)
    if all_stocks_in_sector:
        total_flow = sum(abs(s.money_flow) for s in all_stocks_in_sector)
        if total_flow > 0 and abs(stock.money_flow) / total_flow > 0.15:
            score += 1  # 该股吸引超过15%的板块资金
    
    return score


def classify_leader(score: int) -> str:
    """LS评分 → 状态分类"""
    if score > 7:
        return "🏆 龙头"
    elif score >= 5:
        return "📈 跟随"
    else:
        return "⚪ 后排"


def find_leaders(stocks: List[Stock], min_score: int = 5) -> List[Stock]:
    """找出板块内所有龙头/跟随股(LS ≥ min_score)"""
    for s in stocks:
        s.leader_score = compute_leader_score(s, stocks)
    
    leaders = [s for s in stocks if s.leader_score >= min_score]
    return sorted(leaders, key=lambda s: (s.leader_score, s.change_pct), reverse=True)


def find_sector_leader(stocks: List[Stock]) -> Stock | None:
    """找出板块内最强龙头"""
    leaders = find_leaders(stocks, min_score=7)
    if leaders:
        return leaders[0]
    # 如果没有龙头(LS≥7)，退而找跟随(LS≥5)
    followers = find_leaders(stocks, min_score=5)
    return followers[0] if followers else None

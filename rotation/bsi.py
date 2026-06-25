"""
rotation/bsi.py — Board Strength Index (板块强度评分)

量化板块的强弱程度，用多维加权评分替代单纯的涨幅排序
"""
from .models import Sector
from typing import List
import math

def compute_bsi(sector: Sector, all_sectors: List[Sector]) -> int:
    """
    计算板块强度评分 BSI
    
    公式:
    BSI = percentile_rank(涨幅) * 20 
        + min(涨停数, 5) * 3
        + clamp(量变化, 0.5, 3.0) * 5
        + clamp(资金流入量级, 0, 10) * 2
        + 连续强度加分
    
    Returns: BSI score (0-100)
    """
    score = 0.0
    
    # 1. 涨幅排名权重 (0-20分)
    all_changes = [s.change_1d for s in all_sectors if s.change_1d is not None]
    if all_changes:
        rank = sum(1 for c in all_changes if c < sector.change_1d)
        percentile = rank / len(all_changes) * 100
        score += (percentile / 100) * 20
    
    # 2. 涨停数量 (0-15分, 每只3分, 封顶5只)
    score += min(sector.num_limit_up, 5) * 3
    
    # 3. 成交量变化 (0-15分, clamp 0.5~3.0)
    vol_factor = max(0.5, min(sector.volume_change, 3.0))
    score += vol_factor * 5
    
    # 4. 主力资金流入 (0-20分, 量级评分)
    if sector.net_money_flow > 0:
        # 亿级资金流
        flow_magnitude = min(abs(sector.net_money_flow) / 1e8, 10)
        score += flow_magnitude * 2
    
    # 5. 连续3日强度加分 (0-5分)
    if sector.change_3d > 0 and sector.change_3d > sector.change_5d:
        # 3日趋势在加速 → 持续强化
        score += 5
    elif sector.change_3d > 0:
        score += 2
    
    return min(int(score), 100)


def classify_bsi(score: int) -> str:
    """BSI分数 → 状态分类"""
    if score > 30:
        return "🔥 强势板块"
    elif score >= 15:
        return "🟡 中等轮动"
    else:
        return "⚪ 弱势"


def rank_sectors(sectors: List[Sector]) -> List[Sector]:
    """计算所有板块的BSI并降序排列"""
    for s in sectors:
        s.bsi_score = compute_bsi(s, sectors)
    return sorted(sectors, key=lambda s: s.bsi_score, reverse=True)

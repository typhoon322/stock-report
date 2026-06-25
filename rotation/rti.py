"""
rotation/rti.py — Rotation Timing Indicator (板块轮动识别引擎)

核心逻辑: 识别"资金正在切换的新方向"，不是热门板块
公式: RTI = Σ(低位异动 + 放量 + 首次异动 + 无新闻 + 涨停)
"""
from .models import Sector, RotationSignal
from typing import List, Dict
import math

def compute_rti(
    sector: Sector,
    market_avg_chg_5d: float,
    news_keywords: Dict[str, List[str]],
) -> RotationSignal:
    """
    计算板块轮动评分 RTI
    
    Args:
        sector: 板块数据
        market_avg_chg_5d: 大盘5日均涨幅(参考基准)
        news_keywords: 各板块的关联新闻关键词 {sector_name: [keywords]}
    
    Returns:
        RotationSignal with RTI score and status
    """
    score = 0
    reasons = []
    
    # 1. 低位板块 + 今日涨幅突然上升 (权重1)
    if sector.is_low_position and sector.change_1d > 2.0:
        score += 1
        reasons.append(f"低位异动: 5日涨幅{sector.change_5d:.1f}%低于大盘{market_avg_chg_5d:.1f}%, 今日突然涨{sector.change_1d:.1f}%")
    elif sector.is_low_position and sector.change_1d > 1.0 and sector.change_1d > sector.change_5d:
        score += 1
        reasons.append(f"低位转强: 今日{sector.change_1d:.1f}% > 5日均{sector.change_5d:.1f}%")
    
    # 2. 成交量放大 > 1.5倍均值 (权重1)
    if sector.volume_change > 1.5:
        score += 1
        reasons.append(f"放量: 成交量{sector.volume_change:.1f}x均值")
    elif sector.volume_change > 1.3 and sector.change_1d > 1.0:
        score += 1
        reasons.append(f"温和放量: {sector.volume_change:.1f}x + 涨{sector.change_1d:.1f}%")
    
    # 3. 板块内首次异动个股数量 ≥ 3 (权重1)
    # 首次异动 = 量比>2 且 5日前无明显涨幅
    early_movers = sum(
        1 for s in sector.stocks 
        if s.volume_ratio > 2.0 and s.is_early_starter
    )
    if early_movers >= 3:
        score += 1
        reasons.append(f"首次异动: {early_movers}只个股首次放量启动")
    elif early_movers >= 1:
        score += 0.5  # 部分启动
        reasons.append(f"个别异动: {early_movers}只首次放量")
    
    # 4. 无明显新闻驱动 (权重1) — 这是核心！
    related_news = news_keywords.get(sector.name, [])
    if not related_news:
        score += 1
        reasons.append("无新闻驱动: 自然资金迁移(轮动信号)")
    else:
        reasons.append(f"有新闻驱动: {', '.join(related_news[:3])} (可能短期炒作)")
    
    # 5. 板块内有涨停股 ≥ 1 (权重1)
    if sector.num_limit_up >= 1:
        score += 1
        reasons.append(f"涨停确认: {sector.num_limit_up}只涨停")
    elif sector.num_stocks_up > sector.num_stocks_up * 0.6:
        score += 0.5
    
    # Round to integer
    score = round(score)
    
    # 判定
    if score >= 4:
        status = "🔥 潜在新主线"
    elif score >= 3:
        status = "🟡 轮动试探"
    else:
        status = "⚪ 无轮动"
    
    return RotationSignal(
        sector=sector,
        rti_score=score,
        status=status,
        reason=" | ".join(reasons) if reasons else "未触发轮动条件",
    )


def rank_rotation_signals(signals: List[RotationSignal]) -> List[RotationSignal]:
    """按RTI降序排列，只返回有轮动信号的(≥3)"""
    filtered = [s for s in signals if s.rti_score >= 3]
    return sorted(filtered, key=lambda x: x.rti_score, reverse=True)


def detect_news_drivers(
    sector_name: str, 
    news_titles: List[str]
) -> List[str]:
    """检测板块是否有新闻驱动
    
    关键词匹配策略:
    - 高确定性驱动词: 政策/发布/获批/签约
    - 中等驱动词: 突破/创新/合作
    - 弱驱动词: 看好/预计/或将 (不纳入)
    """
    strong_kw = ["政策", "发布", "获批", "签约", "投资", "补贴", "重组"]
    mid_kw = ["突破", "创新", "合作", "扩产", "涨价"]
    
    sector_kw = sector_name.split()  # 板块名分词
    drivers = []
    
    for title in news_titles:
        if any(kw in title for kw in sector_kw):
            for kw in strong_kw + mid_kw:
                if kw in title:
                    drivers.append(title[:80])
                    break
    
    return drivers[:5]  # 最多5条

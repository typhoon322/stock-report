"""
rotation/audit_builder.py — 训练数据构建器

把历史每天的板块状态变成训练样本 (滑窗法: t日特征 → t+1~t+3日label)

数据结构: AuditBundle (9 features + 1 label)
Label逻辑: 板块未来3天是否成为主线 (涨幅Top10% OR ≥2龙头涨停 OR 资金Top5连续2天)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json, os, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class AuditBundle:
    """单个训练样本"""
    date: str
    sector: str

    # 特征 (X)
    change_1d: float = 0.0
    change_3d: float = 0.0
    change_5d: float = 0.0
    volume_change: float = 1.0
    num_stocks_up: int = 0
    num_limit_up: int = 0
    net_money_flow: float = 0.0
    has_news_driver: int = 0       # 0/1
    low_position: int = 0          # 0/1
    early_starters: int = 0        # 异动个股数

    # 标签 (y) — 从未来3天数据计算
    becomes_main_theme_3d: int = 0

    def to_feature_vector(self) -> List[float]:
        return [
            self.change_1d,
            self.change_3d,
            self.change_5d,
            self.volume_change,
            float(self.num_stocks_up),
            float(self.num_limit_up),
            self.net_money_flow,
            float(self.has_news_driver),
            float(self.low_position),
        ]

    @classmethod
    def feature_names(cls) -> List[str]:
        return [
            "change_1d", "change_3d", "change_5d",
            "volume_change", "num_stocks_up", "num_limit_up",
            "net_money_flow", "has_news_driver", "low_position",
        ]


def build_features(sector_data_t: Dict, all_sectors_t: List[Dict]) -> Dict:
    """
    从t日板块数据构建特征向量
    
    Args:
        sector_data_t: 该板块t日数据
        all_sectors_t: t日所有板块数据 (用于计算相对排名)
    """
    chg_1d = sector_data_t.get("change_pct", 0) or 0
    
    # change_3d / change_5d 从历史数据推算 (简化: 用当日数据近似)
    # TODO: 从连续历史数据精确计算
    chg_3d = chg_1d  # 近似
    chg_5d = chg_1d  # 近似
    
    # 低位判断: 5日涨幅 < 全市场均值
    market_avg = sum(s.get("change_pct", 0) or 0 for s in all_sectors_t) / max(len(all_sectors_t), 1)
    is_low = 1 if chg_5d < market_avg else 0
    
    # 新闻驱动: 暂无直接数据，默认0
    has_news = 0
    
    return {
        "change_1d": chg_1d,
        "change_3d": chg_3d,
        "change_5d": chg_5d,
        "volume_change": 1.0,  # 默认，后续从成分股数据补充
        "num_stocks_up": sector_data_t.get("num_up_stocks", 0) or 0,
        "num_limit_up": 0,     # 默认
        "net_money_flow": sector_data_t.get("net_flow", 0) or 0,
        "has_news_driver": has_news,
        "low_position": is_low,
        "early_starters": 0,   # 默认
    }


def compute_label(
    sector_name: str,
    future_days_data: Dict[str, List[Dict]],  # {date: [sector_data, ...]}
    date_start: str,
    date_end: str,
) -> int:
    """
    判断板块在未来3天是否成为主线
    
    Label = 1 如果满足任一:
      - 板块未来3天涨幅 Top 10%
      - 龙头股 ≥2个涨停 (简化: net_flow Top5 连续2天)
      - 板块资金流入 Top 5 连续2天
    """
    if not future_days_data:
        return 0
    
    score = 0
    
    # 条件1: 涨幅 Top 10%
    for date in sorted(future_days_data.keys()):
        if date < date_start or date > date_end:
            continue
        sectors = future_days_data[date]
        if not sectors:
            continue
        
        # 找该板块
        sector = next((s for s in sectors if s.get("sector") == sector_name), None)
        if not sector:
            continue
        
        all_chgs = [s.get("change_pct", 0) or 0 for s in sectors]
        all_chgs.sort(reverse=True)
        top10_threshold = all_chgs[max(0, int(len(all_chgs) * 0.1) - 1)] if all_chgs else 0
        
        if (sector.get("change_pct", 0) or 0) >= top10_threshold:
            score += 1
    
    # 条件2+3: 资金流入 Top 5 (连续2天)
    top5_count = 0
    for date in sorted(future_days_data.keys()):
        if date < date_start or date > date_end:
            continue
        sectors = future_days_data[date]
        if not sectors:
            continue
        
        flows = [(s.get("net_flow", 0) or 0, s.get("sector", "")) for s in sectors]
        flows.sort(reverse=True)
        top5_sectors = [f[1] for f in flows[:5]]
        
        if sector_name in top5_sectors:
            top5_count += 1
    
    if top5_count >= 2:
        score += 1
    
    return 1 if score >= 2 else 0


def build_dataset_from_history(
    history: Dict,
    lookback_days: int = 3,
) -> List[AuditBundle]:
    """
    主入口: 从历史数据构建训练集
    
    Args:
        history: from rotation.history.build_history()
        lookback_days: 未来几天的label窗口
    
    Returns:
        List[AuditBundle] 训练样本
    """
    all_sectors_raw = history.get("sectors", [])
    all_concepts_raw = history.get("concepts", [])
    
    # 按日期分组
    dates = sorted(set(s.get("date", "") for s in all_sectors_raw if s.get("date")))
    if len(dates) < lookback_days + 1:
        print(f"  ⚠ 历史数据不足: {len(dates)}天, 需要>{lookback_days}")
        return []
    
    # t日 → {sector_name: sector_data}
    sectors_by_date: Dict[str, Dict[str, Dict]] = {}
    all_by_date: Dict[str, List[Dict]] = {}
    
    for date in dates:
        day_sectors = [s for s in all_sectors_raw if s.get("date") == date]
        sectors_by_date[date] = {s.get("sector", ""): s for s in day_sectors}
        all_by_date[date] = day_sectors
    
    # 滑窗构建
    bundles = []
    for i, t_date in enumerate(dates[:-lookback_days]):
        sectors_t = all_by_date.get(t_date, [])
        if not sectors_t:
            continue
        
        # 未来3天的数据
        future = {d: all_by_date.get(d, []) for d in dates[i+1:i+1+lookback_days]}
        date_end = dates[min(i + lookback_days, len(dates) - 1)]
        
        for sector_data in sectors_t:
            sector_name = sector_data.get("sector", "")
            features = build_features(sector_data, sectors_t)
            label = compute_label(sector_name, future, dates[i+1], date_end)
            
            bundle = AuditBundle(
                date=t_date,
                sector=sector_name,
                change_1d=features["change_1d"],
                change_3d=features["change_3d"],
                change_5d=features["change_5d"],
                volume_change=features["volume_change"],
                num_stocks_up=features["num_stocks_up"],
                num_limit_up=features["num_limit_up"],
                net_money_flow=features["net_money_flow"],
                has_news_driver=features["has_news_driver"],
                low_position=features["low_position"],
                early_starters=features["early_starters"],
                becomes_main_theme_3d=label,
            )
            bundles.append(bundle)
    
    pos = sum(1 for b in bundles if b.becomes_main_theme_3d == 1)
    print(f"  ✅ 训练集: {len(bundles)}样本, 正例{pos}({pos/max(len(bundles),1)*100:.1f}%)")
    return bundles


def bundles_to_arrays(bundles: List[AuditBundle]):
    """转为 numpy 数组 (X, y)"""
    import numpy as np
    X = np.array([b.to_feature_vector() for b in bundles])
    y = np.array([b.becomes_main_theme_3d for b in bundles])
    return X, y

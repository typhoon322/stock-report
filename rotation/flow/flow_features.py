"""
rotation/flow/flow_features.py — 资金流特征工程

从行业/概念板块数据提取资金流特征
"""
from typing import Dict, List
import numpy as np


def extract_flow_features(sectors: List[Dict]) -> Dict:
    """
    从板块数据提取资金流特征
    
    Args:
        sectors: [{"net_flow": float, "change_pct": float, ...}, ...]
    
    Returns:
        {
            "net_flow_total": float,       # 全市场总净流入
            "net_flow_positive_count": int, # 净流入板块数
            "flow_concentration": float,    # 资金集中度(Top5占比)
            "flow_acceleration": float,     # 资金加速度
            "sector_dispersion": float,     # 板块分化度
            "strongest_sector": str,        # 最强流入板块
        }
    """
    if not sectors:
        return _empty_features()
    
    flows = [s.get("net_flow", 0) or 0 for s in sectors]
    changes = [s.get("change_pct", 0) or s.get("change_1d", 0) or 0 for s in sectors]
    
    net_flow_total = sum(flows)
    positive_flows = sum(1 for f in flows if f > 0)
    
    # 资金集中度: Top5 流入 / 总流入
    sorted_flows = sorted(flows, reverse=True)
    top5_sum = sum(sorted_flows[:5]) if len(sorted_flows) >= 5 else sum(sorted_flows)
    total_positive = sum(f for f in flows if f > 0) or 1
    concentration = round(top5_sum / total_positive, 3)
    
    # 板块分化度 (标准差)
    dispersion = round(float(np.std(changes)), 3) if changes else 0.0
    
    return {
        "net_flow_total": round(net_flow_total, 2),
        "net_flow_positive_count": positive_flows,
        "total_sectors": len(sectors),
        "flow_concentration": concentration,
        "sector_dispersion": dispersion,
        "breadth_flow": round(positive_flows / max(len(sectors), 1), 3),
    }


def _empty_features() -> Dict:
    return {
        "net_flow_total": 0, "net_flow_positive_count": 0,
        "total_sectors": 0, "flow_concentration": 0,
        "sector_dispersion": 0, "breadth_flow": 0,
    }

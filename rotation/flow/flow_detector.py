"""
rotation/flow/flow_detector.py — 资金流检测主入口
"""
from typing import Dict, List
from .flow_features import extract_flow_features
from .flow_regime import detect_flow_regime, compute_flow_direction


def detect_flow(sectors: List[Dict]) -> Dict:
    """
    完整资金流检测管道
    
    Returns:
        {
            "regime": str,
            "direction": dict,
            "features": dict,
        }
    """
    features = extract_flow_features(sectors)
    
    # 资金加速度: 从前日数据推算 (简化: 用 concentration 作为 proxy)
    flow_accel = (features["flow_concentration"] - 0.5) * 2  # -1 到 +1
    
    regime = detect_flow_regime(
        net_flow_total=features["net_flow_total"],
        breadth_up=features["breadth_flow"],
        sector_dispersion=features["sector_dispersion"],
        flow_acceleration=flow_accel,
    )
    
    direction = compute_flow_direction(
        features["net_flow_total"], flow_accel
    )
    
    return {
        "regime": regime,
        "direction": direction,
        "features": features,
    }

"""
rotation/validation/feature_switcher.py — 模块开关控制

支持动态组合: 全开 / 单模块关闭 / 最小核心
"""
from typing import Dict, List

# 完整特性列表
ALL_FEATURES = ["RTI", "FLOW", "SMART_MONEY", "COST_BASIS", "BREAKOUT", "MTF"]

# 预定义配置
PRESET_CONFIGS = {
    "baseline":       {f: True for f in ALL_FEATURES},
    "no_rti":         {**{f: True for f in ALL_FEATURES}, "RTI": False},
    "no_flow":        {**{f: True for f in ALL_FEATURES}, "FLOW": False},
    "no_smart_money": {**{f: True for f in ALL_FEATURES}, "SMART_MONEY": False},
    "no_cost_basis":  {**{f: True for f in ALL_FEATURES}, "COST_BASIS": False},
    "no_breakout":    {**{f: True for f in ALL_FEATURES}, "BREAKOUT": False},
    "no_mtf":         {**{f: True for f in ALL_FEATURES}, "MTF": False},
    "minimal_core":   {"RTI": True, "FLOW": True, "SMART_MONEY": False, "COST_BASIS": False, "BREAKOUT": False, "MTF": False},
    "no_new_modules": {"RTI": True, "FLOW": True, "SMART_MONEY": False, "COST_BASIS": False, "BREAKOUT": False, "MTF": False},
    "all_off":        {f: False for f in ALL_FEATURES},
}


def get_config(config_name: str) -> Dict[str, bool]:
    """获取预定义配置"""
    return dict(PRESET_CONFIGS.get(config_name, PRESET_CONFIGS["baseline"]))


def list_configs() -> List[str]:
    """列出所有可用配置"""
    return list(PRESET_CONFIGS.keys())


def apply_config(config: Dict[str, bool], signals: Dict[str, float]) -> Dict[str, float]:
    """
    应用配置开关: 将关闭模块的信号设为0
    """
    applied = dict(signals)
    for feature in ALL_FEATURES:
        key = feature.lower()
        if key in applied and not config.get(feature, True):
            applied[key] = 0.0
    return applied

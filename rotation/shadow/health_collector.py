"""
System Health Collector — API成功率、数据缺失率、异常检测
"""
import json, os, time
from datetime import datetime, timezone, timedelta


def _now_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _today_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y%m%d")


def save_health_log(
    api_stats: dict = None,
    data_quality: dict = None,
    module_status: dict = None,
) -> str:
    """保存系统健康日志
    
    Args:
        api_stats: {'api_name': {'calls': N, 'success': N, 'errors': N}}
        data_quality: {'missing_rate': float, 'fallback_count': int, ...}
        module_status: {'rti': 'ok', 'ls': 'no_data', ...}
    """
    health = {
        "timestamp": _now_str(),
        "api": api_stats or {},
        "data_quality": data_quality or {"missing_rate": 0, "fallback_count": 0},
        "modules": module_status or {},
    }
    
    # 自动计算缺失率
    if data_quality:
        total = data_quality.get("total_fields", 0)
        missing = data_quality.get("missing_fields", 0)
        if total > 0:
            health["data_quality"]["missing_rate"] = round(missing / total, 4)
    
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "rotation", "shadow", "logs", f"system_health_{_today_str()}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(health, f, ensure_ascii=False, indent=2, default=str)
    
    return path


def collect_api_stats() -> dict:
    """收集当前运行的API调用统计"""
    # AKShare 不提供内置计数器，基于已知调用路径估算
    return {
        "stock_zh_a_spot": {"calls": 1, "source": "sina"},
        "stock_board_industry_name_em": {"calls": 1, "notes": "cached after first call"},
        "stock_board_concept_name_em": {"calls": 1, "notes": "cached after first call"},
        "stock_board_industry_cons_em": {"calls": "N (per sector)", "notes": "retry=2"},
        "stock_board_concept_cons_em": {"calls": "N (per sector)", "notes": "retry=2"},
        "futures_global_spot_em": {"calls": 1},
        "sinajs_index": {"calls": 1, "source": "sina"},
        "sinajs_global_index": {"calls": 1, "source": "sina"},
    }

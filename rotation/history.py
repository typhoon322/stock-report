"""
rotation/history.py — 历史数据缓存层

为回测和RTI v3提供1-2年日级板块+个股历史数据
存储: JSON文件缓存, 增量更新
"""
import akshare as ak
import pandas as pd
import json, os, time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "history_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_key(date_str: str) -> str:
    return date_str.replace("-", "")

def load_cache(filename: str) -> Optional[list]:
    path = os.path.join(CACHE_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def save_cache(filename: str, data):
    path = os.path.join(CACHE_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, default=str)

def fetch_sector_history(date_str: str) -> List[dict]:
    """获取某日的行业板块数据"""
    cached = load_cache(f"sector_{date_str}.json")
    if cached:
        return cached
    
    rows = []
    try:
        df = ak.stock_fund_flow_industry(symbol='即时')
        for _, r in df.iterrows():
            rows.append({
                "date": date_str,
                "sector": str(r['行业']),
                "change_pct": float(r.get('行业-涨跌幅', 0) or 0),
                "net_flow": float(r.get('净额', 0) or 0),
                "num_companies": int(float(r.get('公司家数', 0) or 0)),
            })
        save_cache(f"sector_{date_str}.json", rows)
    except Exception as e:
        print(f"  ⚠ sector history {date_str}: {e}")
    return rows


def fetch_concept_history(date_str: str) -> List[dict]:
    """获取某日的概念板块数据"""
    cached = load_cache(f"concept_{date_str}.json")
    if cached:
        return cached
    
    rows = []
    try:
        df = ak.stock_fund_flow_concept(symbol='即时')
        for _, r in df.iterrows():
            rows.append({
                "date": date_str,
                "sector": str(r['行业']),
                "change_pct": float(r.get('行业-涨跌幅', 0) or 0),
                "net_flow": float(r.get('净额', 0) or 0),
            })
        save_cache(f"concept_{date_str}.json", rows)
    except Exception as e:
        print(f"  ⚠ concept history {date_str}: {e}")
    return rows


def fetch_stock_history(date_str: str) -> List[dict]:
    """获取某日的全市场个股数据(缓存7天)"""
    cached = load_cache(f"stocks_{date_str}.json")
    if cached:
        return cached
    
    rows = []
    try:
        df = ak.stock_zh_a_spot()
        for _, r in df.iterrows():
            rows.append({
                "date": date_str,
                "code": str(r['代码']),
                "name": str(r.get('名称', '')),
                "change_pct": float(r.get('涨跌幅', 0) or 0),
                "volume_ratio": float(r.get('量比', 1.0) or 1.0),
                "is_limit_up": float(r.get('涨跌幅', 0) or 0) >= 9.5,
            })
        save_cache(f"stocks_{date_str}.json", rows)
    except Exception as e:
        print(f"  ⚠ stock history {date_str}: {e}")
    return rows


def build_history(days: int = 120) -> Dict:
    """
    构建历史数据集
    
    Returns: {
        "sectors": [...],    # 每日板块数据
        "concepts": [...],   # 每日概念数据
        "stocks": [...],     # 每日个股数据(只存最近7天)
        "date_range": [start, end]
    }
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    
    print(f"📡 采集{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')} 历史数据...")
    
    all_sectors = []
    all_concepts = []
    
    current = start
    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        sectors = fetch_sector_history(ds)
        concepts = fetch_concept_history(ds)
        
        all_sectors.extend(sectors)
        all_concepts.extend(concepts)
        
        if sectors:
            print(f"  {ds}: {len(sectors)}行业 + {len(concepts)}概念")
        
        current += timedelta(days=1)
    
    # 最近的个股数据
    recent_stocks = fetch_stock_history(end.strftime("%Y-%m-%d"))
    
    result = {
        "sectors": all_sectors,
        "concepts": all_concepts,
        "stocks": recent_stocks,
        "date_range": [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")],
        "total_records": len(all_sectors) + len(all_concepts),
    }
    
    save_cache("history_meta.json", {
        "date_range": result["date_range"],
        "total_records": result["total_records"],
        "last_updated": datetime.now().isoformat(),
    })
    
    return result


def get_sector_timeseries(history: Dict, sector_name: str) -> List[dict]:
    """从历史数据提取某个板块的时间序列"""
    series = []
    all_sectors = history.get("sectors", [])
    for s in all_sectors:
        if sector_name in s.get("sector", ""):
            series.append(s)
    return sorted(series, key=lambda x: x["date"])


def get_top_sectors_by_date(history: Dict, date_str: str, n: int = 5) -> List[dict]:
    """某日涨幅最高的板块"""
    day_sectors = [s for s in history.get("sectors", []) if s["date"] == date_str]
    day_sectors.sort(key=lambda x: x["change_pct"], reverse=True)
    return day_sectors[:n]

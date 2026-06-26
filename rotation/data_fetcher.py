"""
rotation/data_fetcher.py — 数据采集层

从 AKShare / Sinajs / westock-data 采集板块+个股数据，
填充 Stock / Sector / MarketSentiment 模型。
"""
import akshare as ak
import pandas as pd
import requests
import json
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .models import Stock, Sector, MarketSentiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def to_float(v, default=0.0):
    try: return float(v)
    except: return default

def fetch_sina_index(code: str) -> Optional[List[str]]:
    """Sinajs实时指数"""
    try:
        r = requests.get(f"https://hq.sinajs.cn/list={code}",
                        headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        r.encoding = 'gbk'
        if code in r.text and '=""' not in r.text:
            return r.text.split('="')[1].strip('";').split(',')
    except: pass
    return None


def fetch_market_breadth() -> Tuple[int, int, int]:
    """从全市场数据计算涨跌家数
    
    Returns: (上涨数, 下跌数, 涨停数)
    """
    try:
        df = ak.stock_zh_a_spot()  # Sina源
        up = len(df[df["涨跌幅"].astype(float) > 0])
        down = len(df[df["涨跌幅"].astype(float) < 0])
        limit_up = len(df[df["涨跌幅"].astype(float) >= 9.5])
        return up, down, limit_up
    except:
        return 0, 0, 0


def fetch_industry_sectors() -> List[Sector]:
    """从行业板块数据构建 Sector 列表"""
    sectors = []
    try:
        df = ak.stock_fund_flow_industry(symbol='即时')
        for _, row in df.iterrows():
            sec = Sector(
                name=str(row['行业']),
                change_1d=to_float(row.get('行业-涨跌幅', 0)),
                net_money_flow=to_float(row.get('净额', 0)),
                num_stocks_up=int(to_float(row.get('公司家数', 0))),
            )
            sectors.append(sec)
    except Exception as e:
        print(f"  ⚠ 行业板块获取失败: {e}")
    return sectors


def fetch_concept_sectors() -> List[Sector]:
    """从概念板块数据构建 Sector 列表（更细粒度）"""
    sectors = []
    try:
        df = ak.stock_fund_flow_concept(symbol='即时')
        for _, row in df.iterrows():
            sec = Sector(
                name=str(row['行业']),
                change_1d=to_float(row.get('行业-涨跌幅', 0)),
                net_money_flow=to_float(row.get('净额', 0)),
            )
            sectors.append(sec)
    except:
        pass
    return sectors


def fetch_all_stocks() -> List[Stock]:
    """获取全市场个股数据"""
    stocks = []
    try:
        df = ak.stock_zh_a_spot()
        for _, row in df.iterrows():
            s = Stock(
                code=str(row['代码']),
                name=str(row.get('名称', '')),
                change_pct=to_float(row.get('涨跌幅', 0)),
                volume_ratio=to_float(row.get('量比', 1.0), 1.0),
                is_limit_up=to_float(row.get('涨跌幅', 0)) >= 9.5,
                industry=str(row.get('所属行业', '')),
            )
            stocks.append(s)
    except:
        pass
    return stocks


# ── 板块代码缓存（全局，避免重复调用 _name_em()）──
_sector_code_map: Dict[str, str] = {}
_code_map_loaded = False


def _ensure_code_map():
    """预加载行业+概念板块名称→代码映射（只调一次API）"""
    global _code_map_loaded, _sector_code_map
    if _code_map_loaded:
        return
    import akshare as ak
    for _ in range(3):
        try:
            df = ak.stock_board_industry_name_em()
            for __, row in df.iterrows():
                _sector_code_map[str(row['板块名称'])] = str(row['板块代码'])
            break
        except Exception:
            time.sleep(3)
    for _ in range(3):
        try:
            df = ak.stock_board_concept_name_em()
            for __, row in df.iterrows():
                _sector_code_map[str(row['板块名称'])] = str(row['板块代码'])
            break
        except Exception:
            time.sleep(3)
    _code_map_loaded = True


def fetch_sector_constituents(sector_name: str, max_retries: int = 3) -> List[str]:
    """获取板块成分股代码列表（带重试+限频+预缓存code map）"""
    import akshare as ak
    _ensure_code_map()
    
    board_code = _sector_code_map.get(sector_name)
    if not board_code:
        return []
    
    time.sleep(0.5)  # 限频
    
    for attempt in range(max_retries):
        try:
            df_cons = ak.stock_board_industry_cons_em(symbol=board_code)
            if df_cons is not None and len(df_cons) > 0:
                return df_cons['代码'].tolist()
        except Exception:
            pass
        
        try:
            df_cons = ak.stock_board_concept_cons_em(symbol=board_code)
            if df_cons is not None and len(df_cons) > 0:
                return df_cons['代码'].tolist()
        except Exception:
            pass
        
        if attempt < max_retries - 1:
            delay = 3 + attempt * 2
            time.sleep(delay)
    
    return []


def _normalize_code(code: str) -> str:
    """统一不同数据源的代码格式为纯数字"""
    c = str(code).strip().upper()
    # 去掉 SH/SZ/BJ 前缀，去掉 .SH/.SZ 后缀
    for prefix in ('SH', 'SZ', 'BJ', 'S_'):
        if c.startswith(prefix) and len(c) > 2:
            c = c[len(prefix):]
    for suffix in ('.SH', '.SZ', '.BJ', '.OF', '.IB'):
        if c.endswith(suffix):
            c = c[:-len(suffix)]
    return c


def match_stocks_to_sectors(all_stocks: List[Stock], sector_names: List[str]) -> Dict[str, List[Stock]]:
    """将个股匹配到所属板块（成分股API优先，限频重试，全部板块）"""
    result: Dict[str, List[Stock]] = {name: [] for name in sector_names}
    
    # 预建代码查找表
    stock_by_code = {_normalize_code(s.code): s for s in all_stocks}
    
    total = len(sector_names)
    matched_via_api = 0
    for i, sector_name in enumerate(sector_names):
        if i > 0 and i % 3 == 0:
            time.sleep(1.5)
        
        codes = fetch_sector_constituents(sector_name, max_retries=2)
        if codes:
            matched_stocks = [stock_by_code[_normalize_code(c)] for c in codes if _normalize_code(c) in stock_by_code]
            if matched_stocks:
                result[sector_name] = matched_stocks
                matched_via_api += 1
    
    # Fallback: 用板块名模糊匹配（Sina数据没有 industry 字段，只做代码匹配兜底）
    name_match_count = 0
    for sector_name in sector_names:
        if not result.get(sector_name):
            result[sector_name] = [
                s for s in all_stocks 
                if sector_name in (s.industry or '') or (s.industry or '') in sector_name
            ]
            if len(result[sector_name]) > 0:
                name_match_count += 1
    
    print(f"    API成分股匹配: {matched_via_api}/{total} 个板块")
    print(f"    名称模糊匹配: {name_match_count}/{total} 个板块")
    return result


def compute_sector_stats(sectors: List[Sector], all_stocks: List[Stock]) -> List[Sector]:
    """用全市场数据补充板块统计（成分股API优先，次用stock.industry字段）"""
    sector_names = [s.name for s in sectors]
    name_stock_map = match_stocks_to_sectors(all_stocks, sector_names)
    
    for sec in sectors:
        sec.stocks = name_stock_map.get(sec.name, [])
        sec.num_limit_up = sum(1 for s in sec.stocks if s.is_limit_up)
        sec.num_stocks_up = sum(1 for s in sec.stocks if s.change_pct > 0)
        
        # 量比均值
        if sec.stocks:
            ratios = [s.volume_ratio for s in sec.stocks if s.volume_ratio > 0]
            sec.volume_change = sum(ratios) / len(ratios) if ratios else 1.0
    
    return sectors


def estimate_low_position(sec: Sector, market_avg_5d: float) -> bool:
    """判断板块是否处于低位（相对大盘）"""
    if sec.change_5d < market_avg_5d and sec.change_1d > 0:
        return True
    return sec.change_5d < 0  # 5日累计下跌也视为低位


def build_market_sentiment() -> MarketSentiment:
    """构建市场情绪对象"""
    up, down, limit_up = fetch_market_breadth()
    total = up + down
    breadth = up / total if total > 0 else 0.5
    
    return MarketSentiment(
        limit_up_count=limit_up,
        fall_limit_count=down - up if down > up else 0,  # 近似跌停
        market_breadth=round(breadth, 3),
        up_down_ratio=round(up / max(down, 1), 2),
    )


def fetch_news_for_sectors() -> Dict[str, List[str]]:
    """获取新闻，按板块关键词归类"""
    news_map: Dict[str, List[str]] = {}
    try:
        df = ak.stock_info_global_sina()
        for _, row in df.iterrows():
            title = str(row.get('内容', ''))[:200]
            # 简单分词检测
            for sector_name in ["AI", "芯片", "半导体", "新能源", "医药", "消费", "金融", "地产", "军工"]:
                if sector_name in title:
                    news_map.setdefault(sector_name, []).append(title)
    except:
        pass
    return news_map

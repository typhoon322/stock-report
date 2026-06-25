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


def compute_sector_stats(sectors: List[Sector], all_stocks: List[Stock]) -> List[Sector]:
    """用全市场数据补充板块统计（涨停数、成交量变化、成分股等）"""
    for sec in sectors:
        # 找属于该板块的个股
        sector_stocks = [s for s in all_stocks if sec.name in s.industry or s.industry in sec.name]
        sec.stocks = sector_stocks
        
        # 统计涨停
        sec.num_limit_up = sum(1 for s in sector_stocks if s.is_limit_up)
        
        # 统计上涨家数
        sec.num_stocks_up = sum(1 for s in sector_stocks if s.change_pct > 0)
        
        # 量比均值
        if sector_stocks:
            ratios = [s.volume_ratio for s in sector_stocks if s.volume_ratio > 0]
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

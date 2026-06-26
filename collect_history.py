#!/usr/bin/env python3
"""
collect_history.py — 采集60天真实行业板块历史数据

运行后填充 history_cache/, 然后可执行回测+消融。
"""
import akshare as ak
import json, os, time, sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "history_cache")
os.makedirs(CACHE, exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")


def _save(name, data):
    with open(os.path.join(CACHE, name), 'w') as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def collect_sectors(days=60):
    """采集行业板块日线历史 (60交易日 ≈ 90日历来天)"""
    print(f"[1/4] 获取板块列表...")
    df_names = None
    for attempt in range(3):
        try:
            df_names = ak.stock_board_industry_name_em()
            break
        except Exception as e:
            if attempt < 2:
                print(f"    retry {attempt+1}: {e}")
                time.sleep(5)
    
    if df_names is None:
        print("  ❌ 板块列表获取失败，跳过")
        return []
    
    sectors = []
    for _, row in df_names.iterrows():
        sectors.append({
            "name": str(row['板块名称']),
            "code": str(row['板块代码']),
        })
    print(f"  共 {len(sectors)} 个行业板块")
    
    # 只取前30个主要板块（避免API过载）
    major_sectors = sectors[:30]
    
    all_records = []
    success = 0
    for i, sec in enumerate(major_sectors):
        if i > 0 and i % 3 == 0:
            time.sleep(1)  # 限频
        
        for attempt in range(2):
            try:
                df = ak.stock_board_industry_hist_em(symbol=sec['code'])
                if df is None or len(df) == 0:
                    continue
                # 取最后 days 行
                df = df.tail(days)
                for _, r in df.iterrows():
                    all_records.append({
                        "date": str(r['日期'])[:10],
                        "sector": sec['name'],
                        "change_pct": float(r.get('涨跌幅', 0) or 0),
                        "volume": float(r.get('成交量', 0) or 0),
                        "open": float(r.get('开盘', 0) or 0),
                        "close": float(r.get('收盘', 0) or 0),
                    })
                success += 1
                break
            except Exception:
                if attempt < 1:
                    time.sleep(3)
        
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(major_sectors)}] {sec['name']} ... OK({success})")
    
    _save("sector_history.json", all_records)
    print(f"  ✅ sector_history.json: {len(all_records)} 条记录 ({success} 板块)")
    return all_records


def collect_indices(days=60):
    """采集六大指数日线"""
    print("\n[2/4] 采集指数日线...")
    indices = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
    }
    
    records = []
    for code, name in indices.items():
        for attempt in range(2):
            try:
                df = ak.stock_zh_index_daily(symbol=code)
                df = df.tail(days)
                for _, r in df.iterrows():
                    records.append({
                        "date": str(r['date'])[:10],
                        "index": name,
                        "code": code,
                        "close": float(r['close']),
                        "volume": float(r.get('volume', 0) or 0),
                    })
                print(f"  {name}: {len(df)} days")
                break
            except:
                time.sleep(2)
    
    _save("index_history.json", records)
    print(f"  ✅ index_history.json: {len(records)} 条")
    return records


def collect_market_breadth(days=60):
    """采集市场涨跌家数 (用概念板块近似)"""
    print("\n[3/4] 采集市场广度...")
    breadth = []
    
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_spot()
            total = len(df)
            up = len(df[df['涨跌幅'] > 0])
            down = len(df[df['涨跌幅'] < 0])
            limit_up = len(df[df['涨跌幅'] >= 9.5])
            fall_limit = len(df[df['涨跌幅'] <= -9.5])
            vol = float(df['成交额'].sum()) if '成交额' in df.columns else 0
            
            breadth.append({
                "date": TODAY,
                "total": total,
                "up": up,
                "down": down,
                "limit_up": limit_up,
                "fall_limit": fall_limit,
                "total_volume": vol,
                "breadth": round(up / total, 4) if total > 0 else 0,
            })
            print(f"  {TODAY}: {up}/{total} up, {limit_up} limit-up, vol={vol/1e8:.0f}亿")
            break
        except:
            time.sleep(3)
    
    _save("breadth.json", breadth)
    return breadth


def run_summary():
    """总览"""
    print("\n" + "="*50)
    print("[4/4] SUMMARY")
    for f in sorted(os.listdir(CACHE)):
        path = os.path.join(CACHE, f)
        if f.endswith('.json'):
            size = os.path.getsize(path)
            with open(path) as fh:
                data = json.load(fh)
            if isinstance(data, list):
                print(f"  {f}: {size:>6,}B  ({len(data)} records)")
            else:
                print(f"  {f}: {size:>6,}B")
    print("="*50)


if __name__ == "__main__":
    print(f"📦 历史数据采集 — {TODAY}")
    print(f"   缓存目录: {CACHE}")
    print(f"   目标: 60交易日板块+指数+广度")
    print()
    
    try:
        collect_sectors(60)
    except Exception as e:
        print(f"  ⚠ sectors: {e}")
    
    try:
        collect_indices(60)
    except Exception as e:
        print(f"  ⚠ indices: {e}")
    
    try:
        collect_market_breadth()
    except Exception as e:
        print(f"  ⚠ breadth: {e}")
    
    run_summary()
    print("\n✅ 历史数据采集完成。现在可以运行:")
    print("   python -m rotation.backtest")
    print("   python -m rotation.validation.ablation_engine")

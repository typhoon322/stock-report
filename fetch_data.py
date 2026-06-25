#!/usr/bin/env python3
"""
A股午盘数据采集脚本 v2 — 多数据源并行采集 + 交叉验证
数据源：东方财富（主力）→ 新浪（备份）→ 腾讯自选股（单股补全）
"""
import akshare as ak
import pandas as pd
import json
import sys
import os
import time
from datetime import datetime

OUT_DIR = "/Users/yanx/WorkBuddy/automation-2026-06-24-19-35-08"

# ============================================================
# 工具函数
# ============================================================

def retry(func, name, max_retries=1, timeout=None):
    """重试机制"""
    for attempt in range(max_retries + 1):
        try:
            print(f"  [{name}] 第{attempt+1}次尝试...")
            start = time.time()
            result = func()
            elapsed = time.time() - start
            rows = len(result) if hasattr(result, '__len__') and not isinstance(result, str) else 'N/A'
            print(f"  [{name}] ✓ 成功 ({elapsed:.1f}s, {rows}行)")
            return result
        except Exception as e:
            short_err = str(e)[:80]
            print(f"  [{name}] ✗ 失败: {short_err}")
            if attempt < max_retries:
                print(f"  [{name}] 重试中...")
    print(f"  [{name}] ⚠ 数据暂缺")
    return None

def save_json(data, filename, meta=None):
    """保存数据 + 元信息"""
    path = os.path.join(OUT_DIR, filename)
    if data is not None:
        if isinstance(data, pd.DataFrame):
            data.to_json(path, orient='records', force_ascii=False)
        elif isinstance(data, (list, dict)):
            with open(path, 'w') as f:
                json.dump(data, f, ensure_ascii=False)
        print(f"  → 保存: {filename}")
        if meta:
            meta_path = path.replace('.json', '_meta.json')
            with open(meta_path, 'w') as f:
                json.dump(meta, f, ensure_ascii=False)
    else:
        with open(path, 'w') as f:
            json.dump({"status": "data_missing", "timestamp": datetime.now().isoformat()}, f)
        print(f"  → 空标记: {filename}")

def compare_sources(df_em, df_sina):
    """交叉验证两个数据源的涨跌幅差异（抽样对比）"""
    if df_em is None or df_sina is None:
        return None
    
    # 统一代码格式
    em_cols = df_em.columns.tolist()
    sina_cols = df_sina.columns.tolist()
    
    # 东方财富列名（可能有变化）
    code_col_em = '代码' if '代码' in em_cols else em_cols[0]
    name_col_em = '名称' if '名称' in em_cols else em_cols[1]
    pct_col_em = '涨跌幅' if '涨跌幅' in em_cols else ([c for c in em_cols if '涨跌幅' in str(c)] or [None])[0]
    price_col_em = '最新价' if '最新价' in em_cols else ([c for c in em_cols if '最新价' in str(c)] or [None])[0]
    
    code_col_sina = '代码' if '代码' in sina_cols else sina_cols[0]
    pct_col_sina = '涨跌幅' if '涨跌幅' in sina_cols else ([c for c in sina_cols if '涨跌幅' in str(c)] or [None])[0]
    price_col_sina = '最新价' if '最新价' in sina_cols else ([c for c in sina_cols if '最新价' in str(c)] or [None])[0]
    
    if not all([code_col_em, pct_col_em, code_col_sina, pct_col_sina]):
        return {"error": "无法匹配涨跌幅列"}
    
    # 取交集代码
    codes_em = set(df_em[code_col_em].astype(str))
    codes_sina = set(df_sina[code_col_sina].astype(str))
    common = codes_em & codes_sina
    
    if len(common) < 100:
        return {"error": f"交集代码过少({len(common)}个)"}
    
    # 抽样100只对比
    sample = list(common)[:100]
    em_sub = df_em[df_em[code_col_em].astype(str).isin(sample)].set_index(code_col_em)
    sina_sub = df_sina[df_sina[code_col_sina].astype(str).isin(sample)].set_index(code_col_sina)
    
    diffs = []
    for code in sample:
        if code in em_sub.index and code in sina_sub.index:
            try:
                pct_em = float(em_sub.loc[code, pct_col_em])
                pct_sina = float(sina_sub.loc[code, pct_col_sina])
                diff = abs(pct_em - pct_sina)
                diffs.append({'code': code, 'diff': round(diff, 4)})
            except:
                pass
    
    if not diffs:
        return {"error": "无法计算差异"}
    
    avg_diff = sum(d['diff'] for d in diffs) / len(diffs)
    max_diff = max(d['diff'] for d in diffs)
    big_diffs = [d for d in diffs if d['diff'] > 0.5]
    
    return {
        "样本数": len(diffs),
        "平均差异": round(avg_diff, 4),
        "最大差异": round(max_diff, 4),
        "差异>0.5%的个数": len(big_diffs),
        "交叉覆盖数": len(common),
        "结论": "数据一致" if avg_diff < 0.1 else ("轻微偏差" if avg_diff < 0.3 else "⚠ 偏差较大")
    }


# ============================================================
# 主流程
# ============================================================

print("=" * 60)
print("A股午盘数据采集 v2 (多源并行)")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 60)

sources_status = {}

# ============================================================
# Step 0: 核心数据 — 全市场个股（双源并行）
# ============================================================
print("\n" + "=" * 60)
print("[核心] 全市场个股数据 — 双源并行采集")
print("=" * 60)

print("\n>>> 源A: 东方财富 (stock_zh_a_spot_em) — 字段最全")
df_em = retry(lambda: ak.stock_zh_a_spot_em(), "东方财富-个股全量")
save_json(df_em, "data_all_em.json", {"source": "东方财富", "time": datetime.now().isoformat()})

print("\n>>> 源B: 新浪财经 (stock_zh_a_spot) — 备选源")
df_sina = retry(lambda: ak.stock_zh_a_spot(), "新浪-个股全量")
save_json(df_sina, "data_all_sina.json", {"source": "新浪财经", "time": datetime.now().isoformat()})

# 交叉验证
print("\n>>> 交叉验证")
comparison = compare_sources(df_em, df_sina)
if comparison:
    print(f"  交叉覆盖: {comparison.get('交叉覆盖数', 'N/A')} 只")
    print(f"  平均差异: {comparison.get('平均差异', 'N/A')}%")
    print(f"  结论: {comparison.get('结论', 'N/A')}")
    save_json(comparison, "data_cross_validation.json")
else:
    print("  ⚠ 无法交叉验证（至少一个源失败）")

# 选择主力数据
if df_em is not None:
    df_all = df_em
    sources_status['全市场个股'] = '东方财富 ✓'
    print("\n>>> 主数据源: 东方财富")
elif df_sina is not None:
    df_all = df_sina
    sources_status['全市场个股'] = '新浪财经 ✓ (东方财富失败)'
    print("\n>>> 主数据源: 新浪财经 (东方财富失败)")
else:
    df_all = None
    sources_status['全市场个股'] = '❌ 双源均失败'
    print("\n>>> ⚠ 双源均失败！")

# 最终保存统一格式
save_json(df_all, "data_step1_all.json")

# ============================================================
# Step 1: 行业资金流向（双源）
# ============================================================
print("\n" + "=" * 60)
print("[Step 1] 行业资金流向 — 双源")
print("=" * 60)

print("\n>>> 源A: 行业资金流排行")
df_ind_rank = retry(
    lambda: ak.stock_sector_fund_flow_rank(indicator='今日', sector_type='行业资金流'),
    "行业资金流排行"
)

print("\n>>> 源B: 行业板块实时行情")
df_ind_flow = retry(
    lambda: ak.stock_fund_flow_industry(symbol='即时'),
    "行业板块实时行情"
)

# 选择可用源
if df_ind_rank is not None:
    save_json(df_ind_rank, "data_step3_industry_fund.json")
    sources_status['行业资金流向'] = '排行 ✓'
elif df_ind_flow is not None:
    save_json(df_ind_flow, "data_step3_industry_fund.json")
    sources_status['行业资金流向'] = '实时行情替代 ✓'
else:
    sources_status['行业资金流向'] = '❌'
    save_json(None, "data_step3_industry_fund.json")

# 实时行情单独保存
save_json(df_ind_flow, "data_step5_industry_flow.json")

# ============================================================
# Step 2: 概念资金 + 板块异动
# ============================================================
print("\n" + "=" * 60)
print("[Step 2] 概念资金 + 板块异动")
print("=" * 60)

print("\n>>> 概念资金流向")
df_concept = retry(lambda: ak.stock_fund_flow_concept(symbol='即时'), "概念资金流向")
save_json(df_concept, "data_step4_concept_fund.json")
sources_status['概念资金流向'] = '✓' if df_concept is not None else '❌'

print("\n>>> 板块异动")
df_rotation = retry(lambda: ak.stock_board_change_em(), "板块异动")
save_json(df_rotation, "data_step2_rotation.json")
sources_status['板块异动'] = '✓' if df_rotation is not None else '❌'

# ============================================================
# Step 3: ETF数据
# ============================================================
print("\n" + "=" * 60)
print("[Step 3] ETF实时数据")
print("=" * 60)

df_etf = retry(lambda: ak.fund_etf_spot_em(), "ETF实时行情")
save_json(df_etf, "data_step6_etf.json")
sources_status['ETF数据'] = '✓' if df_etf is not None else '❌'

# ============================================================
# 汇总报告
# ============================================================
print("\n" + "=" * 60)
print("数据采集完成 — 源状态汇总")
print("=" * 60)
for key, status in sources_status.items():
    icon = "✅" if "✓" in status else "❌"
    print(f"  {icon} {key}: {status}")

# 保存源状态
meta_report = {
    "timestamp": datetime.now().isoformat(),
    "sources": sources_status,
    "cross_validation": comparison,
    "primary_stock_source": "东方财富" if df_em is not None else ("新浪" if df_sina is not None else "NONE"),
    "stock_count": len(df_all) if df_all is not None else 0,
}
save_json(meta_report, "data_source_report.json")
print(f"\n完整报告: data_source_report.json")

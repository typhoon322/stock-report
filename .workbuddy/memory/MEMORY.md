# 项目长期记忆 — 量化分析系统

## 自动化任务（按时间顺序）
| 时间 | 任务 | ID | 状态 |
|------|------|-----|------|
| 8:15 AM | 早盘报告（美股+日韩+商品+新闻） | automation-1782372617267 | ACTIVE |
| 11:35 AM | 午盘分析+下午机会扫描 | automation-1782300903285 | ACTIVE |
| 15:05 PM | 收盘总结（持仓复盘+明日展望） | automation-1782377595324 | ACTIVE |
| 15:15 PM | 涨停板日度分析 | automation-1782294959261 | ACTIVE |

## 数据源策略
- **个股全量**: 东方财富(主,字段全) → 新浪(备,稳定) 双源fallback
- **主要指数**: Sinajs 实时 (s_sh000001等) — 最稳定
- **美股指数**: Sina index_us_stock_sina (.INX/.DJI/.IXIC)
- **恒生指数**: Sinajs int_hangseng
- **日经225**: Sinajs int_nikkei
- **韩国KOSPI**: yfinance(不稳定) — 次级指标
- **全球期货**: 东方财富 futures_global_spot_em (代码已修正: GC/CL/HG/SI/CN+非NaN)
- **外汇**: 中行 currency_boc_sina
- **新闻**: Sina stock_info_global_sina
- **市场广度**: westock-data changedist

## 期货合约代码映射（修正后）
- 黄金: GC前缀 + 非NaN → GC27Q COMEX黄金2708
- 原油: CL前缀 + 非NaN → CL27V NYMEX原油2710
- 铜: HG前缀 → HG27U
- 白银: SI前缀 → SI27U
- A50: CN前缀 + 非NaN → CN00Y/CN26N

## 持仓股票
600487(亨通光电), 600522(中天科技), 002745(木林森), 600733(北汽蓝谷)
513060(恒生医疗ETF), 512170(医疗ETF), 515790(光伏ETF)

## 脚本文件
- fetch_data.py: 午盘数据采集（双源）
- fetch_morning.py: 早盘数据采集 v3
- fetch_closing.py: 收盘数据采集 v1

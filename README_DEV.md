# Stock-Report 量化策略系统 — 开发者手册

> 版本: v3.1 | 最后更新: 2026-06-26 (v2.21: 云雾报告系统重构)
> 定位: 中期资金轮动识别与交易决策辅助系统  
> 运行: GitHub Actions 云端 + WorkBuddy 本地自动化  
> 输出: 6份日报/周报 HTML → GitHub Pages 手机端访问  
> 数据源: AKShare (东方财富/Sina) + Sinajs 实时 + 中行外汇

---

## 一、项目全景

```
┌─────────────────────────────────────────────────────────┐
│                    数据采集层                              │
│  AKShare / Sinajs / 东方财富 / 中行外汇                     │
│  ├── 全市场5528只个股 (stock_zh_a_spot)                    │
│  ├── 90个行业板块 (stock_fund_flow_industry)               │
│  ├── 385个概念板块 (stock_fund_flow_concept)               │
│  ├── 美股三大指数 (index_us_stock_sina)                    │
│  ├── 全球期货620种 (futures_global_spot_em)                │
│  ├── 新闻全球 (stock_info_global_sina)                    │
│  └── 历史缓存122个JSON (60天日级数据)                       │
├─────────────────────────────────────────────────────────┤
│                    特征工程层 (rotation/)                   │
│  RTI v3 — 轮动识别 (6因子加权: FlowShift/Acceleration/...) │
│  BSI    — 板块强度 (5维评分: 涨幅/涨停/量/资金/持续性)         │
│  LS     — 龙头识别 (5维: 启动/突破/放量/第一/集中度)          │
│  Phase  — 周期判断 (冰点→试探→轮动→主升→退潮)               │
│  History— 历史数据缓存 (60天28K条记录)                      │
│  Backtest— 回测引擎 (信号→交易→绩效6指标)                   │
│  Optimizer— Grid Search参数优化                            │
├─────────────────────────────────────────────────────────┤
│                    报告生成层 (cloud_scripts/)                │
│  cloud_utils.py  → retry/log/BJT时间/新鲜度 共享工具          │
│  cloud_morning.py → docs/morning_report.html  08:15 BJT     │
│  cloud_midday.py  → docs/midday_report.html   11:35 BJT     │
│  cloud_closing.py → docs/closing_report.html  15:05 BJT     │
│  cloud_weekly.py  → docs/weekly_report.html   15:45 BJT FRI │
│  docs/report_log.json → 执行日志 (每次生成追加)              │
│  docs/log.html    → 日志查看器                                │
│  generate_dashboard.py → docs/dashboard.html (20层仪表盘)    │
│  rotation/report.py    → docs/quant_daily.html               │
├─────────────────────────────────────────────────────────┤
│                    部署与自动化                             │
│  GitHub Actions: 4个cron工作流 (.github/workflows/)         │
│  GitHub Pages: docs/ → https://typhoon322.github.io/stock-report/ │
│  WorkBuddy: 4个本地自动化 (早盘/午盘/收盘/周报)              │
└─────────────────────────────────────────────────────────┘
```

## 🧠 v2.9 完整模块树 (12层决策链)

```
rotation/                        # 核心引擎包
├── models.py                    # 数据结构 (Stock/Sector/Sentiment)
├── data_fetcher.py              # 数据采集 (AKShare/Sinajs → 模型填充)
├── rti.py / rti2.py / rti3.py   # RTI v1/v2/v3 轮动识别
├── bsi.py                       # BSI 板块强度评分
├── ls.py                        # LS 龙头识别
├── phase.py                     # Phase 周期判断
├── history.py                   # 历史数据缓存 (60天28K条)
├── audit_builder.py             # 训练数据构造器
├── rti_ml.py                    # RTI ML模型 (LogisticRegression)
├── train_pipeline.py            # ML训练管道
├── eval.py                      # 模型评估
├── report.py                    # 量化日报生成
│
├── ci/                          # 🔬 CI Gate 自动验收
│   ├── ci_runner.py             #   主入口 (6指标+drift+决策)
│   ├── metrics.py               #   指标计算 (IC/Precision/HitRate...)
│   ├── thresholds.py            #   合格线定义
│   ├── drift_check.py           #   市场结构漂移检测
│   ├── report_generator.py      #   CI报告 (JSON+Markdown)
│   ├── pr_report.py             #   PR审计报告 (研究员级别)
│   └── github_comment.py        #   GitHub PR评论发布
│
├── evolution/                   # 🧬 模型进化日志
│   ├── log_store.py             #   JSONL持久化
│   ├── tracker.py               #   自动追踪 (CI集成)
│   ├── analyzer.py              #   趋势+Plateau检测
│   ├── diff.py                  #   版本对比+最佳/最差
│   └── timeline.py              #   进化报告生成
│
├── rollback/                    # 🔁 自动回滚免疫系统
│   ├── registry.py              #   模型注册中心
│   ├── rollback_engine.py       #   回滚决策 (6条件)
│   ├── stability_tracker.py     #   稳定性评分
│   └── version_manager.py       #   模型文件归档/恢复
│
├── model_selector/              # 🧠 Model Brain 自适应择优
│   ├── selector.py              #   主决策器 (regime→评分→择优)
│   ├── regime_detector.py       #   市场状态识别 (4 regime)
│   ├── model_score.py           #   5维模型评分
│   └── switch_engine.py         #   防抖切换 (连续3天/差距>10%)
│
├── ensemble/                    # 🗳️ 模型委员会投票
│   ├── voter.py                 #   投票核心+主入口
│   ├── model_pool.py            #   模型池+标准化信号
│   ├── signal_aggregator.py     #   加权聚合+熵计算
│   ├── weight_manager.py        #   动态权重 (regime自适应)
│   └── conflict_resolver.py     #   冲突检测+3策略
│
├── flow/                        # 💰 资金流驱动权重
│   ├── flow_regime.py           #   资金状态识别 (4状态)
│   ├── flow_features.py         #   特征工程 (净流/集中度/分化度)
│   ├── flow_detector.py         #   检测主入口
│   └── flow_weight.py           #   权重计算 (alignment×multiplier)
│
└── smart_money/                 # 🧠 主力行为识别 (认知层)
    ├── microstructure.py        #   10维微观结构特征
    ├── pattern_library.py       #   4种行为规则库
    ├── behavior_score.py        #   行为评分+交易映射
    └── behavior_detector.py     #   主入口+报告
```

---

## 二、目录结构

```
stock-report/
├── rotation/                    # 🔥 核心量化引擎包
│   ├── __init__.py              # 包导出
│   ├── models.py                # 数据类: Stock, Sector, MarketSentiment, DailyReport
│   ├── data_fetcher.py          # 数据采集: API → 模型填充
│   ├── rti.py                   # RTI v1 轮动评分 (5因子)
│   ├── rti2.py                  # RTI v2 资金迁移+四阶段管线
│   ├── rti3.py                  # RTI v3 加权公式 (6因子可调权重)
│   ├── bsi.py                   # BSI 板块强度评分 (0-100)
│   ├── ls.py                    # LS 龙头评分 (0-8)
│   ├── phase.py                 # Phase 周期判断 (5阶段)
│   ├── history.py               # 历史数据缓存 (60天日级)
│   ├── backtest.py              # 回测引擎 (信号→交易→绩效)
│   ├── optimizer.py             # Grid Search 参数优化
│   └── report.py                # 量化日报生成器 (v3)
│   │
│   ├── archive/                  # 📦 Phase I 数据存储 (三层: raw/signal/trade)
│   │   ├── raw_snapshot.py       #   原始市场快照
│   │   ├── signal_snapshot.py    #   策略输出快照
│   │   ├── trade_log.py          #   影子交易日志
│   │   └── runner.py             #   每日归档入口
│   ├── ci/ evolution/ rollback/  # (子包略 — 详见GOVERNANCE.md)
│   ├── model_selector/ ensemble/ #   四引擎
│   ├── flow/ smart_money/        #   资金+主力
│   ├── cost_basis/ breakout/     #   筹码+突破
│   ├── mtf/ meta/ position/      #   周期+决策+仓位
│   ├── execution/ validation/    #   执行+消融
│   ├── weight_learning/          #   动态权重学习
│   └── shadow/                   #   (旧, 已迁移至archive)
│
├── cloud_scripts/               # ☁️ 云端自包含脚本 (fetch+HTML一体)
│   ├── cloud_utils.py           #   共享工具: retry/log/BJT时间/新鲜度
│   ├── cloud_morning.py         #   早盘报告: 美股+亚太+商品+新闻
│   ├── cloud_midday.py          #   午盘报告: 广度+板块+概念+期货+持仓
│   ├── cloud_closing.py         #   收盘报告: 六大指数+板块+期货
│   └── cloud_weekly.py          #   周报: 本周数据仪表盘+持仓
│
├── docs/                        # 📄 GitHub Pages 输出 (自动部署)
│   ├── index.html               #   首页: 报告入口 + 持仓编辑 + 管理面板
│   ├── log.html                 #   日志页: 读取 report_log.json 时间线展示
│   ├── report_log.json          #   执行日志: 每次生成追加 {time,status,errors}
│   ├── dashboard.html           #   仪表盘: 20层量化指标实时展示
│   ├── dashboard_data.json      #   仪表盘底层数据
│   ├── morning_report.html      #   早盘报告
│   ├── midday_report.html       #   午盘报告
│   ├── closing_report.html      #   收盘报告
│   ├── weekly_report.html       #   周报
│   ├── weekly_data.json         #   周数据JSON
│   └── quant_daily.html         #   量化日报 (RTI/BSI/LS)
│
├── .github/workflows/           # 🔄 GitHub Actions cron
│   ├── morning-report.yml       # 8:15 AM BJT (UTC 0:15)
│   ├── midday-report.yml        # 11:35 AM BJT (UTC 3:35)
│   ├── closing-report.yml       # 15:05 PM BJT (UTC 7:05)
│   └── weekly-report.yml        # Fri 15:45 BJT (UTC 7:45)
│
├── history_cache/               # 📦 历史数据缓存 (122个JSON)
│   ├── sector_YYYY-MM-DD.json   # 每日行业板块 (90条/天)
│   ├── concept_YYYY-MM-DD.json  # 每日概念板块 (385条/天)
│   ├── stocks_YYYY-MM-DD.json   # 每日个股 (5528条/天, 只存最近)
│   └── history_meta.json        # 元信息
│
├── portfolio.json               # 📌 持仓配置 (可手动编辑)
├── PRD.md                       # 产品需求文档
├── requirements.txt             # Python依赖
├── fetch_morning.py             # WorkBuddy本地版早盘脚本
├── fetch_data.py                # WorkBuddy本地版午盘脚本
├── fetch_closing.py             # WorkBuddy本地版收盘脚本
└── README_DEV.md                # 📖 本文件 (开发者手册)
```

---

## 三、核心引擎详解

### 3.1 RTI — Rotation Timing Indicator (轮动识别)

**RTI v3 公式:**
```
RTI = w1*FlowShift + w2*Acceleration + w3*LowBaseBreakout 
    + w4*SectorExpansion + w5*NewsDecoupling + w6*OldSectorDecay

默认权重: [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
```

| 因子 | 含义 | 得分逻辑 |
|------|------|---------|
| FlowShift | 资金迁移强度 | 旧主线流出 + 新板块流入 / 总流动 |
| Acceleration | 资金加速度 | 今日流入 - 昨日流入 |
| LowBaseBreakout | 低位突破 | 5日涨幅<大盘 + 今日>1.5% + 无新闻 |
| SectorExpansion | 扩散能力 | 上涨比例×6 + 涨停数×0.8 |
| NewsDecoupling | 无新闻驱动 | 无新闻+异动 = 自然轮动信号 |
| OldSectorDecay | 旧主线衰减 | 龙头滞涨+量缩+涨停断档 |

**判定阈值:**
- RTI ≥ 4.5 → 新主线形成 (new_mainline)
- RTI ≥ 3.0 → 轮动试探 (rotation_probing)
- RTI < 3.0 → 无轮动 (no_rotation)

**四阶段管线 (RTI v2, 保留兼容):**
1. Stage 1: 异常扫描 — 低位+放量+无新闻
2. Stage 2: 试探确认 — ≥2只个股异动, 小范围上涨
3. Stage 3: 扩散确认 — ≥3只涨+涨停+持续放量
4. Stage 4: 主线确认 — 龙头+Top10+资金持续

---

### 3.2 BSI — Board Strength Index (板块强度)

**公式:**
```
BSI = percentile_rank(涨幅) × 20
    + min(涨停数, 5) × 3
    + clamp(量变化, 0.5, 3.0) × 5
    + clamp(资金流入量级, 0, 10) × 2
    + 连续3日强度加分(+5)
```

**判定:**
- BSI > 30 → 🔥 强势板块
- BSI 15-30 → 🟡 中等轮动
- BSI < 15 → ⚪ 弱势

---

### 3.3 LS — Leader Score (龙头评分)

**公式 (0-8):**
```
LS = 2×(最早启动) + 2×(突破20日高点) + 1×(量比>2) 
   + 2×(板块涨幅第一) + 1×(资金集中度>50%分位)
```

**判定:**
- LS > 7 → 🏆 龙头 (可介入)
- LS 5-7 → 📈 跟随 (观察)
- LS < 5 → ⚪ 后排 (不推荐)

---

### 3.4 Phase — 市场周期判断

**输入维度:** 涨跌比 + 涨停数 + 连板高度 + 资金流向 + 板块扩散度

| Phase | 涨跌比 | 涨停 | 策略 | 仓位 |
|-------|--------|------|------|------|
| ❄️ 冰点期 | <0.3 | <20 | 防守 | 0-20% |
| 🔍 试探期 | 0.3-0.5 | 20-50 | 试探 | 20-50% |
| 🔄 轮动期 | 0.4-0.7 | 30-80 | 进攻 | 50-80% |
| 🚀 主升期 | >0.5 | >50 | 主升 | 80-100% |
| 💨 退潮期 | <0.4 | <30 | 退出 | 减仓 |

---

### 3.5 Backtest Engine (回测引擎)

**交易规则:**
- 开仓: RTI ≥ threshold (默认3.0)
- 持有: 5/10/20/30天 (可配)
- 平仓: RTI < 2 或 LS下降 或 进入退潮期

**输出指标 (6项):**
| 指标 | 说明 |
|------|------|
| total_trades | 总交易次数 |
| win_rate | 胜率 (%) |
| avg_return | 平均收益率 |
| max_drawdown | 最大回撤 |
| sharpe_proxy | 近似夏普比率 |
| signal_accuracy | 信号准确率 |

---

### 3.6 Optimizer (参数优化器)

**方法:** Grid Search 网格搜索  
**搜索空间:** 6个权重 × 5个阈值 ≈ 500-1000组合  
**目标函数:** `Score = avg_return×2 + signal_accuracy/10 + win_rate/20 - |min_return|×0.5`

---

## 四、数据源详解

### 4.1 API映射表

| 需要的数据 | 函数 | 源 | 稳定性 |
|-----------|------|-----|--------|
| 全市场个股 (5528只) | `ak.stock_zh_a_spot()` | Sina | ⭐⭐⭐⭐⭐ |
| 全市场个股 (字段全) | `ak.stock_zh_a_spot_em()` | 东方财富 | ⭐⭐⭐ |
| 行业板块行情 | `ak.stock_fund_flow_industry()` | 东方财富 | ⭐⭐⭐⭐ |
| 概念资金流向 | `ak.stock_fund_flow_concept()` | 东方财富 | ⭐⭐⭐⭐ |
| 美股三大指数 | `ak.index_us_stock_sina()` | Sina | ⭐⭐⭐⭐⭐ |
| 恒生指数 | Sinajs `int_hangseng` | Sina实时 | ⭐⭐⭐⭐⭐ |
| 日经225 | Sinajs `int_nikkei` | Sina实时 | ⭐⭐⭐⭐⭐ |
| 上证/深证/创业板/科创50 | Sinajs `s_sh000001`等 | Sina实时 | ⭐⭐⭐⭐⭐ |
| 全球期货 | `ak.futures_global_spot_em()` | 东方财富 | ⭐⭐⭐⭐ |
| 外汇牌价 | `ak.currency_boc_sina()` | 中行 | ⭐⭐⭐⭐⭐ |
| 全球新闻 | `ak.stock_info_global_sina()` | Sina | ⭐⭐⭐⭐⭐ |
| 板块成分股 | `ak.stock_board_industry_cons_em()` | 东方财富 | ⭐⭐⭐ |

### 4.2 期货合约代码修正

| 品种 | 代码前缀 | 示例 | 非NaN过滤 |
|------|---------|------|----------|
| COMEX黄金 | GC | GC27Q = 4206 | ✅ |
| NYMEX原油 | CL | CL27V = 66.36 | ✅ |
| COMEX铜 | HG | HG27U = 6.376 | ✅ |
| COMEX白银 | SI | SI27U = 60.12 | ✅ |
| 天然气 | NG | NG27V = 3.41 | ✅ |
| 富时A50 | CN (非NaN) | CN26N = 15687 | ✅ |
| 布伦特原油 | B | B27X = 70.45 | ✅ |

### 4.3 数据源Fallback策略

个股全量: 东方财富(主) → 新浪(备) 双源并行  
主要指数: Sinajs 实时 (最稳定)  
全球指数: 东方财富(主) → yfinance(备)  
日韩: Sinajs `int_nikkei` (KOSPI用yfinance)

---

## 五、自动化调度

### 5.1 GitHub Actions (云端, 无需电脑开机)

| 工作流 | 文件 | Cron (UTC) | BJT | 输出 |
|--------|------|------------|-----|------|
| Morning | `morning-report.yml` | `15 0 * * 1-5` | 8:15 | morning_report.html |
| Midday | `midday-report.yml` | `35 3 * * 1-5` | 11:35 | midday_report.html |
| Closing | `closing-report.yml` | `5 7 * * 1-5` | 15:05 | closing_report.html |
| Weekly | `weekly-report.yml` | `45 7 * * 5` | 15:45 Fri | weekly_report.html + weekly_data.json |

### 5.2 WorkBuddy 自动化 (电脑开机时运行)

| 名称 | 时间 | ID | 模式 |
|------|------|-----|------|
| 早盘报告 | 8:15 AM | `automation-1782372617267` | 云端URL+本地fallback |
| 午盘分析 | 11:35 AM | `automation-1782300903285` | 云端URL+本地fallback |
| 收盘总结 | 15:05 PM | `automation-1782377595324` | 云端URL+本地fallback |
| 周报深度 | 周五 16:00 | `automation-1782385582451` | LLM深度分析 |

### 5.3 部署方式

GitHub Pages 从 `main` 分支 `/docs` 文件夹自动部署:
- 首页: `https://typhoon322.github.io/stock-report/`
- 每个 `docs/*.html` 文件都可以直接访问

---

## 六、如何本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行量化日报 (全引擎)
python -c "from rotation.report import generate_daily_report, report_to_html
r = generate_daily_report()
open('docs/quant_daily.html','w').write(report_to_html(r))"

# 3. 运行早/午/收盘报告
python cloud_scripts/cloud_morning.py
python cloud_scripts/cloud_midday.py
python cloud_scripts/cloud_closing.py

# 4. 运行周报
python cloud_scripts/cloud_weekly.py

# 5. 采集历史数据 (回测前必须)
python -c "from rotation.history import build_history; build_history(days=120)"

# 6. 运行回测
python -c "from rotation.history import build_history; from rotation.backtest import BacktestEngine
h = build_history(60); e = BacktestEngine(h); print(e.run(hold_days=10))"

# 7. 参数优化
python -c "from rotation.history import build_history; from rotation.optimizer import quick_optimize
h = build_history(60); print(quick_optimize(h))"
```

---

## 七、如何扩展

### 7.1 添加新的数据源

在 `rotation/data_fetcher.py` 添加新函数，返回 `List[Sector]` 或 `List[Stock]`。

### 7.2 调整 RTI 权重

修改 `rotation/rti3.py` 中的 `DEFAULT_WEIGHTS`，或运行时传入:
```python
from rotation.rti3 import compute_rti3
score, signal, components = compute_rti3(..., weights={"w1_flow_shift": 0.30, ...})
```

### 7.3 修改回测策略

修改 `rotation/backtest.py` 中的 `BacktestEngine.run()` 的开仓/平仓逻辑。

### 7.4 添加新的日报类型

在 `cloud_scripts/` 下创建新的 `cloud_xxx.py`，参考现有脚本的 fetch + HTML生成模式。添加到 `.github/workflows/` 对应的 cron 文件。

### 7.5 更新持仓

编辑 `portfolio.json` 或通过首页 Web UI 操作（localStorage 持久化）。

---

## 八、关键设计决策

1. **为什么用 Sina 而不是东方财富？** — Sina `hq.sinajs.cn` 实时API最稳定，东方财富偶发断连。
2. **为什么分 cloud_scripts 和 rotation？** — `cloud_scripts/` 是自包含脚本(GitHub Actions跑)，`rotation/` 是引擎包(WorkBuddy跑)。
3. **为什么 GitHub Pages 用 /docs 而不是 /reports？** — GitHub Pages 只支持 `/root` 和 `/docs` 两个文件夹。
4. **为什么 LS 龙头经常为0？** — 板块成分股API `stock_board_industry_cons_em()` 偶发超时。在牛市时段获取会好很多。
5. **KOSPI 为什么经常缺？** — Sina不支持KOSPI实时，yfinance被限频。用日经225作为亚太代理。

---

## 九、PRD对照

完整的工程设计文档见仓库根目录 `PRD.md`，包含:
- Level 1-4 自检标准
- RTI 2.0/3.0 详细公式
- 轮动识别管线设计
- 数据结构和输出规范
- 下一步升级路线 (RTI v4 概率模型、龙头生命周期)

---

## 十、待优化项

- [ ] 行业板块API偶发超时，影响龙头识别数据管道
- [ ] 主要指数历史数据需改用 Sina 源 (当前东方财富偶发断连)
- [ ] KOSPI 需要更稳定的数据源
- [ ] Dashboard 成本结构和突破分析仍用 FALLBACK 数据，需接入实时API

---

## 十一、Phase I 数据存储五条强制规则

> 适用于: rotation/archive/ 三层存储系统

1. **所有决策必须可回放（replayable）** — 每份 snapshot 必须包含当日全部可观测变量
2. **不允许只存HTML** — HTML 仅用于展示，JSON 是唯一事实源
3. **不允许丢失 signal snapshot** — 每日必须产出 `archive/signal/YYYY-MM-DD.json`
4. **不允许修改历史数据** — 已归档文件为不可变记录
5. **不允许使用未结构化日志作为训练数据** — 所有训练数据必须来自结构化 JSON

### 三层存储

| 目录 | 内容 | 用途 |
|------|------|------|
| `archive/raw/` | 原始市场快照 | 回测核心源 |
| `archive/signal/` | 策略输出快照 | weight learning 核心源 |
| `archive/trade/` | 影子交易日志 | PnL 验证核心源 |

GitHub Actions 入口: `python -m rotation.archive.runner` (midday + closing 两个 workflow 均执行)

---
## 十二、云端报告系统设计规则 (v2.21)

> 适用于: cloud_scripts/ 所有脚本

| # | 规则 | 说明 |
|---|------|------|
| 1 | RETRY | 所有 API 调用经 `retry_with_backoff(name, max_retries=2)` 包装，指数退避 |
| 2 | LOG | `write_report_log(name, status, errors)` → `docs/report_log.json` |
| 3 | TIME | 时间戳统一 `北京时间 2026年06月26日 18:37`，使用 `bjt_format()` |
| 4 | SIGN | 数字格式统一 `{val:+.2f}`，禁止硬编码 `+{val}` → 产生 `+-` |
| 5 | COLOR | 每列独立着色 `cl(val)` / `_color(val)`，不按表格区块统色 |
| 6 | HEADER | 标题动态：正涨幅 → "领涨 Top 5"，全跌 → "抗跌 Top 5" |
| 7 | SAFETY | 数据初始化 `{"up":[],"down":[]}` 不能空 `{}`，HTML 用 `.get()` 兜底 |
| 8 | FRESHNESS | 午盘三级：FRESH/DELAYED/STALE，≥15:00 跳过资金流数据 🆕 |

### 午盘数据新鲜度分级
| 等级 | 时间范围 | 行为 |
|------|---------|------|
| FRESH | 9:30-13:00 BJT | 正常采集全部数据 |
| DELAYED | 13:00-15:00 / <9:30 | 采集全部 + 标注警告 |
| STALE | ≥15:00 BJT | 跳过行业/概念资金流；保留广度/期货/持仓 |

---

## 十二、Gitee Go 国内部署 (v2.21)

### 为什么需要

GitHub Actions 从美国机房访问东方财富/新浪 API 延迟高、频繁 RemoteDisconnected。
Gitee Go 在国内运行，API 延迟 < 100ms，成功率 > 95%。

### 部署步骤

```bash
# 1. 在 Gitee 创建仓库 → 从 GitHub 导入
#    https://gitee.com/ → 新建仓库 → 导入已有仓库
#    输入: https://github.com/typhoon322/stock-report.git

# 2. 推送 .gitee/giteeci.yml 到 Gitee 仓库
git remote add gitee https://gitee.com/你的用户名/stock-report.git
git push gitee main

# 3. 开启 Gitee Go
#    仓库 → 服务 → Gitee Go → 开启

# 4. 开启 Gitee Pages
#    仓库 → 服务 → Gitee Pages → 部署目录选 docs/ → 开启
#    访问: https://你的用户名.gitee.io/stock-report/

# 5. 验证
#    Gitee Go → 构建历史 → 查看流水线日志
```

### 与 GitHub Actions 对比

| | GitHub Actions | Gitee Go |
|---|---|---|
| 调度 | 4 个独立 workflow | 1 个统一 pipeline |
| Runner | Ubuntu (美国) | Docker (中国) |
| API 延迟 | ~500ms | ~50ms |
| 免费额度 | 2000min/月 | 免费 |
| Pages | github.io | gitee.io |

### 配置文件

`.gitee/giteeci.yml` — 统一 pipeline，根据 cron 触发时间自动选择生成对应报告。
4 个 cron 全覆盖: 8:15早盘 / 11:35午盘 / 15:05收盘 / 周五15:45周报。
- [ ] 添加自动学习机制: 每次回测后自动更新权重并应用于新日报

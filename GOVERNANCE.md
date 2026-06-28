# 📌 Work Buddy 标准执行指引 v1.3

> 适用于：Stock-Report 量化系统所有开发任务  
> 最后更新：2026-06-28 · Phase I 数据采集进行中 · v2.22  
> 目标：保证所有模块可训练 / 可回测 / 可演进

---

## 0. 总原则

### ❌ 禁止行为

- 只做"功能实现"，不做验证
- 使用未来数据（lookahead bias）
- 没有 label 的模型训练
- 没有回测就上线策略
- 手动调权重替代学习

### ✅ 必须遵守

- 所有模型必须可回测
- 所有特征必须 T 时刻可获得
- 所有输出必须有"效果指标"
- 所有模块必须可重复运行（deterministic）
- 每个模块必须有"验证脚本"

---

## 1. 标准开发流程（5步）

任何新功能 = 必须走 5 步:

| Step | 名称 | 输出 |
|------|------|------|
| 1 | 数据定义 | data schema（字段+类型） |
| 2 | 特征工程 | feature list + 解释 |
| 3 | 模型/逻辑实现 | rule-based 或 ML-based 代码 |
| 4 | 回测验证（强制） | IC / Precision@TopK / 收益分位 / 命中率 |
| 5 | 上线接入 | 接入 report + daily pipeline + 日志 |

---

## 2. 模块标准结构

```
rotation/<module_name>.py
rotation/eval/<module_name>_eval.py
```

每个模块必须提供：
1. 输入说明
2. 输出说明
3. 特征定义（如有）
4. 时间依赖说明
5. 回测方法
6. 失败模式分析

---

## 3. ML 模块统一规范

- **train/test split**: 必须按时间切分（不能随机）
- **label**: 必须 = 未来 1-3 天真实市场行为，禁止主观标注
- **输出**: 概率值(0~1) + 分位排名 + 稳定性指标

---

## 4. 回测统一标准

- A. 分层收益 (Top10% / 10-30% / Middle / Bottom)
- B. IC 曲线 (rolling 5d/10d/20d)
- C. 命中率 (TP / all predicted positives)
- D. 失败模式分析 (哪种市场结构失效？)

---

## 5. 模型生命周期

| 状态 | 含义 |
|------|------|
| v0 | 规则系统 |
| v1 | ML初版 |
| v1.5 | 回测验证完成 |
| v2 | 可实盘使用 |
| v3 | 自适应系统 |

**触发重训**: IC下降>20% OR Top10%收益消失 OR 市场结构drift

---

## 6. 三条交易级原则

1. **宁可少信号，不要错信号** — precision > recall
2. **所有"强信号"必须可回测证明** — 不存在"看起来合理"
3. **市场变化优先于模型** — 模型只是历史总结，不是规则

---

## 7. 当前系统定位

```
RTI v1 (rule + ML hybrid)          ✅
RTI v1.5 (backtest validated)      ✅
RTI v2   (ML dominant)             ✅
RTI v3   (regime adaptive)         ⬜

系统治理层:
v2.5  CI Gate + PR Audit            ✅
v2.6  Model Evolution Log           ✅
v2.7  Auto Rollback Immune System   ✅
v2.8  Model Brain (自适应择优)        ✅
v2.9  Ensemble Voting (模型委员会)    ✅
v2.10 Flow-Weighted Ensemble        ✅
v2.11 Smart Money Behavior          ✅
v2.12 Cost Basis Reconstruction      ✅
v2.13 Breakout Authenticity          ✅
v2.14 MTF Consistency                ✅
v2.15 Meta Score Engine              ✅
v2.16 Position Sizing                ✅
v2.17 Execution Engine               ✅
v2.18 Ablation Engine                ✅
v2.19 Dynamic Weight Learning        ✅
v2.20 Phase I: LS修复+Shadow Mode+Archive ✅

当前阶段: 🧪 Shadow Trading + Data Truth Phase
目标: 30天稳定运行 → 积累可训练数据集

22层最终管线:
commit → CI Gate → backtest → metrics → evolution log → rollback
  → model selector → flow ensemble → smart money → cost basis
  → breakout → MTF → meta score → position sizing → execution
  → ablation → weight learning → ARCHIVE (raw/signal/trade) → Phase II
```

---

## 8. 默认任务模板

```
任务名称：xxx

目标：做什么能力

必须包含：
- 数据定义
- 特征设计
- 模型或规则实现
- 回测验证（必须）
- failure analysis

输出：
- 可运行代码
- eval报告
- backtest结果

禁止：
- 使用未来数据
- 无验证上线
- 黑盒逻辑
```

---

---

## 9. 升级路线

| 优先级 | 模块 | 状态 |
|--------|------|------|
| 🥇 | RTI backtest + IC 系统 | ✅ |
| 🥈 | drift detection | ✅ |
| 🥉 | 龙头链路模型（板块→交易点） | ✅ LS已修复 |
| 🚀 | CI Gate + PR Audit + Evolution Rollback | ✅ |
| 🧪 | Phase I: LS修复 + Archive + Shadow | ✅ v2.20 |
| ☁️  | Cloud Report System: retry/log/BJT/新鲜度/log页面 | ✅ v2.21 |
| 📦 | Phase II: Auto Training + Module Pruner | ✅ v2.22 (设计完成,30天后触发) |

---

## 10. Phase I 数据存储五条强制规则

> ⚠️ Phase I 期间必须遵守，违反即不可用于后续训练

1. **所有决策必须可回放（replayable）** — 每份快照包含当日全部可观测变量
2. **不允许只存HTML** — HTML仅展示，JSON是唯一事实源
3. **不允许丢失signal snapshot** — 每日必须产出 `archive/signal/YYYY-MM-DD.json`
4. **不允许修改历史数据** — 已归档文件为不可变记录
5. **不允许使用未结构化日志作为训练数据** — 所有训练数据来自结构化JSON

### 三层存储 (v2.20新增)

| 目录 | 入口 | 用途 |
|------|------|------|
| `archive/raw/` | raw_snapshot.py | 原始市场快照 → 回测核心源 |
| `archive/signal/` | signal_snapshot.py | 策略输出快照 → weight learning 核心源 |
| `archive/trade/` | trade_log.py | 影子交易日志 → PnL 验证核心源 |

**执行入口:** `python -m rotation.archive.runner` (midday + closing 两个 workflow 均触发)
**时区:** UTC+8 统一

### Phase I 期间禁止
- 新增功能模块
- Dashboard 数据用于交易决策
- 手动调权重
- 频繁切换模型版本

### 云雾报告系统 (v2.21 — 2026-06-26)

| 组件 | 文件 | 说明 |
|------|------|------|
| 共享工具 | `cloud_scripts/cloud_utils.py` | retry_with_backoff / write_report_log / bjt_format |
| 执行日志 | `docs/report_log.json` | 每次报告生成后追加 {time, report, status, errors} |
| 日志查看 | `docs/log.html` | 独立页面，读取 report_log.json 按时间线展示 |
| 早盘报告 | `cloud_scripts/cloud_morning.py` | 08:15 → docs/morning_report.html |
| 午盘报告 | `cloud_scripts/cloud_midday.py` | 11:35 → docs/midday_report.html |
| 收盘报告 | `cloud_scripts/cloud_closing.py` | 15:05 → docs/closing_report.html |
| 周报 | `cloud_scripts/cloud_weekly.py` | 周五 15:45 → docs/weekly_report.html |

**关键设计规则 (v2.21 新增):**
1. **RETRY**: 所有 API 调用经 `retry_with_backoff(func, name, max_retries=2)` 包装，指数退避
2. **LOG**: 每次运行必须调用 `write_report_log(name, status, errors)` 记录到 `docs/report_log.json`
3. **TIME**: 所有时间戳统一 `北京时间 2026年06月26日 18:37` 格式
4. **SIGN**: 数字格式统一 `{val:+.2f}`（Python 格式化符号，禁止硬编码 `+{val}` → 产生 `+-` 错误）
5. **COLOR**: HTML 每列独立着色（`_color(val)` / `cl(val)`），不按表格区块统色
6. **HEADER**: 行业标题动态切换：有正涨幅 → "🔥 领涨 Top 5"，全跌 → "🔻 抗跌 Top 5"
7. **SAFETY**: 数据初始化必须为完整结构 `{"up":[],"down":[]}`，禁止空 `{}`，HTML 用 `.get()` 兜底
8. **FRESHNESS**: 午盘脚本三级新鲜度检查 🆕
   - FRESH (9:30-13:00): 正常采集全部数据
   - DELAYED (13:00-15:00): 采集全部 + 标注 "资金流可能含下午数据"
   - STALE (≥15:00): 跳过行业/概念资金流（不可信），保留广度/期货/持仓
   - TOO_EARLY (<9:30): 标注 "市场未开盘"

### Phase II 自动训练+剪枝系统 (v2.22 — 30天后触发)

**触发条件**: 归档交易日 ≥ `min_trading_days` (默认20天，理想30天)

**四步流水线** (`rotation/phase2/runner.py`):

| 步骤 | 模块 | 输入 | 输出 |
|------|------|------|------|
| 1 | PnL Calculator | archive/signal/*.json + archive/raw/*.json | 每日真实PnL、模块归因 |
| 2 | Auto Trainer | 真实PnL数据 + 当前权重 | 学习后的权重、模块绩效 |
| 3 | Module Pruner | 模块PnL + 权重 | 剪除决策、剪枝报告 |
| 4 | Report + Save | 完整分析结果 | HTML报告 + 权重落地 |

**权重学习**: effectiveness = win_rate × max(avg_pnl × 50, 0.01), 体制修正, 平滑更新 new = old + LR×(learned−old)

**剪枝规则**（保守，默认最多剪2个）:
- PnL < -5bps × 连续15天 → 标记
- 胜率 < 30% 且交易≥10天 → 标记
- Sharpe < -0.5 且样本≥15天 → 标记
- 剪除=权重归零，代码保留，可随时恢复

**执行入口**: `python -m rotation.phase2.runner`
**HTML报告**: `docs/phase2_report.html`
**JSON数据**: `docs/phase2_data.json`

---

## 11. CI Gate 自动验收 (v2.5)

每次 PR 涉及 `rotation/` 或 `cloud_scripts/` 变更时:

1. GitHub Actions 自动运行 CI Gate
2. 回测 + 6项指标评估 + drift检测
3. 自动生成"研究员级别"审计报告
4. 写回 PR 评论，包含:
   - 📈 Performance (IC/Precision/Sharpe/MaxDD/Alpha)
   - 🧭 Signal Quality (假阳性率/稳定性)
   - 🧠 Drift Analysis (市场结构状态)
   - ⚠️ Key Observations (自动洞察)
   - 🟢 Decision (APPROVED/REJECTED + 修复建议)

**PR 决策流程:**
```
code commit → CI Gate → backtest → metrics → PR report → EVOLUTION LOG → trend analysis
```

---

## 12. Model Evolution Log (v2.6)

每次 CI 运行自动记录模型进化轨迹到 `rotation/evolution/logs/evolution_log.jsonl`。

**核心能力:**
- 📈 追踪 IC/Precision/MaxDD 随时间变化
- 🏆 自动识别最佳改进和最差退化
- ⚠️ Plateau 检测 (IC 增长停滞)
- 📊 进化时间线表格

**三个关键问题:**
1. 我改了什么？ → `change_summary` + `change_type`
2. 模型变好了还是变差了？ → `ic_delta` + `precision_delta`
3. 为什么？ → `diff.py` 归因分析

**报告:** `rotation/evolution/reports/evolution_report.md`

---

## 13. 核心模块速览 (v2.10-v2.21)

| v | 模块 | 一句话 | 路径 |
|----|------|--------|------|
| v2.10 | Flow-Weighted Ensemble | 资金流驱动投票权重, distribution期RTI降权25% | `rotation/flow/` |
| v2.11 | Smart Money Behavior | OHLCV微观结构识别4种主力行为 | `rotation/smart_money/` |
| v2.12 | Cost Basis Reconstruction | Volume Profile筹码成本区重建 | `rotation/cost_basis/` |
| v2.13 | Breakout Authenticity | 5因子真假突破评分(真/诱多/失败) | `rotation/breakout/` |
| v2.14 | MTF Consistency | 三周期趋势一致性过滤 | `rotation/mtf/` |
| v2.15 | Meta Score Engine | 6信号加权 → LONG/HOLD/SHORT | `rotation/meta/` |
| v2.16 | Position Sizing | 动态仓位: strength×confidence×risk | `rotation/position/` |
| v2.17 | Execution Engine | 滑点+拆单+流动性建模 | `rotation/execution/` |
| v2.18 | Ablation Engine | 逐个关闭模块 → 边际贡献 | `rotation/validation/` |
| v2.19 | Dynamic Weight Learning | PnL反哺权重, 闭合学习环 | `rotation/weight_learning/` |
| v2.20 | Phase I Archive | 三层存储 + LS修复 + Dashboard标注 | `rotation/archive/` |
| v2.21 | Cloud Report System | retry/log/BJT时间/新鲜度分级/log页面 | `cloud_scripts/` |
| v2.22 | Phase II Auto Trainer | 30天PnL→权重学习→剪枝→报告 | `rotation/phase2/` |

---

## 14. 会话规范 (完整闭环)

1. 所有新功能开发 → 遵循 §1 五步流程
2. 所有 ML 模块 → 遵循 §3 训练规范
3. 所有策略上线前 → CI Gate §11
4. 所有变更 → 自动记录 Evolution Log §12
5. 所有新模块 → 更新本文档 + README_DEV.md

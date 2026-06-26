# Stock-Report 量化策略系统 PRD

> 版本: v1.0 | 日期: 2025-06-25 | 从数据汇总升级到中期轮动策略系统

---

## 一、目标升级

在现有日报（数据汇总）基础上新增四个核心能力：

| 模块 | 代号 | 目标 |
|------|------|------|
| 板块轮动识别引擎 | **RTI** | 提前1-3天发现新主线，识别"资金迁移" |
| 板块强度评分 | **BSI** | 量化板块强弱，区分主升/轮动/弱势 |
| 龙头识别模型 | **LS** | 板块内最强个股，绝不推荐后排 |
| 市场周期判断 | **Phase** | 冰点→试探→轮动→主升→退潮 |

---

## 二、数据结构

### 2.1 板块对象 (Sector)
```python
@dataclass
class Sector:
    name: str               # "AI算力"
    change_1d: float        # 今日涨幅%
    change_3d: float        # 3日涨幅%
    change_5d: float        # 5日涨幅%
    volume_change: float    # 成交量变化(相对5日均值)
    num_stocks_up: int      # 上涨家数
    num_limit_up: int       # 涨停家数
    net_money_flow: float   # 主力净流入(亿)
    leader_stock: str       # 龙头代码
    stocks: List[Stock]     # 成分股
    # 衍生字段
    is_low_position: bool   # 是否为低位板块
    has_news_driver: bool   # 是否有明显新闻驱动
    rti_score: int = 0      # RTI评分
    bsi_score: int = 0      # BSI评分
```

### 2.2 个股对象 (Stock)
```python
@dataclass
class Stock:
    code: str               # "600XXX"
    name: str               # "xxx"
    change_pct: float       # 涨跌幅%
    volume_ratio: float     # 量比
    is_limit_up: bool       # 是否涨停
    is_breakout: bool       # 是否突破前高
    industry: str           # 所属行业
    money_flow: float       # 资金净流入
    is_early_starter: bool  # 是否板块内最早启动
    leader_score: int = 0   # LS评分
```

### 2.3 市场情绪 (Sentiment)
```python
@dataclass
class MarketSentiment:
    limit_up_count: int     # 涨停家数
    fall_limit_count: int   # 跌停家数
    market_breadth: float   # 上涨占比 (0-1)
    up_down_ratio: float    # 涨跌比
    consecutive_board: int  # 最高连板高度
    index_trend: str        # 指数趋势描述
    risk_level: str         # low/medium/high/extreme
    phase: str              # 当前周期
```

---

## 三、核心算法

### 3.1 轮动识别引擎 (RTI — Rotation Timing Indicator)

**核心公式：**
```
RTI = sum([
    1 if 低位板块(chg_5d < 大盘) and 今日涨幅 > 2% else 0,
    1 if 成交量放大 > 1.5倍均值 else 0,
    1 if 板块首次异动股 >= 3 else 0,
    1 if 无明显新闻驱动 else 0,
    1 if 涨停 >= 1 else 0,
])
```

**判定逻辑：**
| RTI | 状态 | 含义 |
|-----|------|------|
| >= 4 | 🔥 潜在新主线 | 高概率轮动 |
| >= 3 | 🟡 轮动试探 | 关注，等待确认 |
| < 3 | ⚪ 无轮动 | 不关注 |

**关键原则（必须遵守）：**
> 真正的价值在 **"无新闻 + 放量 + 低位异动"**。不是热点板块，而是刚开始动的板块。

### 3.2 板块强度评分 (BSI — Board Strength Index)

**计算公式：**
```
BSI = (
    percentile_rank(chg_1d, 全板块) * 20 +
    min(num_limit_up, 5) * 3 +
    clamp(volume_change, 0.5, 3.0) * 5 +
    clamp(net_money_flow_magnitude, 0, 10) * 2 +
    persistence_bonus  # 连续3日强度加分：+5
)
```

**判断阈值：**
| BSI | 状态 |
|-----|------|
| > 30 | 🔥 强势板块 |
| 15-30 | 🟡 中等轮动 |
| < 15 | ⚪ 弱势 |

### 3.3 龙头识别模型 (LS — Leader Score)

**计算公式：**
```
LS = sum([
    2 if 板块内最早启动(前3日涨幅领先) else 0,
    2 if 今日突破20日高点 else 0,
    1 if 量比 > 2.0 else 0,
    2 if 板块内涨幅第一 else 0,
    1 if 资金流入集中度 > 50%分位 else 0,
])
```

**判断：**
| LS | 状态 | 建议 |
|----|------|------|
| > 7 | 🏆 龙头 | 可介入 |
| 5-7 | 📈 跟随 | 观察 |
| < 5 | ⚪ 后排 | 不建议 |

### 3.4 市场周期判断 (Phase Detection)

**输入维度：**
```
phase_score = {
    "breadth":      market_breadth,
    "limit_up":     limit_up_count,
    "consecutive":  max_consecutive_board,
    "flow":         net_inflow_direction,
    "diffusion":    num_sectors_rising / total_sectors,
}
```

**周期定义：**
| Phase | 涨跌比 | 涨停 | 连板 | 资金 | 板块扩散 | 策略 |
|-------|--------|------|------|------|----------|------|
| ❄️ 冰点期 | < 0.3 | < 20 | < 3 | 大幅流出 | < 0.2 | 0-20%仓位 |
| 🔍 试探期 | 0.3-0.5 | 20-50 | 3-5 | 小幅流出 | 0.2-0.4 | 20-50% |
| 🔄 轮动期 | 0.4-0.7 | 30-80 | 4-7 | 分化流入 | 0.3-0.6 | 50-80% |
| 🚀 主升期 | >0.5 | >50 | >5 | 大幅流入 | >0.5 | 80-100% |
| 💨 退潮期 | <0.4 | <30 | <4 | 转为流出 | 萎缩 | 减仓 |

---

## 四、日报生成规范（重写版）

每份日报必须输出以下结构：

```
# 📊 市场日报 2025-06-25

## 1️⃣ 市场状态
| 指标 | 值 |
|------|-----|
| 当前周期 | 轮动期 |
| 情绪 | 偏强 |
| 风险等级 | medium |
| 仓位建议 | 50-80% |

## 2️⃣ 板块轮动分析（核心）
### 🔥 潜在新主线 (RTI ≥ 4)
| 板块 | RTI | 阶段 | 龙头 | 理由 |
|------|-----|------|------|------|

### 🟡 轮动试探 (RTI = 3)
| 板块 | RTI | 阶段 |
|------|-----|------|

## 3️⃣ 强势板块 (BSI > 30)
| 板块 | BSI | 龙头 | 主升? |
|------|-----|------|-------|

## 4️⃣ 龙头股池 (LS ≥ 5)
| 代码 | 名称 | LS | 板块 | 可介入? |
|------|------|----|------|----------|

## 5️⃣ 风险提示
- 退潮信号: yes/no
- 主线切换: yes/no
- 减仓建议: yes/no

## 6️⃣ 中期策略
| 维度 | 建议 |
|------|------|
| 策略 | 主升 / 试探 / 防守 |
| 仓位 | 50-80% |
| 重点板块 | xxx, xxx |
| 回避板块 | xxx |
```

---

## 五、实现路线图

### Phase 1: 数据层 (2-3h)
- [ ] `rotation/sector.py` — Sector/Stock/Sentiment 数据类
- [ ] `rotation/data_fetcher.py` — 从 AKShare/Sinajs 采集板块+个股全量数据
- [ ] `rotation/history.py` — 5日历史数据缓存

### Phase 2: 算法层 (3-4h)
- [ ] `rotation/rti.py` — RTI 轮动评分
- [ ] `rotation/bsi.py` — BSI 板块强度
- [ ] `rotation/ls.py` — LS 龙头评分
- [ ] `rotation/phase.py` — 市场周期判断

### Phase 3: 输出层 (2h)
- [ ] `rotation/report.py` — 整合所有评分，生成结构化日报
- [ ] `cloud_scripts/cloud_daily_v2.py` — 新版日报脚本（替代旧版）
- [ ] 更新 GitHub Actions workflow

### Phase 4: 周报升级 (1h)
- [ ] 周报增加轮动历史追踪（本周每日 RTI/BSI 变化趋势）

---

## 六、关键原则（必读）

1. **低位 + 异动 + 无新闻 = 轮动信号** — 不是涨幅榜
2. **永远不推荐后排股** — 龙头优先级最高
3. **提前1-3天发现新主线** — 核心价值在识别"轮动早期"
4. **资金流向要结合方向性** — 不是只看金额，要看"新方向"vs"旧主线"
5. **诚实标注不确定性** — 不确定就是不确定，不要假装确定

---

## 七、数据源映射

| 需要的数据 | API | 函数 |
|-----------|-----|------|
| 全市场个股 | AKShare/Sina | `stock_zh_a_spot()` |
| 行业板块行情 | AKShare | `stock_fund_flow_industry()` |
| 概念板块行情 | AKShare | `stock_fund_flow_concept()` |
| 板块成分股 | AKShare | `stock_board_industry_cons_em()` |
| 市场广度 | westock-data | `changedist` |
| 连板高度 | westock-data | `hot board` |
| 3日/5日历史 | AKShare | `stock_zh_a_hist()` |
| 新闻驱动检测 | AKShare | `stock_info_global_sina()` |

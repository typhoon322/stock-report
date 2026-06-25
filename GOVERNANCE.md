# 📌 Work Buddy 标准执行指引 v1.1

> 适用于：Stock-Report 量化系统所有开发任务  
> 最后更新：2025-06-25 · CI v2.5 PR 审计报告系统已上线
> 目标：保证所有模块可训练 / 可回测 / 可演进  
> 最后更新：2025-06-25

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
RTI v1 (rule + ML hybrid)
→ RTI v1.5 (backtest validated)
→ RTI v2   (ML dominant)  
→ RTI v3   (regime adaptive)
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

## 9. 升级路线

| 优先级 | 模块 | 状态 |
|--------|------|------|
| 🥇 | RTI backtest + IC 系统 | ✅ |
| 🥈 | drift detection（市场结构变化检测） | ✅ |
| 🥉 | 龙头链路模型（板块→交易点） | ⬜ |
| 🚀 | Work Buddy 自动验收 CI 系统 | ✅ |
| 🚀 | CI → PR 自动审计报告 | ✅ v2.5 |

---

## 10. CI PR 审计报告 (v2.5)

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

## 11. Model Evolution Log (v2.5)

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

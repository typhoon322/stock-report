"""
rotation/rti2.py — RTI 2.0 轮动识别引擎

核心升级 (vs RTI v1):
  1. FlowShift   — 资金迁移检测（旧主线流出 → 新板块流入）
  2. Acceleration — 资金加速度（流入加速还是减速）
  3. Decay       — 旧主线衰减（龙头滞涨/量缩/连板断档）
  4. 4-Stage     — 异常扫描→试探→扩散→确认

输出: 轮动阶段 + 新主线概率
"""
from .models import Sector, Stock, RotationSignal
from typing import List, Tuple, Optional, Dict
import math

# ─────────────────────────────────────────────
# RTI 2.0 组件
# ─────────────────────────────────────────────

def compute_flow_shift(
    sectors: List[Sector],
    old_leaders: List[str],  # 旧主线板块名
) -> Dict[str, float]:
    """
    资金迁移检测
    
    逻辑: 计算旧主线资金流出量 vs 非旧主线资金流入量
    如果迁移量超过阈值 → 资金在"换方向"
    
    Returns: {sector_name: flow_shift_score}
    """
    if not old_leaders:
        return {}
    
    # 旧主线总流出
    old_outflow = sum(
        abs(s.net_money_flow) for s in sectors 
        if s.name in old_leaders and s.net_money_flow < 0
    )
    
    # 各板块 flow_shift = 自身流入 / (自身流入 + 旧主线流出)
    shift_scores = {}
    total_shift = 0
    for s in sectors:
        if s.name in old_leaders:
            continue
        if s.net_money_flow > 0 and old_outflow > 0:
            # 流入量占迁移总量的比例
            shift = s.net_money_flow / old_outflow
            shift_scores[s.name] = min(shift, 1.0)
            total_shift += shift
    
    return shift_scores


def compute_acceleration(
    sector: Sector,
    prev_day_flow: float = 0,
) -> float:
    """
    资金加速度
    
    Acceleration = TodayFlow - YesterdayFlow
    > 0 → 加速进入
    < 0 → 减速/流出
    """
    if prev_day_flow == 0:
        return 0
    return sector.net_money_flow - prev_day_flow


def detect_old_leader_decay(
    old_sectors: List[Sector],
    old_stocks: Dict[str, List[Stock]],
) -> Dict[str, List[str]]:
    """
    旧主线衰减检测
    
    三个信号:
    1. 龙头滞涨 — 前龙头股今日涨幅<板块均值
    2. 成交量下降 — 板块量比<0.8
    3. 连板断档 — 涨停数骤降
    """
    decay_signals = {}
    
    for sec in old_sectors:
        signals = []
        
        # 信号1: 龙头滞涨
        stocks = old_stocks.get(sec.name, sec.stocks)
        if stocks:
            avg_chg = sum(s.change_pct for s in stocks) / max(len(stocks), 1)
            top_stock = max(stocks, key=lambda s: s.change_pct) if stocks else None
            if top_stock and top_stock.change_pct < avg_chg * 0.8:
                signals.append("龙头滞涨")
        
        # 信号2: 成交量萎缩
        if sec.volume_change < 0.8:
            signals.append("量能萎缩")
        
        # 信号3: 涨停骤减 (假设昨日有更多涨停)
        if sec.num_limit_up == 0 and sec.change_1d < 0:
            signals.append("涨停断档")
        
        if signals:
            decay_signals[sec.name] = signals
    
    return decay_signals


def compute_rti2(
    sector: Sector,
    all_sectors: List[Sector],
    flow_shift_score: float = 0,
    acceleration: float = 0,
    is_low_position: bool = False,
    has_news_driver: bool = False,
    decay_warning: bool = False,  # 是否来自旧主线
) -> Tuple[int, str, List[str]]:
    """
    RTI 2.0 评分
    
    Returns: (score, stage, reasons)
    
    Stage:
      "new_mainline"  — 新主线形成 (4-5)
      "probing"       — 轮动试探 (3)
      "scanning"      — 异常扫描 (1-2)
      "none"          — 无信号
    """
    score = 0
    reasons = []
    
    # 1. 资金迁移 (核心) — 权重最高
    if flow_shift_score > 0.3:
        score += 2
        reasons.append(f"资金迁移强烈(shift={flow_shift_score:.2f})")
    elif flow_shift_score > 0.1:
        score += 1
        reasons.append(f"资金迁移初步(shift={flow_shift_score:.2f})")
    
    # 2. 资金加速度
    if acceleration > 0:
        score += 1
        reasons.append(f"资金加速流入(Δ={acceleration:.1f}亿)")
    
    # 3. 低位异动 + 无新闻
    if is_low_position and not has_news_driver:
        score += 1
        reasons.append("低位+无新闻驱动(自然轮动)")
    elif is_low_position:
        score += 0.5
    
    # 4. 成交量放大
    if sector.volume_change > 1.5:
        score += 1
        reasons.append(f"量能放大{sector.volume_change:.1f}x")
    
    # 5. 涨停确认
    if sector.num_limit_up >= 2:
        score += 1
        reasons.append(f"{sector.num_limit_up}只涨停确认")
    elif sector.num_limit_up >= 1:
        score += 0.5
        reasons.append("1只涨停试探")
    
    # 6. 旧主线衰减加分（切换信号增强）
    if decay_warning:
        score += 0.5
        reasons.append("旧主线衰减→切换概率上升")
    
    score = round(score)
    
    # Stage判定
    if score >= 4:
        stage = "new_mainline"
    elif score >= 3:
        stage = "probing"
    elif score >= 1:
        stage = "scanning"
    else:
        stage = "none"
    
    return score, stage, reasons


# ─────────────────────────────────────────────
# 四阶段轮动管线
# ─────────────────────────────────────────────

class RotationPipeline:
    """
    轮动识别四阶段管线
    
    Stage 1: 异常扫描 — 低位+放量+无新闻
    Stage 2: 试探确认 — ≥2只个股异动, 小范围上涨
    Stage 3: 扩散确认 — ≥3只涨+涨停+持续放量
    Stage 4: 主线确认 — 龙头出现+稳定Top10+资金持续流入
    """
    
    def __init__(self, sectors: List[Sector]):
        self.sectors = sectors
        self.pipeline: Dict[str, dict] = {}
    
    def stage1_scan(self) -> List[Sector]:
        """Stage 1: 异常扫描"""
        candidates = []
        for s in self.sectors:
            if s.change_1d > 1.5 and s.volume_change > 1.3:
                candidates.append(s)
                self.pipeline[s.name] = {"stage": 1, "label": "🔍 异常扫描"}
        return candidates
    
    def stage2_probe(self, candidates: List[Sector]) -> List[Sector]:
        """Stage 2: 试探确认 — ≥2异动+小范围上涨"""
        probed = []
        for s in candidates:
            movers = sum(1 for st in s.stocks if st.volume_ratio > 2.0 and st.change_pct > 0)
            if movers >= 2:
                probed.append(s)
                self.pipeline[s.name] = {"stage": 2, "label": "🟡 试探期", "movers": movers}
        return probed
    
    def stage3_diffuse(self, probed: List[Sector]) -> List[Sector]:
        """Stage 3: 扩散确认 — ≥3涨+涨停+持续放量"""
        diffused = []
        for s in probed:
            up_count = s.num_stocks_up
            has_limit = s.num_limit_up > 0
            if up_count >= 3 and has_limit:
                diffused.append(s)
                self.pipeline[s.name] = {"stage": 3, "label": "🟠 扩散期", 
                                          "up": up_count, "limits": s.num_limit_up}
        return diffused
    
    def stage4_confirm(self, diffused: List[Sector], leader_stocks: List[Stock]) -> List[Sector]:
        """Stage 4: 主线确认 — 龙头+Top10+持续流入"""
        confirmed = []
        leader_codes = {s.code for s in leader_stocks}
        
        for s in diffused:
            has_leader = any(st.code in leader_codes for st in s.stocks)
            if has_leader and s.net_money_flow > 0:
                confirmed.append(s)
                self.pipeline[s.name] = {"stage": 4, "label": "🚀 新主线确认"}
        
        return confirmed
    
    def run(self, leaders: List[Stock]) -> dict:
        """运行完整管线"""
        candidates = self.stage1_scan()
        probed = self.stage2_probe(candidates)
        diffused = self.stage3_diffuse(probed)
        confirmed = self.stage4_confirm(diffused, leaders)
        
        return {
            "stage1_scanning": candidates,
            "stage2_probings": probed,
            "stage3_diffused": diffused,
            "stage4_confirmed": confirmed,
            "summary": self.pipeline,
        }

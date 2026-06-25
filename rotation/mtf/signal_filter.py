"""
rotation/mtf/signal_filter.py — MTF信号过滤

根据多周期一致性对 RTI / Breakout / Smart Money 信号进行加权/过滤
"""
from typing import Dict
from .consistency_checker import run_mtf_check


def filter_rti_signal(rti_signal: str, rti_score: float, mtf: Dict) -> Dict:
    """
    用 MTF 过滤 RTI 信号
    
    Returns: {"signal": str, "confidence": float, "adjusted": bool, "reason": str}
    """
    mtf_score = mtf.get("mtf_score", 0)
    status = mtf.get("status", "divergent")
    
    result = {
        "original_signal": rti_signal,
        "original_score": rti_score,
        "adjusted": False,
        "reason": "MTF一致，信号通过",
    }
    
    # 规则1: RTI做多 + MTF持续下跌 → 拒绝
    if rti_signal == "LONG" and mtf_score <= -2:
        result["signal"] = "HOLD"
        result["confidence"] = 0.2
        result["adjusted"] = True
        result["reason"] = "MTF强一致下跌 → RTI多头信号被过滤"
    
    # 规则2: RTI做空 + MTF持续上涨 → 拒绝
    elif rti_signal == "SHORT" and mtf_score >= 2:
        result["signal"] = "HOLD"
        result["confidence"] = 0.2
        result["adjusted"] = True
        result["reason"] = "MTF强一致上涨 → RTI空头信号被过滤"
    
    # 规则3: 分歧期 → 降低置信
    elif status == "divergent":
        result["signal"] = rti_signal
        result["confidence"] = 0.5
        result["adjusted"] = True
        result["reason"] = "MTF分歧 → 置信度降低"
    
    # 规则4: MTF共振 → 提升置信
    elif mtf_score >= 2 or mtf_score <= -2:
        result["signal"] = rti_signal
        result["confidence"] = min(1.0, rti_score * 1.3)
        result["adjusted"] = True
        result["reason"] = "MTF共振确认 → 置信度提升"
    
    else:
        result["signal"] = rti_signal
        result["confidence"] = rti_score
    
    return result


def filter_breakout(brk_classification: str, brk_score: float, mtf: Dict) -> Dict:
    """用 MTF 过滤突破信号"""
    status = mtf.get("status", "divergent")
    mtf_score = mtf.get("mtf_score", 0)
    long_trend = mtf.get("trends", {}).get("long", 0)
    
    result = {
        "original": brk_classification,
        "score": brk_score,
        "adjusted": False,
    }
    
    # 突破 + 长期下跌 → 假突破风险↑
    if brk_classification in ("genuine_breakout", "suspicious_breakout") and long_trend < 0:
        result["risk_boost"] = 0.3
        result["note"] = "长期结构偏空 → 突破可信度下降"
        result["adjusted"] = True
    
    # 分歧中突破 → 观望
    if status == "divergent" and brk_classification != "liquidity_trap":
        result["risk_boost"] = 0.2
        result["note"] = "MTF分歧 → 建议等待方向明确"
        result["adjusted"] = True
    
    return result


def filter_smart_money(behavior: str, mtf: Dict) -> Dict:
    """用 MTF 过滤 Smart Money 行为信号"""
    mtf_score = mtf.get("mtf_score", 0)
    
    # accumulation + MTF一致 = 强信号
    # distribution + MTF一致 = 强风险
    # manipulation + MTF分歧 = 可能是真洗盘
    
    boost = 0.0
    note = ""
    
    if behavior == "accumulation" and mtf_score > 0:
        boost = 0.3
        note = "accumulation + MTF上升 → 强吸筹信号"
    elif behavior == "distribution" and mtf_score < 0:
        boost = -0.3
        note = "distribution + MTF下降 → 确认出货"
    elif behavior == "manipulation" and mtf_score > 0:
        boost = 0.2
        note = "洗盘 + MTF上升 → 大概率诱空洗盘"
    
    return {
        "behavior": behavior,
        "mtf_boost": round(boost, 2),
        "note": note if note else "MTF对行为无显著影响",
        "adjusted": boost != 0,
    }

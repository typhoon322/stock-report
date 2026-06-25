"""
rotation/ensemble/conflict_resolver.py — 冲突处理

策略: 置信度加权 + LS优先 + 一致性过滤
"""
from typing import Dict, List
from .model_pool import ModelSignal


def resolve_conflict(
    signals: List[ModelSignal],
    strategy: str = "confidence_weighted",
) -> List[ModelSignal]:
    """
    解决模型间信号冲突
    
    strategies:
      - confidence_weighted: 置信度加权 (默认)
      - leader_priority: LS/龙头模型优先
      - consensus_only: 一致性<60% → 全部HOLD
    """
    if strategy == "leader_priority":
        # LS模型优先级最高
        leader_signals = [s for s in signals if "ls" in s.model_name.lower() or "leader" in s.model_name.lower()]
        if leader_signals:
            leader_sig = max(leader_signals, key=lambda s: s.confidence)
            # 如果龙头看空 → 全部降为HOLD
            if leader_sig.signal < 0:
                return [ModelSignal(s.model_name, 0, s.confidence * 0.5, s.target, f"overridden_by_leader={leader_sig.model_name}") for s in signals]
        return signals
    
    elif strategy == "consensus_only":
        longs = sum(1 for s in signals if s.signal > 0)
        shorts = sum(1 for s in signals if s.signal < 0)
        agreement = max(longs, shorts) / max(len(signals), 1)
        if agreement < 0.6:
            return [ModelSignal(s.model_name, 0, 0.3, s.target, "consensus_filter: agreement<60%") for s in signals]
        return signals
    
    else:
        # confidence_weighted: 不做修改，由 voter 加权处理
        return signals


def detect_conflict(signals: List[ModelSignal]) -> Dict:
    """检测是否有严重冲突"""
    longs = [s for s in signals if s.signal > 0]
    shorts = [s for s in signals if s.signal < 0]
    
    conflict = {
        "has_conflict": len(longs) > 0 and len(shorts) > 0,
        "long_models": [s.model_name for s in longs],
        "short_models": [s.model_name for s in shorts],
        "severity": "high" if len(longs) > 0 and len(shorts) > 0 and abs(len(longs) - len(shorts)) <= 1 else (
            "medium" if len(longs) > 0 and len(shorts) > 0 else "none"
        ),
    }
    return conflict

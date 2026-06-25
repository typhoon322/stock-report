"""
rotation/ensemble/voter.py — 投票核心 + 主入口

多模型 → 加权投票 → 最终决策
"""
import json, os
from datetime import datetime
from typing import Dict, List, Optional

from .model_pool import ModelSignal, build_ensemble_pool
from .weight_manager import compute_dynamic_weights
from .signal_aggregator import aggregate_signals, compute_signal_entropy
from .conflict_resolver import resolve_conflict, detect_conflict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_PATH = os.path.join(ROOT, "rotation", "ensemble", "logs", "ensemble_vote.json")


class EnsembleVoter:
    """多模型投票系统"""
    
    def __init__(self):
        self.signals: List[ModelSignal] = []
        self.weights: Dict[str, float] = {}
        self.result: Dict = {}
    
    def add_signal(self, signal: ModelSignal):
        self.signals.append(signal)
    
    def vote(
        self,
        regime: str = "rotation",
        conflict_strategy: str = "confidence_weighted",
    ) -> Dict:
        """执行投票"""
        if not self.signals:
            return {"decision": "HOLD", "error": "no_signals"}
        
        # Step 1: 构建模型池 + 计算权重
        pool = build_ensemble_pool()
        self.weights = compute_dynamic_weights(pool, regime)
        
        # Step 2: 冲突检测 + 解决
        conflict = detect_conflict(self.signals)
        resolved = resolve_conflict(self.signals, conflict_strategy)
        
        # Step 3: 加权投票
        score, agreement, decision = aggregate_signals(resolved, self.weights)
        entropy = compute_signal_entropy(resolved)
        
        # Step 4: 构建报告
        self.result = {
            "timestamp": datetime.now().isoformat(),
            "regime": regime,
            "signals": [s.to_dict() for s in self.signals],
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "conflict": conflict,
            "voting": {
                "weighted_score": score,
                "agreement": agreement,
                "entropy": entropy,
                "decision": decision,
                "confidence": round(min(abs(score) * 1.5 + agreement * 0.3, 1.0), 3),
            },
        }
        
        # 保存报告
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, 'w') as f:
            json.dump(self.result, f, indent=2, ensure_ascii=False, default=str)
        
        return self.result
    
    def print_summary(self):
        if not self.result:
            return
        
        v = self.result["voting"]
        print(f"\n{'='*50}")
        print(f"🧠 Ensemble Vote — {v['decision']}")
        print(f"{'='*50}")
        print(f"\n## Signals")
        for s in self.result["signals"]:
            icon = "🟢" if s["signal"] > 0 else ("🔴" if s["signal"] < 0 else "⚪")
            print(f"  {icon} {s['model']}: {s['signal_label']} (conf={s['confidence']:.2f})")
        
        print(f"\n## Weighted Vote")
        print(f"  Score: {v['weighted_score']:+.4f}")
        print(f"  Agreement: {v['agreement']:.0%}")
        print(f"  Entropy: {v['entropy']:.3f}")
        print(f"  Confidence: {v['confidence']:.0%}")
        
        c = self.result["conflict"]
        if c["has_conflict"]:
            print(f"  ⚠️ Conflict: {c['severity']} (LONG:{c['long_models']} vs SHORT:{c['short_models']})")
        
        print(f"\n## Decision")
        print(f"  👉 {v['decision']}")

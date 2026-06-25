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
        flow_result: Dict = None,
        smart_money_result: Dict = None,
    ) -> Dict:
        """执行投票 (支持资金流权重 + 主力行为校验)"""
        if not self.signals:
            return {"decision": "HOLD", "error": "no_signals"}
        
        # Step 1: 构建模型池 + 计算权重
        pool = build_ensemble_pool()
        self.weights = compute_dynamic_weights(pool, regime)
        
        # Step 1b: 资金流权重覆盖
        flow_weights = None
        if flow_result:
            try:
                from rotation.flow.flow_weight import compute_flow_adjusted_weights
                model_types = {m["name"]: m.get("type", "rule") for m in pool}
                model_signals = {s.model_name: s.signal for s in self.signals}
                flow_weights = compute_flow_adjusted_weights(
                    self.weights, model_types, model_signals,
                    flow_result["regime"], flow_result["direction"]["direction"]
                )
                self.weights = flow_weights
            except Exception as e:
                print(f"  ⚠ 资金流权重失败: {e}")
        
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
            "flow_weighted": flow_weights is not None,
            "smart_money": None,
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
        
        # Step 4b: 主力行为校验 (覆盖决策)
        if smart_money_result:
            behavior = smart_money_result.get("behavior", "")
            trade = smart_money_result.get("trade_implication", {})
            ensemble_decision = self.result["voting"]["decision"]
            
            # distribution / accumulation 覆盖投票决策
            if behavior == "distribution" and ensemble_decision == "LONG":
                self.result["voting"]["decision"] = "HOLD"
                self.result["voting"]["confidence"] *= 0.5
                self.result["smart_money"] = {
                    "override": True,
                    "reason": f"主力出货({behavior}) → 覆盖LONG为HOLD",
                    "behavior": behavior,
                    "score": smart_money_result.get("score", 0),
                }
            elif behavior == "markup" and ensemble_decision == "HOLD":
                self.result["voting"]["confidence"] *= 1.3
                self.result["smart_money"] = {
                    "override": False,
                    "boost": True,
                    "reason": f"主力拉升({behavior}) → 提升HOLD置信度",
                    "behavior": behavior,
                }
            else:
                self.result["smart_money"] = {
                    "override": False,
                    "behavior": behavior,
                    "score": smart_money_result.get("score", 0),
                    "confidence": smart_money_result.get("confidence", 0),
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

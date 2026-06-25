"""
rotation/ensemble/model_pool.py — 模型池管理 + 输出标准化

所有模型统一输出: {"signal": 1|0|-1, "confidence": 0~1, "target": str, "reason": dict}
"""
from typing import Dict, List
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ModelSignal:
    """标准化模型信号"""
    def __init__(self, model_name: str, signal: int, confidence: float, target: str = "market", reason: str = ""):
        self.model_name = model_name
        self.signal = signal          # 1 (LONG) / 0 (HOLD) / -1 (SHORT)
        self.confidence = confidence  # 0.0 ~ 1.0
        self.target = target
        self.reason = reason
    
    def to_dict(self) -> Dict:
        return {
            "model": self.model_name,
            "signal": self.signal,
            "signal_label": "LONG" if self.signal > 0 else ("SHORT" if self.signal < 0 else "HOLD"),
            "confidence": round(self.confidence, 3),
            "target": self.target,
            "reason": self.reason,
        }


def build_ensemble_pool() -> List[Dict]:
    """从 Registry + Evolution 构建模型池 (含权重预设)"""
    pool = []
    
    reg_path = os.path.join(ROOT, "rotation", "rollback", "model_registry.json")
    if os.path.exists(reg_path):
        with open(reg_path) as f:
            reg = json.load(f)
        for m in reg.get("models", []):
            pool.append({
                "name": m["version"],
                "type": _infer_model_type(m["version"]),
                "ic": m.get("ic", 0),
                "precision": m.get("precision_top10", 0),
                "stability": m.get("stability_score", 0.5),
                "base_weight": 0.25,  # default equal weight
                "ci_pass": m.get("ci_pass", False),
            })
    
    return pool


def _infer_model_type(version: str) -> str:
    v = version.lower()
    if "ml" in v or "v2" in v or "v3" in v:
        return "ML"
    if "bsi" in v:
        return "sector_strength"
    if "ls" in v:
        return "leader"
    return "rule"


def create_signal_from_phase(phase: str, model_name: str) -> ModelSignal:
    """从 Phase 判断生成模型信号"""
    mapping = {
        "🚀 主升期": (1, 0.85),
        "🔄 轮动期": (1, 0.60),
        "🔍 试探期": (0, 0.45),
        "❄️ 冰点期": (-1, 0.70),
        "💨 退潮期": (-1, 0.80),
    }
    sig, conf = mapping.get(phase, (0, 0.35))
    return ModelSignal(model_name, sig, conf, "market", f"Phase={phase}")


def create_signal_from_rti(rti_score: float, model_name: str) -> ModelSignal:
    """从 RTI 分数生成信号"""
    if rti_score >= 4.0:
        return ModelSignal(model_name, 1, min(rti_score / 6, 1.0), "sector", f"RTI={rti_score:.1f}")
    elif rti_score >= 2.5:
        return ModelSignal(model_name, 0, 0.5, "sector", f"RTI={rti_score:.1f}")
    else:
        return ModelSignal(model_name, -1, min((3 - rti_score) / 3, 1.0), "sector", f"RTI={rti_score:.1f}")

"""
rotation/rollback/registry.py — Model Registry (版本注册中心)

管理所有历史模型 + 当前生产模型 + 稳定模型查找
"""
import json, os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY_PATH = os.path.join(ROOT, "rotation", "rollback", "model_registry.json")


@dataclass
class ModelVersion:
    version: str
    timestamp: str
    ic: float
    precision_top10: float
    max_drawdown: float
    stability_score: float = 0.0
    is_production: bool = False
    ci_pass: bool = False
    drift_score: float = 0.0
    change_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ModelRegistry:
    """模型注册中心"""
    
    def __init__(self):
        self.models: List[ModelVersion] = []
        self._load()
    
    def _load(self):
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH) as f:
                data = json.load(f)
            self.models = [ModelVersion(**m) for m in data.get("models", [])]
    
    def _save(self):
        os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
        with open(REGISTRY_PATH, 'w') as f:
            json.dump({
                "models": [m.to_dict() for m in self.models],
                "updated": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)
    
    def add_model(self, model: ModelVersion):
        """注册新模型版本"""
        # 如果已经存在，更新
        existing = [i for i, m in enumerate(self.models) if m.version == model.version]
        if existing:
            self.models[existing[0]] = model
        else:
            self.models.append(model)
        self._save()
    
    def get_production(self) -> Optional[ModelVersion]:
        """当前生产模型"""
        for m in self.models:
            if m.is_production:
                return m
        return None
    
    def set_production(self, version: str):
        """设置生产版本 (只有一个)"""
        for m in self.models:
            m.is_production = (m.version == version)
        self._save()
    
    def get_last_stable(self, min_stability: float = 0.7) -> Optional[ModelVersion]:
        """最近一个稳定版本"""
        stable = [m for m in self.models if m.stability_score >= min_stability and m.ci_pass]
        if not stable:
            return None
        return sorted(stable, key=lambda m: m.timestamp, reverse=True)[0]
    
    def get_best_by_ic(self) -> Optional[ModelVersion]:
        """IC最高版本"""
        if not self.models:
            return None
        return max(self.models, key=lambda m: m.ic)
    
    def get_all_stable(self) -> List[ModelVersion]:
        """所有稳定版本 (stability>=0.7)"""
        return sorted(
            [m for m in self.models if m.stability_score >= 0.7 and m.ci_pass],
            key=lambda m: m.timestamp
        )
    
    def get_evolution(self) -> List[dict]:
        """进化时间线"""
        return sorted(
            [{"version": m.version, "ic": m.ic, "stability": m.stability_score, 
              "ci": m.ci_pass, "production": m.is_production} 
             for m in self.models],
            key=lambda x: x["version"]
        )

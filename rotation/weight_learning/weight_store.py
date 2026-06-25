"""
rotation/weight_learning/weight_store.py — 权重版本管理
"""
import json, os
from datetime import datetime
from typing import Dict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(ROOT, "rotation", "weight_learning", "store")
os.makedirs(STORE_DIR, exist_ok=True)


def save_weights(weights: Dict[str, float], regime: str = "current") -> str:
    """保存权重 (版本化)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    version_name = f"weights_{regime}_{timestamp}.json"
    path = os.path.join(STORE_DIR, version_name)
    
    data = {
        "version": version_name,
        "timestamp": datetime.now().isoformat(),
        "regime": regime,
        "weights": weights,
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Also save as "current" for easy lookup
    current_path = os.path.join(STORE_DIR, "weights_current.json")
    with open(current_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return version_name


def load_current_weights() -> Dict:
    """加载当前权重"""
    path = os.path.join(STORE_DIR, "weights_current.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"weights": {}, "regime": "unknown"}


def list_weight_versions() -> list:
    """列出所有权重版本"""
    versions = []
    for f in os.listdir(STORE_DIR):
        if f.startswith("weights_") and f.endswith(".json") and f != "weights_current.json":
            timestamp = f.replace("weights_", "").replace(".json", "")
            versions.append({"file": f, "timestamp": timestamp})
    return sorted(versions, key=lambda x: x["timestamp"], reverse=True)

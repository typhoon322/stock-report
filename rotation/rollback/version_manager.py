"""
rotation/rollback/version_manager.py — 模型版本文件管理

负责: 模型文件(pkl)的归档/恢复/生产部署
"""
import os, shutil, json
from datetime import datetime
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHIVE_DIR = os.path.join(ROOT, "rotation", "rollback", "archive")
MODEL_PATH = os.path.join(ROOT, "rotation", "models", "rti_model.pkl")
PROD_LINK = os.path.join(ROOT, "rotation", "models", "rti_model_production.pkl")

os.makedirs(ARCHIVE_DIR, exist_ok=True)


def archive_model(version: str):
    """归档当前模型"""
    if not os.path.exists(MODEL_PATH):
        return None
    
    archive_path = os.path.join(ARCHIVE_DIR, f"rti_model_{version}.pkl")
    shutil.copy2(MODEL_PATH, archive_path)
    
    # 记录归档信息
    meta = {
        "version": version,
        "archived_at": datetime.now().isoformat(),
        "source": MODEL_PATH,
    }
    with open(archive_path.replace('.pkl', '.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    
    return archive_path


def restore_model(version: str) -> bool:
    """恢复指定版本的模型到生产路径"""
    archive_path = os.path.join(ARCHIVE_DIR, f"rti_model_{version}.pkl")
    if not os.path.exists(archive_path):
        return False
    
    # 备份当前
    if os.path.exists(MODEL_PATH):
        bak = MODEL_PATH + f".bak_{datetime.now().strftime('%Y%m%d_%H%M')}"
        shutil.copy2(MODEL_PATH, bak)
    
    # 恢复
    shutil.copy2(archive_path, MODEL_PATH)
    return True


def get_archived_versions() -> list:
    """列出所有已归档版本"""
    if not os.path.exists(ARCHIVE_DIR):
        return []
    versions = []
    for f in os.listdir(ARCHIVE_DIR):
        if f.endswith('.pkl'):
            version = f.replace('rti_model_', '').replace('.pkl', '')
            meta_path = f.replace('.pkl', '.json')
            meta = {}
            if os.path.exists(os.path.join(ARCHIVE_DIR, meta_path)):
                with open(os.path.join(ARCHIVE_DIR, meta_path)) as mf:
                    meta = json.load(mf)
            versions.append({"version": version, "meta": meta})
    return sorted(versions, key=lambda v: v["version"])

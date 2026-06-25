"""
rotation/rollback/ — Auto Rollback System (模型免疫系统)
"""
from .registry import ModelRegistry, ModelVersion
from .stability_tracker import should_auto_rollback, compute_stability_score, classify_stability
from .version_manager import archive_model, restore_model
from .rollback_engine import run_rollback_check

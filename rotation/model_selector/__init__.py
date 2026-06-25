"""
rotation/model_selector/ — Model Brain (自适应模型择优系统)
"""
from .selector import select_best_model, build_model_pool
from .regime_detector import detect_regime, Regime
from .model_score import score_all_models, compute_model_score
from .switch_engine import should_switch

"""
rotation/smart_money/ — Smart Money Behavior Detection
"""
from .behavior_detector import detect_behavior, detect_behavior_simple, get_behavior_report
from .microstructure import compute_microstructure
from .behavior_score import score_all_behaviors, classify_behavior, BEHAVIOR_TRADE_MAP
from .pattern_library import match_pattern, BEHAVIOR_PATTERNS

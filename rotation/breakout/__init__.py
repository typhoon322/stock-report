"""
rotation/breakout/ — Breakout Authenticity System (真假突破识别)
"""
from .breakout_detector import detect_breakout
from .authenticity_score import compute_authenticity_score
from .false_break_classifier import classify_breakout, get_breakout_report
from .liquidity_trap import detect_liquidity_trap
from .follow_through import check_follow_through

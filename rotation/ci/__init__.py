"""
rotation/ci/ — CI Gate 自动验收系统
"""
from .ci_runner import CIGate, quick_ci_check
from .metrics import compute_all_metrics
from .thresholds import THRESHOLDS
from .drift_check import full_drift_check
from .report_generator import generate_ci_report, save_ci_report

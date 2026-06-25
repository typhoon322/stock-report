"""
rotation/ci/ci_runner.py — CI Gate 主入口

任何模型/策略必须通过此门禁才能上线
"""
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

from .metrics import compute_all_metrics
from .thresholds import THRESHOLDS
from .drift_check import full_drift_check
from .report_generator import generate_ci_report, save_ci_report


class CIGate:
    """CI 自动验收门禁"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.result = {
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "decision": "PENDING",
        }
    
    def run(
        self,
        predictions: List[float],
        labels: List[int],
        returns: List[float],
        benchmark_returns: List[float] = None,
        historical_returns: List[float] = None,
        recent_returns: List[float] = None,
    ) -> Dict:
        """
        运行 CI 验收
        
        Args:
            predictions: 模型预测值 (RTI/LS/BSI scores)
            labels: 实际标签 (是否成为主线/龙头)
            returns: 实际收益
            benchmark_returns: 基准收益 (沪深300)
            historical_returns: 历史收益 (用于drift检测)
            recent_returns: 近期收益 (用于drift检测)
        
        Returns:
            {decision, metrics, drift, report}
        """
        print(f"\n🧪 CI Gate: {self.model_name}")
        print("=" * 50)
        
        # Step 1: 计算指标
        print("  [1] 指标计算...")
        metrics = compute_all_metrics(predictions, labels, returns, benchmark_returns or [])
        
        # Step 2: 检查达标
        print("  [2] 门槛检查...")
        checks = self._check_thresholds(metrics)
        
        # Step 3: Drift检测
        print("  [3] 市场结构检测...")
        drift = {}
        if historical_returns and recent_returns:
            drift = full_drift_check(historical_returns, recent_returns)
        else:
            drift = {"drift_score": 0, "drift_status": "stable (no history)", "alert": False}
        
        # Step 4: 决策
        print("  [4] 决策...")
        all_pass = all(v["pass"] for v in checks.values())
        drift_ok = not drift.get("alert", False)
        
        if all_pass and drift_ok:
            decision = "APPROVED ✅"
        elif all_pass and not drift_ok:
            decision = "APPROVED (drift warning) ⚠️"
        else:
            failed = [k for k, v in checks.items() if not v["pass"]]
            decision = f"REJECTED ❌ — failed: {', '.join(failed)}"
        
        # Step 5: 生成报告
        print("  [5] 生成报告...")
        report = generate_ci_report(self.model_name, metrics, drift, decision)
        paths = save_ci_report(report)
        
        self.result = {
            "model": self.model_name,
            "decision": decision,
            "metrics": metrics,
            "checks": checks,
            "drift": drift,
            "report_paths": paths,
        }
        
        self._print_summary()
        return self.result
    
    def _check_thresholds(self, metrics: Dict) -> Dict:
        """逐项检查是否达标"""
        checks = {}
        
        rules = [
            ("IC", metrics.get("IC", 0), THRESHOLDS["IC"], ">"),
            ("Precision@Top10%", metrics.get("precision_top10", 0), THRESHOLDS["precision_top10"], ">"),
            ("Hit Rate", metrics.get("hit_rate", 0), THRESHOLDS["hit_rate"], ">"),
            ("Sharpe", metrics.get("sharpe_proxy", 0), THRESHOLDS["sharpe_proxy"], ">"),
            ("Max Drawdown", metrics.get("max_drawdown", 1), THRESHOLDS["max_drawdown"], "<"),
            ("Return vs Benchmark", metrics.get("return_over_benchmark", 0), THRESHOLDS["return_over_benchmark"], ">"),
        ]
        
        for name, value, threshold, op in rules:
            if op == ">":
                passed = value > threshold
            else:
                passed = value < threshold
            
            checks[name] = {
                "value": value,
                "threshold": threshold,
                "pass": passed,
            }
        
        return checks
    
    def _print_summary(self):
        """打印摘要"""
        decision = self.result["decision"]
        icon = "✅" if "APPROVED" in decision else "❌"
        
        print(f"\n{'='*50}")
        print(f"  CI Gate 结果: {icon} {decision}")
        print(f"{'='*50}")
        
        for name, check in self.result["checks"].items():
            status = "✅" if check["pass"] else "❌"
            print(f"  {status} {name}: {check['value']:.4f} (阈值: {check['threshold']})")
        
        drift = self.result.get("drift", {})
        print(f"  {'⚠️' if drift.get('alert') else '✅'} Drift: {drift.get('drift_status', 'unknown')}")


def quick_ci_check(predictions: List[float], labels: List[int], returns: List[float]) -> Dict:
    """快速CI检查 (无历史数据时)"""
    gate = CIGate("quick_check")
    return gate.run(predictions, labels, returns)

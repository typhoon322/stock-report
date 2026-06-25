"""
rotation/model_selector/selector.py — 主决策器

在所有可用模型中，按"当前市场状态"选最优模型
"""
import os, json
from datetime import datetime
from typing import Dict, List, Optional

from .regime_detector import detect_regime, Regime, get_regime_from_market_state
from .model_score import score_all_models
from .switch_engine import should_switch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_PATH = os.path.join(ROOT, "rotation", "model_selector", "logs", "selection_report.md")


def build_model_pool() -> List[Dict]:
    """从 Registry + Evolution Log 构建模型池"""
    pool = []
    
    # 从 Registry 加载
    reg_path = os.path.join(ROOT, "rotation", "rollback", "model_registry.json")
    if os.path.exists(reg_path):
        with open(reg_path) as f:
            reg = json.load(f)
        for m in reg.get("models", []):
            pool.append({
                "version": m["version"],
                "ic": m.get("ic", 0),
                "precision_top10": m.get("precision_top10", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "stability_score": m.get("stability_score", 0.5),
                "ci_pass": m.get("ci_pass", False),
                "is_production": m.get("is_production", False),
            })
    
    # 从 Evolution Log 补充
    evo_path = os.path.join(ROOT, "rotation", "evolution", "logs", "evolution_log.jsonl")
    if os.path.exists(evo_path):
        existing_versions = {m["version"] for m in pool}
        with open(evo_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if r.get("model_version") not in existing_versions:
                        pool.append({
                            "version": r["model_version"],
                            "ic": r.get("ic", 0),
                            "precision_top10": r.get("precision_top10", 0),
                            "max_drawdown": r.get("max_drawdown", 0),
                            "stability_score": 0.5,
                            "ci_pass": r.get("ci_pass", False),
                            "is_production": False,
                        })
                        existing_versions.add(r["model_version"])
                except:
                    pass
    
    return pool


def select_best_model(
    market_breadth: float = 0.5,
    limit_up_count: int = 30,
    current_production: str = "",
    phase: str = "",
) -> Dict:
    """
    主入口: 在当前市场状态下选择最优模型
    
    Returns:
        {
            "regime": str,
            "best_model": str,
            "best_score": float,
            "all_models": [...],  # 全部评分
            "should_switch": bool,
            "switch_reason": str,
            "report": str,
        }
    """
    # Step 1: 识别市场状态
    regime = detect_regime(market_breadth, limit_up_count, phase=phase)
    
    # Step 2: 构建模型池
    pool = build_model_pool()
    if not pool:
        return {"error": "empty_model_pool", "regime": regime}
    
    # Step 3: 评分
    scored = score_all_models(pool, regime)
    best = scored[0]
    
    # Step 4: 是否切换
    current_score = 0
    if current_production:
        for m in scored:
            if m["version"] == current_production:
                current_score = m["regime_score"]
                break
    
    do_switch, switch_reason = should_switch(
        best_model=best["version"],
        best_score=best["regime_score"],
        current_model=current_production or best["version"],
        current_score=current_score if current_production else best["regime_score"],
    )
    
    # Step 5: 生成报告
    report = generate_selection_report(regime, scored, best, do_switch, switch_reason)
    
    return {
        "regime": regime,
        "best_model": best["version"],
        "best_score": best["regime_score"],
        "current_model": current_production,
        "all_models": scored[:5],
        "should_switch": do_switch,
        "switch_reason": switch_reason,
        "report": report,
    }


def generate_selection_report(
    regime: str,
    scored: List[Dict],
    best: Dict,
    do_switch: bool,
    reason: str,
) -> str:
    """生成模型选择报告"""
    lines = [
        f"# 🧠 Model Selection Report",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Current Regime**: {regime}",
        f"",
        f"## 📊 Models Evaluated",
        f"",
        f"| Model | Score | IC | Precision | Stability |",
        f"|-------|-------|-----|-----------|-----------|",
    ]
    
    for m in scored[:10]:
        marker = " ⭐" if m["version"] == best["version"] else ""
        lines.append(
            f"| {m['version']}{marker} | {m['regime_score']:.2f} | {m.get('ic', 0):.4f} | {m.get('precision_top10', 0):.4f} | {m.get('stability_score', 0):.2f} |"
        )
    
    lines.extend([
        f"",
        f"## 🎯 Decision",
        f"",
        f"**Best Model**: {best['version']} (score: {best['regime_score']:.2f})",
        f"**Action**: {'🔄 SWITCH' if do_switch else '✅ KEEP'}",
        f"**Reason**: {reason}",
        f"",
        f"---",
        f"*🤖 Model Brain v1 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])
    
    report = "\n".join(lines)
    
    # 保存
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        f.write(report)
    
    return report

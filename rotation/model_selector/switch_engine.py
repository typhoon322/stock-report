"""
rotation/model_selector/switch_engine.py — 模型切换执行 + 防抖

避免频繁切换:
- 至少持续3天优胜才切换
- 或score差距>10%
"""
import json, os
from datetime import datetime, timedelta
from typing import Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SWITCH_LOG = os.path.join(ROOT, "rotation", "model_selector", "logs", "switch_log.jsonl")
STATE_PATH = os.path.join(ROOT, "rotation", "model_selector", "logs", "switch_state.json")


def load_switch_state() -> Dict:
    """加载切换状态"""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"leading_model": None, "lead_streak": 0, "last_switch": None, "current_model": None}


def save_switch_state(state: Dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2, default=str)


def log_switch(from_model: str, to_model: str, reason: str, score_gap: float):
    os.makedirs(os.path.dirname(SWITCH_LOG), exist_ok=True)
    event = {
        "timestamp": datetime.now().isoformat(),
        "from": from_model,
        "to": to_model,
        "reason": reason,
        "score_gap": round(score_gap, 4),
    }
    with open(SWITCH_LOG, 'a') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')


def should_switch(
    best_model: str,
    best_score: float,
    current_model: str,
    current_score: float,
    streak_days: int = 3,
    score_gap_threshold: float = 0.10,
) -> tuple:
    """
    判断是否应该切换模型
    
    Returns: (should_switch: bool, reason: str)
    """
    state = load_switch_state()
    
    # 没有当前模型 → 首次选择
    if not current_model:
        state["leading_model"] = best_model
        state["lead_streak"] = 1
        state["current_model"] = best_model
        save_switch_state(state)
        return True, "FIRST_SELECT — 首次选择模型"
    
    # 当前就是最佳 → 不切换
    if best_model == current_model:
        state["leading_model"] = None
        state["lead_streak"] = 0
        save_switch_state(state)
        return False, "ALREADY_BEST — 当前模型即最优"
    
    # 计算分数差距
    score_gap = (best_score - current_score) / max(current_score, 0.01)
    
    # 差距>阈值 → 立即切换
    if score_gap > score_gap_threshold:
        state["leading_model"] = best_model
        state["lead_streak"] = 0
        state["current_model"] = best_model
        state["last_switch"] = datetime.now().isoformat()
        save_switch_state(state)
        log_switch(current_model, best_model, f"GAP_{score_gap:.1%}", score_gap)
        return True, f"SCORE_GAP — 最佳模型领先{score_gap:.0%} (>10%阈值)"
    
    # 累积领先天数
    if state.get("leading_model") == best_model:
        state["lead_streak"] += 1
    else:
        state["leading_model"] = best_model
        state["lead_streak"] = 1
    
    # 连续领先≥streak_days → 切换
    if state["lead_streak"] >= streak_days:
        state["current_model"] = best_model
        state["last_switch"] = datetime.now().isoformat()
        state["lead_streak"] = 0
        save_switch_state(state)
        log_switch(current_model, best_model, f"STREAK_{streak_days}d", score_gap)
        return True, f"STREAK_{streak_days}D — 连续{streak_days}天领先"
    
    save_switch_state(state)
    return False, f"WAITING — 领先{state['lead_streak']}/{streak_days}天 (差距{score_gap:.0%})"

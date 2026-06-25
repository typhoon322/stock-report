"""
rotation/smart_money/behavior_detector.py — 主力行为识别主入口
"""
from typing import Dict, List
from .microstructure import compute_microstructure
from .behavior_score import score_all_behaviors, classify_behavior, BEHAVIOR_TRADE_MAP


def detect_behavior(
    prices: List[float],
    volumes: List[float],
    highs: List[float] = None,
    lows: List[float] = None,
    opens: List[float] = None,
) -> Dict:
    """
    主入口: 识别主力行为
    
    Returns:
        {
            "behavior": str,
            "score": float,
            "confidence": float,
            "scores": dict,
            "microstructure": dict,
            "trade_implication": dict,
        }
    """
    # Step 1: 微观结构特征
    features = compute_microstructure(prices, volumes, highs, lows, opens)
    
    # Step 2: 行为评分
    scores = score_all_behaviors(features)
    
    # Step 3: 分类
    result = classify_behavior(scores)
    result["microstructure"] = features
    
    return result


def detect_behavior_simple(
    change_1d: float,
    change_5d: float,
    volume_ratio: float,
    is_limit_up: bool = False,
    is_low_position: bool = False,
) -> Dict:
    """
    简化版行为检测 (只需要基本数据，不需要完整OHLCV)
    用于快速集成到日报管道
    """
    # 模拟价格序列
    prices = [100 * (1 + change_5d/100), 100, 100 * (1 + change_1d/100)]
    volumes = [100, 100 * volume_ratio, 100 * max(volume_ratio, 0.8)]
    highs = [p * 1.02 for p in prices]
    lows = [p * 0.98 for p in prices]
    opens = [prices[0], prices[1], prices[2]]
    
    # 调整: 如果是低位, 压低价格
    if is_low_position:
        prices = [p * 0.85 for p in prices]
    
    # 调整: 如果是涨停, 标记
    if is_limit_up:
        prices[-1] *= 1.05  # 收盘略高于开盘
    
    return detect_behavior(prices, volumes, highs, lows, opens)


def get_behavior_report(result: Dict) -> str:
    """生成行为分析报告"""
    behavior = result.get("behavior", "unknown")
    score = result.get("score", 0)
    confidence = result.get("confidence", 0)
    scores = result.get("scores", {})
    micro = result.get("microstructure", {})
    trade = result.get("trade_implication", {})
    
    lines = [
        f"# 🧠 Smart Money Behavior",
        f"",
        f"## Classification",
        f"👉 **{behavior}** (score={score:.2f}, confidence={confidence:.0%})",
        f"",
        f"## Scores",
    ]
    
    icons = {"accumulation": "📦", "markup": "🚀", "distribution": "📤", "manipulation": "🎢"}
    for b, s in scores.items():
        icon = icons.get(b, "•")
        bar = "█" * int(s * 20) + "░" * (20 - int(s * 20))
        lines.append(f"- {icon} {b}: {bar} {s:.2f}")
    
    lines.extend([
        f"",
        f"## Microstructure",
        f"- Position: {micro.get('position_zone', '?')}",
        f"- Momentum: {micro.get('price_momentum', 0):.3f}",
        f"- Volume Spike: {micro.get('volume_spike', 0):.2f}",
        f"- Breakout: {micro.get('breakout_strength', 0):.3f}",
        f"- Shadow Ratio: {micro.get('shadow_ratio', 0):.3f} (正=吸筹/负=出货)",
        f"",
        f"## Trade Implication",
        f"- Action: **{trade.get('action', '?')}**",
        f"- Risk: {trade.get('risk', '?')}",
        f"- {trade.get('description', '')}",
    ])
    
    return "\n".join(lines)

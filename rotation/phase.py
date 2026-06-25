"""
rotation/phase.py — Market Phase Detection (市场周期判断)

基于: 涨跌比 + 涨停数 + 连板高度 + 资金流向 + 板块扩散度
输出: 冰点期 / 试探期 / 轮动期 / 主升期 / 退潮期
"""
from .models import MarketSentiment
from typing import Dict

def detect_phase(sentiment: MarketSentiment) -> str:
    """
    基于多维度判断当前市场周期
    
    决策逻辑（按优先级）:
    1. 退潮期: 资金转为流出 + 涨跌比骤降 + 涨停骤减
    2. 冰点期: 涨跌比极低 + 涨停极少 + 资金大幅流出
    3. 主升期: 涨跌比高 + 涨停多 + 连板高 + 资金大幅流入
    4. 试探期: 从冰点回暖, 涨跌比回升但未确认
    5. 轮动期: 资金分化流入, 板块扩散中等
    """
    b = sentiment.market_breadth
    limit_up = sentiment.limit_up_count
    fall_limit = sentiment.fall_limit_count
    consecutive = sentiment.consecutive_board
    
    # 1. 退潮期检测: 跌停突然增多 + 连板高度下降
    if fall_limit > limit_up * 0.5 and consecutive < 4:
        return "💨 退潮期"
    
    # 2. 冰点期: 极端悲观
    if b < 0.3 and limit_up < 20:
        return "❄️ 冰点期"
    
    # 3. 主升期: 涨跌比高 + 涨停多 + 连板高
    if b > 0.55 and limit_up > 50 and consecutive >= 5:
        return "🚀 主升期"
    
    # 4. 试探期: 从低位回暖
    if 0.3 <= b < 0.45 and limit_up < 40:
        return "🔍 试探期"
    
    # 5. 轮动期: 中间状态(最常见)
    return "🔄 轮动期"


def get_position_advice(phase: str) -> Dict:
    """根据周期给出仓位建议"""
    advice = {
        "❄️ 冰点期": {
            "position": "0-20%",
            "strategy": "防守",
            "action": "轻仓或空仓，等待回暖信号",
            "focus": "逆势抗跌板块",
        },
        "🔍 试探期": {
            "position": "20-50%",
            "strategy": "试探",
            "action": "小仓位尝试低位异动板块",
            "focus": "RTI ≥ 3 的轮动试探板块",
        },
        "🔄 轮动期": {
            "position": "50-80%",
            "strategy": "进攻",
            "action": "重点配置BSI>30的强势板块",
            "focus": "RTI ≥ 4 的潜在新主线",
        },
        "🚀 主升期": {
            "position": "80-100%",
            "strategy": "主升",
            "action": "重仓龙头股，持股待涨",
            "focus": "LS ≥ 7 的龙头股",
        },
        "💨 退潮期": {
            "position": "逐步减仓",
            "strategy": "退出",
            "action": "减仓至30%以下，清仓弱势股",
            "focus": "现金为王，等待冰点",
        },
    }
    return advice.get(phase, advice["🔄 轮动期"])


def compute_risk_level(sentiment: MarketSentiment, phase: str) -> str:
    """综合风险评级"""
    if phase in ["💨 退潮期", "❄️ 冰点期"]:
        return "high" if sentiment.fall_limit_count > 50 else "medium"
    elif phase == "🚀 主升期":
        return "low"
    else:
        return "medium"

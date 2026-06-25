"""
rotation/backtest.py — 回测引擎

验证: RTI是否提前识别主线 / LS是否找到龙头 / 策略是否跑赢指数
"""
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import math


class TradeSimulator:
    """交易模拟器"""
    
    def __init__(self, hold_days: int = 10):
        self.hold_days = hold_days
        self.positions = []  # [(entry_date, exit_date, sector, rti, return)]
    
    def open(self, date: str, sector: str, rti: float):
        """开仓"""
        self.positions.append({
            "entry_date": date,
            "sector": sector,
            "entry_rti": rti,
            "exit_date": None,
            "return_pct": None,
        })
    
    def close(self, idx: int, date: str, return_pct: float):
        """平仓"""
        if idx < len(self.positions):
            self.positions[idx]["exit_date"] = date
            self.positions[idx]["return_pct"] = return_pct
    
    def get_open_positions(self) -> List[int]:
        return [i for i, p in enumerate(self.positions) if p["return_pct"] is None]


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, history: Dict):
        self.history = history  # from history.build_history()
        self.trades = []        # completed trades
        self.signals = []       # all signals generated
        self.metrics = {}
    
    def run(
        self,
        rti_threshold: float = 3.0,
        hold_days: int = 10,
    ) -> Dict:
        """
        运行回测
        
        简化策略:
        - 每日扫描所有板块RTI
        - RTI ≥ threshold → 开仓该板块（买龙头）
        - 持有hold_days天后平仓
        - 记录收益率
        """
        sectors_data = self.history.get("sectors", [])
        if not sectors_data:
            return {"error": "无历史数据", "trades": 0}
        
        # 按日期分组
        dates = sorted(set(s["date"] for s in sectors_data))
        if len(dates) < hold_days + 1:
            return {"error": f"数据不足({len(dates)}天)", "trades": 0}
        
        simulator = TradeSimulator(hold_days)
        
        for i, date in enumerate(dates):
            day_sectors = [s for s in sectors_data if s["date"] == date]
            
            # 平仓到期持仓
            for pos_idx in simulator.get_open_positions():
                pos = simulator.positions[pos_idx]
                entry_date = pos["entry_date"]
                entry_idx = dates.index(entry_date) if entry_date in dates else -1
                if entry_idx >= 0 and i - entry_idx >= hold_days:
                    # 计算收益率
                    entry_data = [s for s in sectors_data 
                                  if s["date"] == entry_date and s["sector"] == pos["sector"]]
                    exit_data = [s for s in day_sectors 
                                 if s["sector"] == pos["sector"]]
                    if entry_data and exit_data:
                        ret = exit_data[0]["change_pct"] - entry_data[0]["change_pct"]
                        simulator.close(pos_idx, date, ret)
                    self.trades.append(simulator.positions[pos_idx])
            
            # 开仓: RTI ≥ threshold
            for s in day_sectors:
                # 用RTI v3评分（简化: 用change_pct作为代理）
                rti_proxy = s.get("change_pct", 0)
                if abs(rti_proxy) >= rti_threshold and rti_proxy > 0:
                    # 只同时持有一个仓位
                    if len(simulator.get_open_positions()) == 0:
                        simulator.open(date, s["sector"], rti_proxy)
                        self.signals.append({
                            "date": date,
                            "sector": s["sector"],
                            "rti": rti_proxy,
                            "signal": "entry",
                        })
        
        # 计算指标
        self._compute_metrics()
        return self.metrics
    
    def _compute_metrics(self):
        """计算回测绩效指标"""
        if not self.trades:
            self.metrics = {"trades": 0, "win_rate": 0, "avg_return": 0, "alpha": 0}
            return
        
        returns = [t["return_pct"] for t in self.trades if t["return_pct"] is not None]
        wins = [r for r in returns if r > 0]
        
        self.metrics = {
            "total_trades": len(self.trades),
            "completed_trades": len(returns),
            "win_rate": round(len(wins) / max(len(returns), 1) * 100, 1),
            "avg_return": round(sum(returns) / max(len(returns), 1), 2),
            "max_return": round(max(returns), 2) if returns else 0,
            "min_return": round(min(returns), 2) if returns else 0,
            "total_return": round(sum(returns), 2),
            "sharpe_proxy": round(
                (sum(returns) / max(len(returns), 1)) / 
                max((sum((r - sum(returns)/max(len(returns),1))**2 for r in returns) / max(len(returns),1))**0.5, 0.01), 2
            ) if len(returns) > 1 else 0,
            "signal_count": len(self.signals),
            "signal_accuracy": round(len(wins) / max(len(self.signals), 1) * 100, 1),
        }

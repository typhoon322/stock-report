"""
Daily Archive Runner — GitHub Actions 每日入口

执行三步归档:
  raw snapshot  → rotation/archive/raw/YYYY-MM-DD.json
  signal snapshot → rotation/archive/signal/YYYY-MM-DD.json
  trade log      → rotation/archive/trade/YYYY-MM-DD.json
"""
import json, os, sys, traceback
from datetime import datetime, timezone, timedelta


def _now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def run_daily_archive():
    """主入口：采集并归档所有数据"""
    print(f"📦 Daily Archive — {_now()} (UTC+8)")
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    results = {"status": "ok", "files": [], "errors": [], "timestamp": _now()}
    
    # ── 1. Raw Market Snapshot ──
    try:
        from rotation.archive.raw_snapshot import save_raw_snapshot
        
        raw_market = {}
        sectors_list = []
        futures_data = {}
        flows_data = {}
        portfolio_data = {}
        
        # 市场广度
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot()
            if df is not None:
                total = len(df)
                up = len(df[df['涨跌幅'] > 0])
                limit_up = len(df[df['涨跌幅'] >= 9.5])
                fall_limit = len(df[df['涨跌幅'] <= -9.5])
                raw_market = {"total_stocks": total, "up": up, "down": total - up,
                              "limit_up": limit_up, "fall_limit": fall_limit,
                              "breadth": round(up / total, 4) if total > 0 else 0}
        except Exception as e:
            results["errors"].append(f"market_breadth: {e}")
        
        # 板块
        try:
            from rotation.data_fetcher import fetch_industry_sectors
            sectors = fetch_industry_sectors()
            sectors_list = [{"name": s.name, "bsi": s.bsi_score, "chg": s.change_1d,
                             "flow": s.net_money_flow} for s in sectors[:10]]
        except Exception as e:
            results["errors"].append(f"sectors: {e}")
        
        # 期货
        try:
            import akshare as ak
            df = ak.futures_global_spot_em()
            for kw, label in [('黄金', '黄金'), ('原油', '原油'), ('铜', '铜')]:
                mask = df['名称'].str.contains(kw, na=False) & df['最新价'].notna()
                m = df[mask]
                if len(m) > 0:
                    r = m.iloc[0]
                    futures_data[label] = {"price": float(r['最新价']), "chg": float(r.get('涨跌幅', 0))}
        except Exception as e:
            results["errors"].append(f"futures: {e}")
        
        # 持仓
        try:
            with open(os.path.join(ROOT, "portfolio.json"), 'r') as f:
                portfolio_data = json.load(f)
        except:
            pass
        
        path = save_raw_snapshot(raw_market, sectors_list, futures_data, flows_data, portfolio_data)
        results["files"].append(path)
    except Exception as e:
        results["errors"].append(f"raw_snapshot: {e}")
        traceback.print_exc()
    
    # ── 2. Signal Snapshot ──
    try:
        from rotation.archive.signal_snapshot import save_signal_snapshot
        
        signals = {}
        
        # BSI
        try:
            from rotation.bsi import get_top_sectors
            top = get_top_sectors(5)
            signals["bsi"] = {"top": len(top), "names": [s["name"] for s in top]}
        except Exception as e:
            signals["bsi"] = {"error": str(e)[:60]}
        
        # Phase
        try:
            from rotation.phase import detect_phase, get_position_advice
            from rotation.data_fetcher import build_market_sentiment
            sent = build_market_sentiment()
            phase = detect_phase(sent)
            signals["phase"] = {"phase": phase, "advice": get_position_advice(phase)}
        except Exception as e:
            signals["phase"] = {"error": str(e)[:60]}
        
        # MTF
        try:
            from rotation.mtf import run_mtf_check
            mtf = run_mtf_check()
            signals["mtf"] = {"score": mtf["mtf_score"], "status": mtf["status"]}
        except Exception as e:
            signals["mtf"] = {"error": str(e)[:60]}
        
        # Weights
        weights = {}
        try:
            from rotation.weight_learning import load_current_weights
            w = load_current_weights()
            weights = w.get("weights", {})
        except:
            pass
        
        regime = signals.get("phase", {}).get("phase", "")
        path = save_signal_snapshot(signals, weights=weights, regime=regime)
        results["files"].append(path)
    except Exception as e:
        results["errors"].append(f"signal_snapshot: {e}")
    
    # ── 3. Trade Log ──
    try:
        from rotation.archive.trade_log import save_trade_log
        
        portfolio = None
        try:
            with open(os.path.join(ROOT, "portfolio.json"), 'r') as f:
                portfolio = json.load(f)
        except:
            pass
        
        path = save_trade_log(portfolio=portfolio)
        results["files"].append(path)
    except Exception as e:
        results["errors"].append(f"trade_log: {e}")
    
    # Summary
    err_count = len(results["errors"])
    status = "✅" if err_count == 0 else "⚠️"
    print(f"\n{status} Archive complete: {len(results['files'])} files, {err_count} errors")
    if err_count:
        for e in results["errors"]:
            print(f"   {e}")
    
    return results


if __name__ == "__main__":
    run_daily_archive()

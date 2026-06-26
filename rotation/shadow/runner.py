"""
Shadow Mode Runner — 每日自动运行入口
"""
import json, os, sys, traceback
from datetime import datetime, timezone, timedelta


def _now_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def run_shadow_mode():
    """主入口：收集所有影子数据"""
    print(f"🧪 Shadow Mode — {_now_str()}")
    print("  时区: UTC+8 (北京时间)")
    
    results = {"status": "ok", "files": [], "errors": []}
    
    # 1. Signal Snapshot
    try:
        from rotation.shadow.signal_snapshot import save_signal_snapshot
        # 收集各子系统信号
        signals = {}
        try:
            from rotation import rti3
            signals["rti"] = {"source": "rti3", "status": "ok"}
        except Exception as e:
            signals["rti"] = {"source": "rti3", "status": f"error:{e}"}
        
        try:
            from rotation.bsi import get_top_sectors
            bsi_data = get_top_sectors(5)
            signals["bsi"] = {"source": "bsi", "status": "ok", "top": len(bsi_data)}
        except Exception as e:
            signals["bsi"] = {"source": "bsi", "status": f"error:{e}"}
        
        try:
            from rotation.ls import get_leader_summary
            signals["ls"] = {"source": "ls", "status": "ok"}
        except Exception as e:
            signals["ls"] = {"source": "ls", "status": f"error:{e}"}
        
        path = save_signal_snapshot(signals)
        results["files"].append(path)
        print(f"  ✅ Signal Snapshot: {path}")
    except Exception as e:
        results["errors"].append(f"signal_snapshot: {e}")
    
    # 2. Shadow Trade
    try:
        from rotation.shadow.shadow_trade import save_shadow_trades
        
        # Load portfolio
        try:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            with open(os.path.join(root, "portfolio.json"), 'r') as f:
                pf = json.load(f)
        except:
            pf = None
        
        path = save_shadow_trades(portfolio=pf)
        results["files"].append(path)
        print(f"  ✅ Shadow Trades: {path}")
    except Exception as e:
        results["errors"].append(f"shadow_trades: {e}")
    
    # 3. System Health
    try:
        from rotation.shadow.health_collector import save_health_log, collect_api_stats
        api_stats = collect_api_stats()
        module_status = {}
        for mod in ["rti", "bsi", "ls", "phase", "mtf", "meta", "position"]:
            try:
                __import__(f"rotation.{mod}", fromlist=[""])
                module_status[mod] = "loaded"
            except:
                module_status[mod] = "missing"
        
        path = save_health_log(api_stats=api_stats, module_status=module_status)
        results["files"].append(path)
        print(f"  ✅ System Health: {path}")
    except Exception as e:
        results["errors"].append(f"health_log: {e}")
    
    # Summary
    err_count = len(results["errors"])
    print(f"\n{'✅' if err_count == 0 else '⚠️'} Shadow Mode 完成: {len(results['files'])} 文件, {err_count} 错误")
    if err_count:
        for err in results["errors"]:
            print(f"    {err}")
    
    return results


if __name__ == "__main__":
    run_shadow_mode()

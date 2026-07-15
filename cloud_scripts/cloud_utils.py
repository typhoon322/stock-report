"""cloud_utils.py — shared utilities for cloud scripts"""
from datetime import datetime, timezone, timedelta
import time, os, json

BJT = timezone(timedelta(hours=8))

def bjt_now():
    return datetime.now(BJT)

def bjt_format(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def retry_with_backoff(func, name="", max_retries=3):
    """Call func() with exponential backoff on failure"""
    for attempt in range(max_retries):
        try:
            result = func()
            return result, True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"   ⚠ {name} 失败: {e}")
                return None, False

def write_report_log(report_type, status="success", errors=None):
    """Write a lightweight execution log"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{report_type}_log.json")
    log_entry = {
        "type": report_type,
        "status": status,
        "time": bjt_now().isoformat(),
        "errors": errors or []
    }
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)
    print(f"   日志: {log_path}")

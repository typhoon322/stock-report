"""
cloud_utils.py — Shared utilities for all cloud report scripts.
- retry_with_backoff: Retry failed API calls with exponential backoff
- write_report_log: Append a structured log entry to docs/report_log.json
- bjt_now / bjt_format: Beijing time (UTC+8) helpers
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT, "docs", "report_log.json")

BJT = timezone(timedelta(hours=8))

def bjt_now():
    """Return current datetime in Beijing timezone."""
    return datetime.now(BJT)

def bjt_format(dt=None):
    """Format as '北京时间 2026年06月26日 18:23'"""
    if dt is None:
        dt = bjt_now()
    return f"北京时间 {dt.strftime('%Y年%m月%d日 %H:%M')}"


def retry_with_backoff(func, name, max_retries=3, base_delay=2):
    """
    Retry a callable with exponential backoff.
    Returns (result, ok_flag) where result is None if all retries fail.
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            result = func()
            if result is None or (hasattr(result, 'empty') and result.empty):
                raise ValueError("Empty result")
            return result, True
        except Exception as e:
            last_err = str(e)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"  ⚠️ {name} retry {attempt+1}/{max_retries} (delay {delay}s): {last_err}")
                time.sleep(delay)
            else:
                print(f"  ❌ {name} FAILED after {max_retries} attempts: {last_err}")
    return None, False


def write_report_log(report_name, status="success", errors=None, extra=None):
    """Append a structured log entry to docs/report_log.json."""
    now = bjt_now()
    entry = {
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "timezone": "UTC+8",
        "report": report_name,
        "status": status,
    }
    if errors:
        entry["errors"] = errors if isinstance(errors, list) else [errors]
    if extra:
        entry["extra"] = extra

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except (json.JSONDecodeError, FileNotFoundError):
            logs = []

    logs.append(entry)
    # Keep last 500 entries
    if len(logs) > 500:
        logs = logs[-500:]

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    print(f"  📝 Log appended: {report_name} {entry['time']} {status}")

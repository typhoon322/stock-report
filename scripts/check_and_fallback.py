#!/usr/bin/env python3
"""
check_and_fallback.py — 云端延迟→本地兜底
检查指定报告是否新鲜，若不新鲜则本地生成并推送GitHub

用法: python3 scripts/check_and_fallback.py [closing|midday|morning|weekly]
"""
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPORTS = {
    "closing": {
        "file": "docs/closing_report.html",
        "script": "cloud_scripts/cloud_closing.py",
        "name": "收盘报告",
    },
    "midday": {
        "file": "docs/midday_report.html",
        "script": "cloud_scripts/cloud_midday.py",
        "name": "午盘报告",
    },
    "morning": {
        "file": "docs/morning_report.html",
        "script": "cloud_scripts/cloud_morning.py",
        "name": "早盘报告",
    },
    "weekly": {
        "file": "docs/weekly_report.html",
        "script": "cloud_scripts/cloud_weekly.py",
        "name": "周报",
    },
    "dashboard": {
        "file": "docs/dashboard.html",
        "script": "generate_dashboard.py",
        "name": "量化仪表盘",
    },
}


def is_stale(filepath):
    """Check if report file exists and contains today's date"""
    if not os.path.exists(filepath):
        return True, "file_missing"

    today_str = datetime.now(BJT).strftime("%Y-%m-%d")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read(500)

    if today_str not in content:
        return True, "date_mismatch"

    return False, "fresh"


def find_python():
    """Find a working Python 3 interpreter with akshare installed"""
    candidates = [
        "/Users/yanx/.workbuddy/binaries/python/envs/default/bin/python",
        "/Users/yanx/.workbuddy/binaries/python/versions/3.13.12/bin/python3",
        "/usr/local/bin/python3",
        sys.executable,
    ]
    for py in candidates:
        if os.path.exists(py):
            return py
    return sys.executable


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check_and_fallback.py <report_name>")
        print(f"Available: {list(REPORTS.keys())}")
        sys.exit(1)

    report_name = sys.argv[1]

    if report_name not in REPORTS:
        print(f"Unknown report: {report_name}. Available: {list(REPORTS.keys())}")
        sys.exit(1)

    cfg = REPORTS[report_name]
    filepath = os.path.join(ROOT, cfg["file"])

    print(f"🔍 检查 {cfg['name']} ({cfg['file']})...")

    stale, reason = is_stale(filepath)
    if not stale:
        print(f"  ✅ {cfg['name']} 已是最新，无需重新生成")
        return

    print(f"  ⚠️ {cfg['name']} 过时/缺失 (原因: {reason})，启动本地兜底生成...")
    print(f"  📅 今日: {datetime.now(BJT).strftime('%Y-%m-%d %H:%M')} BJT")

    # Run the generation script
    script_path = os.path.join(ROOT, cfg["script"])
    python = find_python()

    print(f"  🐍 使用解释器: {python}")
    print(f"  📜 执行脚本: {script_path}")

    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT

    result = subprocess.run(
        [python, script_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f"  ❌ 生成脚本失败 (exit code {result.returncode})")
        sys.exit(1)

    # Verify output
    if not os.path.exists(filepath):
        print(f"  ❌ 脚本运行完成但未生成 {cfg['file']}")
        sys.exit(1)

    still_stale, _ = is_stale(filepath)
    if still_stale:
        print(f"  ⚠️ 生成的文件仍不含今日日期，可能数据源异常 — 仍将推送")

    # ── Update data status counter ──
    print(f"\n📊 更新数据收集天数...")
    status_script = os.path.join(ROOT, "scripts", "update_data_status.py")
    if os.path.exists(status_script):
        r = subprocess.run([python, status_script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        print(f"  {r.stdout.strip()}")
        tracking_files.append("docs/data_status.json")

    # Git push
    print(f"\n🚀 推送到GitHub (origin/master)...")
    tracking_files = [cfg["file"], "docs/report_log.json"]

    # Only add files that exist
    existing = [f for f in tracking_files if os.path.exists(os.path.join(ROOT, f))]
    if not existing:
        print("  ⚠️ 无可推送文件")
        return

    commit_msg = f"Auto: {cfg['name']} 本地兜底 {datetime.now(BJT).strftime('%m-%d %H:%M')}"

    commands = [
        (["git", "add"] + existing, "git add"),
        (["git", "commit", "-m", commit_msg], "git commit"),
        (["git", "push", "origin", "HEAD"], "git push"),
    ]

    for cmd, label in commands:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
        combined = (r.stdout + r.stderr).lower()
        if r.returncode == 0 or "nothing to commit" in combined or "up to date" in combined:
            print(f"  ✅ {label}")
        elif "everything up-to-date" in combined:
            print(f"  ✅ {label} (up-to-date)")
        else:
            print(f"  ⚠️ {label}: {r.stderr.strip()[:200]}")

    print(f"\n✅ {cfg['name']} 本地兜底完成 → GitHub 已推送")


if __name__ == "__main__":
    main()

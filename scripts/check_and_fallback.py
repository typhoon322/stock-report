#!/usr/bin/env python3
"""
check_and_fallback.py — Report freshness checker + local fallback generator.

Usage: python scripts/check_and_fallback.py <report>
  report: morning | midday | closing | all

At check time:
1. git pull latest from GitHub
2. Check if target report HTML contains today's date
3. If missing → generate locally + commit + push

Designed as a WorkBuddy automation companion to GitHub Actions cron.
"""
import os, sys, subprocess, re
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPORTS = {
    "morning": {
        "check_after": (8, 30),       # 08:30 BJT check
        "expected_cron": "08:15 BJT",
        "html": "docs/morning_report.html",
        "script": "cloud_scripts/cloud_morning.py",
    },
    "midday": {
        "check_after": (12, 0),       # 12:00 BJT check
        "expected_cron": "11:35 BJT",
        "html": "docs/midday_report.html",
        "script": "cloud_scripts/cloud_midday.py",
    },
    "closing": {
        "check_after": (15, 30),      # 15:30 BJT check
        "expected_cron": "15:05 BJT",
        "html": "docs/closing_report.html",
        "script": "cloud_scripts/cloud_closing.py",
    },
}


def _run(cmd, cwd=ROOT, timeout=120):
    """Run a shell command, return output."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def check_and_fallback(report_name):
    """Check one report and fallback if missing."""
    cfg = REPORTS[report_name]
    today = datetime.now(BJT).strftime("%Y-%m-%d")
    now_str = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")

    print(f"\n{'='*50}")
    print(f"🔍 Fallback check: {report_name} @ {now_str}")
    print(f"   预期 cron: {cfg['expected_cron']}")
    print(f"{'='*50}")

    # ── Step 1: git pull ──
    print("[1/4] Pulling latest from GitHub...")
    code, out, err = _run(["git", "pull", "origin", "main"])
    if code == 0:
        already = "Already up to date" in out
        print(f"   {'✅ Already current' if already else f'📥 Pulled:{out[:80]}'}")
    else:
        print(f"   ⚠️  Pull failed (continuing anyway): {err[:60]}")

    # ── Step 2: Check freshness ──
    print(f"[2/4] Checking {cfg['html']} for {today}...")
    html_path = os.path.join(ROOT, cfg["html"])

    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Check both <title> and the timestamp line
        has_today = today in content
        if has_today:
            print(f"   ✅ Report already has {today} data — no fallback needed")
            return {"report": report_name, "status": "already_fresh", "date": today}
        else:
            old_date = re.search(r'2026-\d{2}-\d{2}', content)
            old = old_date.group(0) if old_date else "unknown"
            print(f"   ❌ Report is stale ({old}), need to regenerate")
    else:
        print(f"   ❌ {cfg['html']} not found, need to generate")

    # ── Step 3: Generate locally ──
    print(f"[3/4] Generating {report_name} report locally...")
    script_path = os.path.join(ROOT, cfg["script"])
    code, out, err = _run(["python3", script_path], timeout=180)

    if code == 0:
        print(f"   ✅ Generated successfully")
        if out:
            for line in out.split("\n")[-5:]:
                print(f"      {line}")
    else:
        print(f"   ❌ Generation failed (code={code})")
        print(f"   stderr: {err[:200]}")
        return {"report": report_name, "status": "generation_failed", "date": today, "error": err[:200]}

    # ── Step 4: Commit + push ──
    print("[4/4] Committing + pushing...")
    _run(["git", "add", cfg["html"], "docs/report_log.json"])
    code, out, err = _run([
        "git", "commit", "-m",
        f"📊 {report_name} {today} (local fallback — Actions cron delayed)"
    ])
    if code != 0 and "nothing to commit" not in out + err:
        print(f"   ⚠️  Commit warning: {out[:80]} {err[:80]}")

    code, out, err = _run(["git", "push", "origin", "main"])
    if code == 0:
        print(f"   ✅ Pushed to GitHub")
    else:
        print(f"   ⚠️  Push warning: {err[:80]}")

    return {"report": report_name, "status": "fallback_generated", "date": today}


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    today = datetime.now(BJT)

    if arg == "all":
        # Check all reports that should have run by now
        bjth = today.hour
        bjtm = today.minute

        results = []
        for name, cfg in REPORTS.items():
            ch = cfg["check_after"]
            if bjth > ch[0] or (bjth == ch[0] and bjtm >= ch[1]):
                results.append(check_and_fallback(name))
            else:
                print(f"\n⏭️  {name}: not yet {cfg['check_after'][0]:02d}:{cfg['check_after'][1]:02d}, skipping")

        # Summary
        print(f"\n{'='*50}")
        fresh = sum(1 for r in results if r["status"] == "already_fresh")
        gen = sum(1 for r in results if r["status"] == "fallback_generated")
        fail = sum(1 for r in results if r["status"] == "generation_failed")
        print(f"📊 Summary: {fresh} fresh, {gen} fallback, {fail} failed")
        print(f"{'='*50}")
    else:
        check_and_fallback(arg)


if __name__ == "__main__":
    main()

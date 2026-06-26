#!/usr/bin/env python3
"""
云效 Flow 统一执行脚本

四档 cron 合并为一个入口，根据北京时刻判断运行哪些报告。
时区: UTC+8 (TZ env=Asia/Shanghai)
"""
import os, sys, time
from datetime import datetime, timezone, timedelta

os.environ['TZ'] = 'Asia/Shanghai'
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

def _beijing_hour():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).hour, datetime.now(tz).strftime('%u')  # 1=Monday

def _now_str():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

def run(cmd: str, label: str):
    """Run a command, print result, never crash"""
    print(f"\n{'='*50}")
    print(f"[{_now_str()}] {label}")
    print(f"{'='*50}")
    ret = os.system(cmd)
    if ret != 0:
        print(f"  ⚠️ {label} 退出码={ret}")
    else:
        print(f"  ✅ {label} 完成")
    return ret

def git_push():
    """提交产出到 Gitee"""
    os.system("git config user.name 'aliyun-flow[bot]'")
    os.system("git config user.email 'flow@aliyun.com'")
    ret = os.system("git add docs/ rotation/archive/ history_cache/ 2>/dev/null; git diff --staged --quiet || git commit -m '📊 云效自动报告'")
    os.system("git pull --rebase origin main 2>/dev/null")
    ret2 = os.system("git push origin main 2>&1")
    print(f"  git push: {'✅' if ret2 == 0 else '⚠'}")

hour, weekday = _beijing_hour()
print(f"🚀 云效 Flow 启动 — 北京时间 {hour}:00  星期{weekday}")

results = []

# 早盘 8:00-9:00
if 8 <= hour <= 9:
    results.append(("🏙️ 早盘", run("python3 cloud_scripts/cloud_morning.py", "早盘报告")))

# 午盘 11:00-12:30
if 11 <= hour <= 12:
    results.append(("🌤️ 午盘", run("python3 cloud_scripts/cloud_midday.py", "午盘报告")))

# 收盘 15:00-16:00 (主跑)
if 15 <= hour <= 16:
    results.append(("🌙 收盘", run("python3 cloud_scripts/cloud_closing.py", "收盘报告")))
    results.append(("📦 归档", run("python3 -m rotation.archive.runner", "每日归档")))
    results.append(("📊 仪表盘", run("python3 generate_dashboard.py", "量化仪表盘")))
    
    # 周五加跑周报
    if weekday == '5':
        results.append(("📊 周报", run("python3 cloud_scripts/cloud_weekly.py", "周报")))

# 手动触发 (非 cron 时段)
if hour not in [8, 9, 11, 12, 15, 16]:
    print("🔧 手动触发 → 全量生成")
    for label, cmd in [
        ("早盘", "python3 cloud_scripts/cloud_morning.py"),
        ("午盘", "python3 cloud_scripts/cloud_midday.py"),
        ("收盘", "python3 cloud_scripts/cloud_closing.py"),
        ("归档", "python3 -m rotation.archive.runner"),
        ("仪表盘", "python3 generate_dashboard.py"),
        ("周报", "python3 cloud_scripts/cloud_weekly.py"),
    ]:
        results.append((label, run(cmd, label)))

# 推送
print(f"\n{'='*50}")
print("📤 推送结果到 Gitee...")
git_push()

# 总结
fails = [name for name, code in results if code != 0]
print(f"\n{'='*50}")
print(f"总结: {len(results)} 任务, {len(fails)} 失败")
if fails:
    print(f"  失败: {', '.join(fails)}")
else:
    print("  ✅ 全部成功")

# 列出产出
print(f"\n产出文件:")
for pattern in ['docs/*.html', 'rotation/archive/raw/*.json', 'rotation/archive/signal/*.json']:
    os.system(f"ls -lh {pattern} 2>/dev/null | tail -3")

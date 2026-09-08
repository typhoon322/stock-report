#!/usr/bin/env python3
"""
generate_quant_daily.py — 生成 docs/quant_daily.html (量化日报)

封装 rotation.report 的 generate_daily_report() + report_to_html(),
供 GitHub Actions 每日 workflow 调用 (原 README 里是手写 python -c,
无独立脚本、也无 workflow,导致 2026-06 起停更)。

用法:  python generate_quant_daily.py
依赖:  akshare (实时行情, 需联网)
"""
import os

from rotation.report import generate_daily_report, report_to_html

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    print("🧠 量化日报生成中...")
    html = report_to_html(generate_daily_report())
    out = os.path.join(ROOT, "docs", "quant_daily.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ quant_daily.html ({len(html)} chars) -> {out}")


if __name__ == "__main__":
    main()

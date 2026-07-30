#!/usr/bin/env bash
# 每日归档 -> 刷新状态 -> 推送到 GitHub (供 GitHub Pages 看板使用)
# 归档文件(signal/raw/trade)与 HTML 报告由 GitHub Actions 负责推送；
# 本脚本只负责把 docs/data_status.json 同步到远程，避免重复提交造成冲突。
set -e
cd "$(dirname "$0")"

echo "[$(date +%F\ %T)] 1/4 运行归档流水线"
python -m rotation.archive.runner
python scripts/update_data_status.py

echo "[$(date +%F\ %T)] 2/4 丢弃本地归档/报告写入 (GitHub Actions 拥有并推送这些)"
git checkout -- rotation/archive/ docs/ 2>/dev/null || true
git clean -fd rotation/archive/ 2>/dev/null || true

echo "[$(date +%F\ %T)] 3/4 拉取远程最新 (合并 GitHub Actions 报告)"
git pull --rebase origin main 2>&1 || git pull --rebase origin main

echo "[$(date +%F\ %T)] 4/4 仅提交并推送 data_status.json"
git add docs/data_status.json
if git diff --cached --quiet; then
  echo "data_status 无变化，无需推送"
  exit 0
fi
git commit -m "data: daily sync $(date +%F)" 2>&1
git push origin main 2>&1
echo "DONE"

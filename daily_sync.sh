#!/usr/bin/env bash
# 同步 docs/data_status.json 到 GitHub Pages
# 归档文件(signal/raw/trade)与 HTML 报告由 GitHub Actions 负责采集并推送;
# 本脚本只把看板指标 data_status.json 与远程实际归档对齐后推送。
# 设计要点:
#  - 不跑 akshare(避免网络抖动), 只 pull GA 的归档 -> 重算 data_status -> 推送。
#  - rebase 若因历史归档文件(7/15 回填提交)与 GA 冲突, 自动以远程( theirs )为准解决。
#  - 不会误还原 data_status.json (旧版 bug)。
set -e
cd "$(dirname "$0")"

echo "[$(date +%F\ %T)] 1/4 清理本地写入(缓存/未跟踪归档), 保持可 rebase"
git checkout -- . 2>/dev/null || true
git clean -fd rotation/archive 2>/dev/null || true

echo "[$(date +%F\ %T)] 2/4 拉取远程最新 (合并 GitHub Actions 报告/归档)"
if ! git pull --rebase origin main 2>/dev/null; then
  echo "  rebase 冲突, 自动以远程为准解决归档文件"
  git checkout --theirs -- rotation/archive/ 2>/dev/null || true
  git add -- rotation/archive/ 2>/dev/null || true
  git checkout --ours -- docs/data_status.json daily_sync.sh 2>/dev/null || true
  git add -- docs/data_status.json daily_sync.sh 2>/dev/null || true
  GIT_EDITOR=true git rebase --continue 2>/dev/null || true
fi

echo "[$(date +%F\ %T)] 3/4 依据实际归档刷新 data_status.json"
python scripts/update_data_status.py

echo "[$(date +%F\ %T)] 4/4 仅提交并推送 data_status.json"
git add docs/data_status.json
if git diff --cached --quiet; then
  echo "data_status 无变化, 跳过推送"
  exit 0
fi
git commit -m "data: daily sync $(date +%F)"
git pull --rebase origin main 2>/dev/null || git pull --rebase origin main
git push origin main 2>&1
echo DONE

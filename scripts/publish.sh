#!/bin/bash
# AI Daily 发布脚本 — 检查 posts/ 变更后 git add → commit → push

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

DATE_STR="$(date '+%Y-%m-%d')"

# 检查是否有变更
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard posts/)" ]; then
    echo "[PUBLISH] 无新内容，跳过发布。"
    exit 0
fi

git add posts/

# 统计变更文件数
FILE_COUNT=$(git diff --cached --name-only -- posts/ | wc -l | tr -d ' ')
COMMIT_MSG="daily: $DATE_STR - $FILE_COUNT files"

echo "[PUBLISH] 提交: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo "[PUBLISH] 推送到 GitHub ..."
git push -u origin main 2>/dev/null || git push

echo "[PUBLISH] 发布完成!"

#!/usr/bin/env bash

# 严格模式：任何命令失败直接退出；未定义变量即报错；管道中任一失败即退出。
set -euo pipefail

# 获取脚本所在目录，并定位仓库根目录（当前脚本放在 repo/src/ 下）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_DIR"

# 显式使用北京时间，确保“今天”的日期与日报文件一致。
DATE="$(TZ=Asia/Shanghai date +%F)"

# 1) 先生成日报数据：关闭内置 editor-picks，避免与 Codex 版本重复。
python3 .codex/skills/rss-daily-report/scripts/run.py "$DATE" --no-editor-picks --no-build-site

# 2) 再调用 Codex 的 rss-editor-picks 做“头条/精选”回写。
#    注意："$rss-editor-picks" 中的 "$" 是 Codex 的技能引用语法，
#    不能被 shell 展开成变量，因此这里显式转义 "$"。
CODEX_FAILED=0
CODEX_PROMPT="\$rss-editor-picks $DATE"
if ! codex exec --full-auto --sandbox workspace-write "$CODEX_PROMPT"; then
  CODEX_FAILED=1
  echo "[warn] codex exec failed, committing without editor picks" >&2
fi

# 3) 仅当 NewsReport 目录有变更时才提交，避免 cache 或其他噪声触发提交。
if [[ -n "$(git status --porcelain -- NewsReport)" ]]; then
  git add NewsReport
  if [[ "$CODEX_FAILED" -eq 1 ]]; then
    git commit -m "chore: daily report $DATE (no picks)"
  else
    git commit -m "chore: daily report $DATE"
  fi
  git push
else
  echo "No changes under NewsReport, skip commit."
fi

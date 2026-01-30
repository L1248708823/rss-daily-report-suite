#!/usr/bin/env bash

# 严格模式：任何命令失败直接退出；未定义变量即报错；管道中任一失败即退出。
set -euo pipefail

# 获取脚本所在目录，并定位仓库根目录（当前脚本放在 repo/src/ 下）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_DIR"

# 显式使用北京时间，确保“今天”的日期与日报文件一致。
DATE="$(TZ=Asia/Shanghai date +%F)"

# Codex 可执行路径（线上实际路径）。
CODEX="/home/ubuntu/.volta/bin/codex"
if [[ ! -x "$CODEX" ]]; then
  echo "[error] codex not found: $CODEX" >&2
  exit 1
fi

# 1) 先生成日报数据：关闭内置 editor-picks，避免与 Codex 版本重复。
OPENAI_API_KEY= python3 .codex/skills/rss-daily-report/scripts/run.py "$DATE" --no-ai --no-editor-picks --no-build-site

# 2) 再调用 Codex 的 rss-editor-picks 做“头条/精选”回写。
#    注意："$rss-editor-picks" 中的 "$" 是 Codex 的技能引用语法，
#    不能被 shell 展开成变量，因此这里显式转义 "$"。
CODEX_PROMPT="\$rss-editor-picks $DATE"
# 允许外部覆盖超时（单位：秒），默认 15 分钟。
CODEX_EXEC_TIMEOUT_SEC="${CODEX_EXEC_TIMEOUT_SEC:-300}"

if command -v timeout >/dev/null 2>&1; then
  if ! timeout --signal=INT --kill-after=30s "${CODEX_EXEC_TIMEOUT_SEC}"       "$CODEX" exec --full-auto --sandbox workspace-write "$CODEX_PROMPT"; then
    echo "[warn] codex exec failed or timed out, continue."
  fi
else
  if ! "$CODEX" exec --full-auto --sandbox workspace-write "$CODEX_PROMPT"; then
    echo "[warn] codex exec failed, continue."
  fi
fi

# 3) 仅当 NewsReport 目录有变更时才提交，避免 cache 或其他噪声触发提交。
if [[ -n "$(git status --porcelain -- NewsReport)" ]]; then
  git add NewsReport
  git commit -m "chore: daily report $DATE"
  git push
else
  echo "No changes under NewsReport, skip commit."
fi

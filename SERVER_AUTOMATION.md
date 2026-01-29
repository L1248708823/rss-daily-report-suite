# 服务器定时执行方案（systemd）

> 目标：每天 09:00（Asia/Shanghai）生成日报 → Codex 进行“头条/精选”回写 → 有变更才提交并触发 GitHub Actions。

## 0. 结论摘要（当前对齐）
- 调度：systemd timer（每日 09:00，带补跑）
- 运行用户：非 root 专用用户（示例：`rssbot`）
- 执行链路：`run.py --no-editor-picks` → `codex exec $rss-editor-picks` → `git add/commit/push`
- 失败策略：Codex 失败仍提交“未精选版”（通知预留为空）
- 执行脚本：仓库 `src/run_daily.sh`

## 1. 前置条件（纯净服务器需要准备）
- OS：Linux 且有 systemd
- Python：3.10+（并安装 `requests`）
- 工具：`git`、`codex`（你已安装）
- 网络：可访问 RSS 源；Codex 需要可访问 OpenAI（若用账号登录需保证缓存可读）
- 时区：统一为 `Asia/Shanghai`（建议在 systemd 单元里显式设置）

## 2. 运行用户与权限策略（推荐）
- 创建非 root 用户（示例 `rssbot`），仅授予仓库读写权限
- Git 凭证归属 `rssbot`（SSH key 或 token）
- Codex 认证归属 `rssbot`（`~/.codex/`）
- 运行目录建议固定：`/mnt/e/skills/rss-daily-report-suite`

## 3. 任务流程（精简且可追溯）
1) 计算日期（按北京时间）：
```bash
DATE="$(TZ=Asia/Shanghai date +%F)"
```
2) 生成日报（避免重复调用本地 editor script）：
```bash
python3 .codex/skills/rss-daily-report/scripts/run.py "$DATE" --no-editor-picks --no-build-site
```
3) Codex 精选回写（同一天）：
```bash
codex exec --full-auto --sandbox workspace-write "$rss-editor-picks $DATE"
```
4) 仅在 NewsReport 有变更时提交：
```bash
git status --porcelain -- NewsReport
git add NewsReport
git commit -m "chore: daily report $DATE"
git push
```
> 说明：Codex 失败仍会提交“未精选版”，脚本会给出 warn 提示。

## 4. systemd 配置（模板已落地）

### 4.1 执行脚本（已落地）
路径：`/mnt/e/skills/rss-daily-report-suite/src/run_daily.sh`
```bash
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
```

### 4.2 Service 单元（模板）
路径：`/mnt/e/skills/rss-daily-report-suite/src/rss-daily-report.service`
```ini
[Unit]
Description=RSS Daily Report (generate + editor picks + git push)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=rssbot
WorkingDirectory=/mnt/e/skills/rss-daily-report-suite
Environment=TZ=Asia/Shanghai
# 如果 codex 不在 PATH，可显式设置 PATH
# Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/bin/bash /mnt/e/skills/rss-daily-report-suite/src/run_daily.sh

[Install]
WantedBy=multi-user.target
```

### 4.3 Timer 单元（每日 09:00）
路径：`/mnt/e/skills/rss-daily-report-suite/src/rss-daily-report.timer`
```ini
[Unit]
Description=RSS Daily Report Timer

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 4.4 启用步骤（一次性）
```bash
# 1) 确保脚本可执行
chmod +x /mnt/e/skills/rss-daily-report-suite/src/run_daily.sh

# 2) 复制模板到 systemd 目录
sudo cp /mnt/e/skills/rss-daily-report-suite/src/rss-daily-report.service /etc/systemd/system/
sudo cp /mnt/e/skills/rss-daily-report-suite/src/rss-daily-report.timer /etc/systemd/system/

# 3) 重新加载并启用定时器
sudo systemctl daemon-reload
sudo systemctl enable --now rss-daily-report.timer
```

## 5. 日志与排查
- `systemctl status rss-daily-report.service`
- `journalctl -u rss-daily-report.service -n 200 --no-pager`

## 6. 通知预留（暂空）
- 预留在脚本中加入通知钩子（邮件/IM/企业微信等），当前不实现。

## 7. 已确认项（供回顾）
- Git 推送目标分支：`main`
- `cache.json` 不提交；仅提交 `NewsReport/`
- 执行脚本放在仓库 `src/run_daily.sh`


## 8.手动执行
- codex exec --full-auto --sandbox workspace-write "\$rss-editor-picks $(TZ=Asia/Shanghai date +%F)"

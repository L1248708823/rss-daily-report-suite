# 服务器定时执行方案（systemd）

> 目标：每天 09:00（Asia/Shanghai）生成日报 → Codex 进行“头条/精选”回写 → 有变更才提交并推送。

## 0. 结论摘要（当前对齐）
- 调度：systemd timer（每日 09:00，带补跑）
- 运行用户：`ubuntu`（与当前线上环境一致）
- 执行链路：`run.py --no-editor-picks` → `codex exec $rss-editor-picks` → `git add NewsReport` → commit/push
- 失败策略：**Codex 失败则整体失败，不 push**
- 执行脚本：仓库 `src/run_daily.sh`

## 1. 前置条件（线上需满足）
- OS：Linux 且有 systemd
- Python：3.10+（并安装 `requests`）
- 工具：`git`、`codex`
- 网络：可访问 RSS 源；Codex 可访问 OpenAI（登录或 API Key 已可用）
- 时区：使用 `Asia/Shanghai`（service 中显式设置）

## 2. 运行用户与权限策略（当前实际）
- 使用 `ubuntu` 用户
- Git 凭证归属 `ubuntu`（SSH key 可写）
- Codex 认证归属 `ubuntu`（`/home/ubuntu/.codex/`）
- 仓库路径：`/srv/services/rss-daily-report-suite`

## 3. 任务流程（精简且可追溯）
1) 计算日期（按北京时间）：
```bash
DATE="$(TZ=Asia/Shanghai date +%F)"
```
2) 生成日报（关闭内置 editor-picks，避免重复）：
```bash
python3 .codex/skills/rss-daily-report/scripts/run.py "$DATE" --no-editor-picks --no-build-site
```
3) Codex 精选回写：
```bash
/home/ubuntu/.volta/bin/codex exec --full-auto --sandbox workspace-write "\$rss-editor-picks $DATE"
```
4) 仅在 NewsReport 有变更时提交并推送：
```bash
git status --porcelain -- NewsReport
git add NewsReport
git commit -m "chore: daily report $DATE"
git push
```

> 注意：我们只提交 `NewsReport/`，避免把 cache 等噪声产物提交进仓库。

## 4. systemd 配置（模板已落地）

### 4.1 执行脚本（已落地）
路径：`/srv/services/rss-daily-report-suite/src/run_daily.sh`

要点：
- 失败即退出，不进行 push
- 仅提交 `NewsReport/`

### 4.2 Service 单元（模板）
路径：`/srv/services/rss-daily-report-suite/src/rss-daily-report.service`
```ini
[Unit]
Description=RSS Daily Report (generate + editor picks + git push)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/srv/services/rss-daily-report-suite
Environment=TZ=Asia/Shanghai
Environment=HOME=/home/ubuntu
Environment=PATH=/usr/local/bin:/usr/bin:/bin:/home/ubuntu/.volta/bin
ExecStart=/bin/bash /srv/services/rss-daily-report-suite/src/run_daily.sh

[Install]
WantedBy=multi-user.target
```

### 4.3 Timer 单元（每日 09:00）
路径：`/srv/services/rss-daily-report-suite/src/rss-daily-report.timer`
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
chmod +x /srv/services/rss-daily-report-suite/src/run_daily.sh

# 2) 复制模板到 systemd 目录
sudo cp /srv/services/rss-daily-report-suite/src/rss-daily-report.service /etc/systemd/system/
sudo cp /srv/services/rss-daily-report-suite/src/rss-daily-report.timer /etc/systemd/system/

# 3) 重新加载并启用定时器
sudo systemctl daemon-reload
sudo systemctl enable --now rss-daily-report.timer
```

## 5. 日志与排查
- `systemctl status rss-daily-report.service`
- `journalctl -u rss-daily-report.service -n 200 --no-pager`

## 6. 需要额外确认的点（执行前）
- git 用户信息（`user.name`/`user.email`）已配置，否则 commit 会失败。
- 若仓库路径或运行用户发生变化，需要同步更新 service。

## 7. 手动执行（一次性验证）
```bash
/srv/services/rss-daily-report-suite/src/run_daily.sh
```

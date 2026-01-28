---
name: rss-daily-report
description: 从可配置的 RSS/Atom 源列表抓取条目并生成当天 Markdown/JSON 日报数据；推荐与 $rss-editor-picks 配合进行二次编辑回写（头条/精选/摘要优化/软删除）。
argument-hint: [可选: 日期]
disable-model-invocation: false
user-invocable: true
---

# RSS Daily Report

这个 skill 只负责把 RSS/Atom 拉取、去重、分类/打分并生成当天数据文件；“编辑部式二次加工”（头条/精选、摘要改写、软删除）统一交给 `$rss-editor-picks`。

## 最短流程（推荐）

### 0) 准备源列表（只选一种）

- 默认源列表：`.codex/skills/rss-daily-report/sources.md`
- 推荐个人入口：维护 `my/sources.checklist.md`，同步生成 `my/sources.md`
  - 同步命令：`python3 .codex/skills/rss-daily-report/scripts/sync_sources.py`

（可选）仓库根目录放 `my/config.json` 作为默认参数入口（代理/配额/启用源文件等）。

### 1) 生成日报数据（今天 / 指定日期）

建议生成阶段关闭自动“编辑回写”，避免覆盖后续编辑结果：

- 今天：`python3 .codex/skills/rss-daily-report/scripts/run.py --no-editor-picks`
- 指定日期：`python3 .codex/skills/rss-daily-report/scripts/run.py YYYY-MM-DD --no-editor-picks`

输出文件（相对仓库根目录）：

- 日数据：`NewsReport/data/YYYY-MM-DD.json`
- 索引：`NewsReport/data/index.json`
- 日报：`NewsReport/YYYY-MM-DD-rss-daily-report.md`
- 缓存：`.codex/skills/rss-daily-report/cache.json`

### 2) 编辑精选（由 AI 执行）

用 Codex CLI 显式调用 `$rss-editor-picks`（需已配置模型访问能力，例如已登录/已设置 Key）：

- 今天：`codex exec --full-auto --sandbox workspace-write "$rss-editor-picks"`
- 指定日期：`codex exec --full-auto --sandbox workspace-write "$rss-editor-picks YYYY-MM-DD"`

编辑规范与输出约束见：`.codex/skills/rss-editor-picks/SKILL.md`（含：合集摘要改写、全来源软删除、写入 `meta.removed_items[]`、幂等更新 Markdown 区块等）。

### 3)（可选）提交并触发部署

如果你走“服务器定时 → push → GitHub Actions → Pages”：

- `git add NewsReport site .codex/skills/rss-daily-report/cache.json`
- `git commit -m "chore: daily report YYYY-MM-DD"`
- `git push`

## 更多配置（避免文档随版本失效）

- 所有可用参数以脚本帮助为准：`python3 .codex/skills/rss-daily-report/scripts/run.py --help`

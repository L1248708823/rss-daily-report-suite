---
name: rss-editor-picks
description: 基于当天 NewsReport/data 的 JSON，自动挑选 1 条【头条】+ 5 条【精选】，并回写 pin/title_zh/summary，同时在 Markdown 日报中插入“头条/精选”区块（不依赖任何 API/key）。
argument-hint: [可选: 日期]
disable-model-invocation: false
user-invocable: true
---

# RSS Editor Picks（头条 / 精选）

这个 skill 用于在日报产出后，做一次“编辑精选”后处理：

- 从 `NewsReport/data/YYYY-MM-DD.json` 的 `items` 里选出：
  - 头条（`pin=lead`）1 条
  - 精选（`pin=top`）5 条
- 回写到当天 JSON（方便 web 端直接展示/过滤）
- 同步把“头条/精选”区块写入 `NewsReport/YYYY-MM-DD-rss-daily-report.md`

特性：

- 不依赖任何 API/key
- 偏好技术/财经/信息密度高的内容；“有趣但有价值”的也可能入选
- 若英文标题/摘要缺少中文，会做“尽力翻译/中文化”的兜底（离线规则）
- 若条目是“热榜/合集”类，会把摘要改写成更像“这条合集到底讲了什么”

## 使用

- 处理今天：`python3 .codex/skills/rss-editor-picks/scripts/run.py`
- 处理指定日期：`python3 .codex/skills/rss-editor-picks/scripts/run.py YYYY-MM-DD`

常用参数：

- `--lead-n 1`：头条条数（默认 1）
- `--top-n 5`：精选条数（默认 5）
- `--min-top-tech 2`：精选中至少包含 N 条“技术向”（默认 2，尽力满足）
- `--day-json PATH`：指定当天 JSON 路径（默认按日期推导）
- `--report-md PATH`：指定当天 Markdown 路径（默认按日期推导）

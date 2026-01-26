---
name: rss-daily-report
description: 从可配置的 RSS/Atom 源列表抓取条目，去重后生成最多 50 条的 Markdown 日报；支持按平台热度（默认）或按主题分类输出，并维护 cache.json（可选用 OpenAI 生成中文摘要/要点/关键词）。
argument-hint: [可选: 日期]
disable-model-invocation: false
user-invocable: true
---

# RSS Daily Report（可发布版 Skill）

这个 skill 是一个**可发布给别人使用**的 Codex skill：不依赖任何“原作者技能包”，只需要本目录下的脚本与一个 RSS 源列表文件。

## 快速开始

1) 编辑源列表：

- 默认源列表：`.codex/skills/rss-daily-report/sources.md`
- 也可以参考示例：`.codex/skills/rss-daily-report/references/sources.example.md`

2) 生成今天日报（默认读取本 skill 里的 `sources.md`）：

- `python3 .codex/skills/rss-daily-report/scripts/run.py`

如果你不想每次都手敲一堆参数，可以在仓库根目录放一个 `my/config.json`（脚本会自动读取；用 `--no-config` 可禁用），例如：

- `{"defaults":{"per_feed_limit":30,"per_platform_limit":10,"time_budget":240,"sources":["my/sources.md"],"proxy":"http://127.0.0.1:7890"}}`

本仓库推荐的“选源方式”是只维护一份可勾选清单，然后一键同步生成启用源：

- 勾选：`my/sources.checklist.md`
- 同步：`python3 .codex/skills/rss-daily-report/scripts/sync_sources.py`（写入 `my/sources.md`）
- 生成：`python3 .codex/skills/rss-daily-report/scripts/run.py`

可选：在 checklist 的名称后追加 `|limit=15` / `|platform=Foo` / `|fallback=https://...`，同步后会写入 `my/sources.md`（用于“每个源抓几条/兜底端点”的可维护配置）。

如果你有一份“RSS 源目录”（Markdown 表格）+ 一份“关键 key 列表”（你想要的平台/来源名），也可以这样跑（可选）：

- `python3 .codex/skills/rss-daily-report/scripts/run.py --sources RSS源.md --select-keys-file my/RSS.md --group-by platform --per-platform-limit 10 --max-items 0 --per-feed-limit 30`

如果还想额外加一个“国外时政”单独 section：从源目录里按关键词匹配出候选源，随机抽 3 个 feed URL，请求后按最近排序保留 10 条：

- `python3 .codex/skills/rss-daily-report/scripts/run.py --sources RSS源.md --select-keys-file my/RSS.md --group-by platform --per-platform-limit 10 --max-items 0 --per-feed-limit 30 --foreign-news-section`

3) 生成指定日期（YYYY-MM-DD）：

- `python3 .codex/skills/rss-daily-report/scripts/run.py 2026-01-22`

输出：

- 日报：`NewsReport/YYYY-MM-DD-rss-daily-report.md`
- 缓存：`.codex/skills/rss-daily-report/cache.json`

## 源列表格式（sources.md）

每行一个源，支持：

1) `名字<TAB>URL`
2) `URL`（名字会自动用域名代替）

可选：为“平台热度”设置权重（用于排序/分组），格式：

- `名字|80<TAB>URL`

可选：为单个源设置抓取条数/回退 URL（用于源站不通时重试其它端点），格式：

- `名字|limit=15<TAB>URL`
- `名字|fallback=https://mirror.example.com/feed<TAB>URL`
- `名字|80|limit=15|fallback=https://mirror.example.com/feed<TAB>URL`

支持 `https://` 的 RSS/Atom；空行与 `#` 注释行会被忽略。

此外，`--sources` 也支持读取“RSS 源目录”的 Markdown 表格（列名包含“名称 / RSS”即可），会自动从表格行里提取 `名称` + `RSS源`。

## 可选：AI 摘要（OpenAI）

不设置 key 也能跑（使用 feed 的 description 做摘要兜底）。

如需更像“编辑写的中文摘要/要点/关键词”：

- `export OPENAI_API_KEY='...'`
- 可选：`export OPENAI_MODEL='gpt-4o-mini'`
- 运行同上

英文条目增强（需要 AI）：

- 当标题主要为英文时，脚本会在日报里输出中文标题翻译，并保留原标题。

关闭 AI（即使你设置了 key）：

- `python3 .codex/skills/rss-daily-report/scripts/run.py --no-ai`

## 运行参数（常用）

- `--max-items 50`：最多收录条数（默认 50；设为 `0` 表示不限制）
- `--per-feed-limit 10`：每个源最多取多少条候选
- `--min-score 2.6`：最低分（越高越“宁缺毋滥”）
- `--time-budget 120`：总时间预算（秒），超时会提前停
- `--group-by platform|topic|none`：输出分组方式（默认 `platform`；`none` 为不分组但仍按平台热度排序）
- `--platform-heat-window-days 30`：平台热度回看天数（仅 `--group-by platform` 生效）
- `--per-platform-limit 10`：每个平台最多保留 N 条（仅 `--group-by platform` 生效；默认 0 不开启）
- `--platform-top-by recent|quality`：开启 `--per-platform-limit` 时的选取方式（默认 `recent`）
- `--sources my/sources.md`：直接指定启用源列表（推荐配合 `sync_sources.py` 从 checklist 生成）
- `--select-keys-file my/RSS.md`：可选（旧模式），从 key 文件筛选平台/来源（1 行 1 个 key；key 会作为“平台”分组名）
- `--select-key "知乎"`：额外追加筛选 key（可重复）
- `--fresh-window-days 3`：新内容时间窗（默认 3 天；超出视为“库存补读”候选）
- `--fallback-fresh-top-k 3`：没有 published 时间时，用 feed 内顺序兜底：每个源只把 top-K 当作“新内容”
- `--backfill-daily-cap 3`：补读（历史库存）每天最多展示多少条（默认 3）
- `--backfill-per-platform-limit 1`：补读的“每平台上限”（默认 1）
- `--min-items-floor 20`：主列表展示保底条数（新内容不足时，从补读候选里补齐；默认 0 关闭）
- `--floor-per-platform-cap 3`：补齐时主列表的“每平台上限”（默认 3）
- `--circuit-breaker-fail-streak 3`：连续失败 N 次后熔断该源（默认 3）
- `--circuit-breaker-mute-days 2`：熔断持续天数（默认 2）
- `--foreign-news-section`：增加“国外时政”单独 section（随机抽 3 个 feed URL）
- `--foreign-source-key "world"`：识别“国外时政源”的关键词（可重复；默认内置一组关键词）
- `--foreign-sample-feeds 3`：随机抽取多少个 feed URL（默认 3）
- `--foreign-section-limit 10`：国外时政 section 最多保留多少条（默认 10）
- `--foreign-seed 2026-01-22`：随机种子（默认用日期做确定性随机，便于复现）
- `--dry-run`：只打印不落盘

## 流程图

```mermaid
flowchart TD
  A[Start] --> B[Read sources.md]
  B --> C[Fetch feeds concurrently<br/>short timeouts]
  C --> D[Parse entries<br/>title/link/summary/pubDate/enclosure]
  D --> E[Normalize + de-dup<br/>URL + title hash + cache TTL]
  E --> F[Classify topic + carrier<br/>tech/biz/life/news/finance/ent/other]
  F --> G[Score + sort]
  G --> H{AI enabled?}
  H -- Yes --> I[AI enrich: summary/key points/keywords/score]
  H -- No --> J[Fallback summary from feed]
  I --> K[Render Markdown (grouped)]
  J --> K
  K --> L[Write report + update cache]
  L --> M[Done]
```

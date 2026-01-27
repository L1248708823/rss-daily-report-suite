# 本地开发（MVP）

## 1) 选源：只改一个文件
- 勾选/取消勾选：`my/sources.checklist.md`
- 同步生成启用列表（会写 `my/sources.md`）：  
  `python3 .codex/skills/rss-daily-report/scripts/sync_sources.py`

## 2) 生成日报数据（会写入 NewsReport/data）
```bash
python3 .codex/skills/rss-daily-report/scripts/run.py
# 或指定日期
python3 .codex/skills/rss-daily-report/scripts/run.py 2026-01-26
```

## 3) 启动 Vue3 前端
```powershell
cd web
pnpm dev
```
浏览器打开：`http://localhost:5173`

## 4) 常见问题
- V2EX 你浏览器能开但脚本超时：通常是 WSL 网络/代理不同步；把代理填到 `my/config.json` 的 `defaults.proxy`。
- 今日条目很少：先看日报里的“抓取明细/失败原因”，再看是否被 `min_score`/平台限额过滤。

---

# 业务流程（rss-daily-report + rss-editor-picks）

## 分层职责

- `rss-daily-report`：抓取 RSS/Atom → 去重 → 分类/打分 → 产出主列表 `items`（以及 `backfill_items`）到 Markdown/JSON。
- `rss-editor-picks`：编辑后处理，从当天 `items` 里挑选 1 条【头条】+ 5 条【精选】，并回写 `pin/title_zh/summary`，同时把“头条/精选”区块插入日报 Markdown 顶部。

## 产物与关键字段

- 日报：`NewsReport/YYYY-MM-DD-rss-daily-report.md`
  - 顶部插入区块：`<!-- editorial-picks:start --> ... <!-- editorial-picks:end -->`
- 数据：`NewsReport/data/YYYY-MM-DD.json`
  - `items[]`：当天主列表（Web 默认阅读）
  - `backfill_items[]`：补读条目（用于保底补齐/回顾）
  - `items[].carrier`：内容载体（文章/视频/项目/帖子…）
  - `items[].pin`：编辑置顶（`lead|top|null`）
  - `meta.editor_picks`：记录本次挑选的 urls/时间等元信息

## 主列表条数如何决定（以“虹膜/中国国家地理”为例）

1) 每个源先按 `per_feed_limit` 抓候选（auto-mode 默认从 10 放宽到 30；单源可用 `|limit=15` 覆盖）。
2) 候选经 URL/标题指纹去重（缓存 TTL 默认 7 天；同日重跑仍会阻止跨日报重复）。
3) 进入排序/分组：
   - 如果 `group_by=platform` 且 `per_platform_limit>0`：按平台分桶后，每个平台最多保留 `per_platform_limit` 条（可被动态配额/平台覆盖调整），桶内按 `platform_top_by`（recent/quality）选 Top-N。
   - 否则：按全局排序取 `max_items`（默认 50）或全部。
4) 若主列表不足 `min_items_floor`，会从 `backfill_items` 补齐，并受 `floor_per_platform_cap` 限制。

## editor-picks 的边界

- 只在 `$rss-daily-report` 产出的 `items` 中挑选置顶（pin），不会删除/重排主列表（除非未来显式扩展为“精编列表”）。
- 不做“针对特定来源的黑/白名单偏见”，仅基于内容特征（技术/财经优先、信息密度、时效性、营销降权、合集摘要提炼）进行挑选。

## 端到端流程图（Mermaid）

```mermaid
flowchart TD
  A[Start: run rss-daily-report] --> B[Read sources + config]
  B --> C[Fetch feeds (per_feed_limit)]
  C --> D[Parse entries]
  D --> E[Normalize URL/title]
  E --> F[De-dup (cache TTL + in-run)]
  F --> G[Classify topic + carrier]
  G --> H[Score + sort]
  H --> I{group_by=platform & per_platform_limit>0?}
  I -- Yes --> J[Bucket by platform\\nwithin-bucket sort\\napply quota (override/dynamic/default)]
  I -- No --> K[Take by max_items or all]
  J --> L[Backfill + floor (optional)]
  K --> L
  L --> M[Write Markdown + JSON + cache]
  M --> N[Run rss-editor-picks]
  N --> O[Pick lead(1) + top(5)\\nedit title_zh/summary\\nwrite pin]
  O --> P[Upsert picks block in Markdown]
  P --> Q[Done]
```

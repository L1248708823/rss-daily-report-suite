# Repository Guidelines

## 约定
- 开头回答的前缀加上【曼波】
- 需要不断和我确认方案和颗粒度后才能写代码
- 需要边工作边维护todo文档

## Project Structure & Module Organization

- `.codex/skills/rss-daily-report/`: RSS 日报核心实现（可发布 skill）。
  - `scripts/run.py`: 抓取 → 去重 → 打分 →（可选 AI）→ 产出 Markdown/JSON。
  - `scripts/sync_sources.py`: 从勾选清单同步生成启用源文件。
  - `sources.md`: 默认源列表（不建议直接手改，优先用 `my/` 覆盖）。
- `RSS源.md`: 全量 RSS 目录（表格），用于检索/补充来源。
- `my/`: 个人配置与“唯一入口”。
  - `my/sources.checklist.md`: 勾选/取消勾选的入口（脚本会同步生成启用列表）。
  - `my/sources.md`: 自动生成的启用源（供 `run.py` 读取）。
  - `my/config.json`: 本地默认参数（配额、窗口期、补读等）。
- `NewsReport/`: 生成物（`NewsReport/data/YYYY-MM-DD.json` + Markdown 日报）。
- `web/`: Vue3（Vite）前端 MVP，用于本地阅读 `NewsReport/data`。
- `site/`: 静态旧站（`site/assets/data.js` 由 `build_site.py` 生成）。

## Build, Test, and Development Commands

本仓库以脚本为主（尽量少依赖），前端仅用于本地阅读。

- Sync enabled sources from checklist: `python3 .codex/skills/rss-daily-report/scripts/sync_sources.py`
- Generate today’s report (uses `my/config.json` if present): `python3 .codex/skills/rss-daily-report/scripts/run.py`
- Generate a date: `python3 .codex/skills/rss-daily-report/scripts/run.py YYYY-MM-DD`
- Dry run (no files written): `python3 .codex/skills/rss-daily-report/scripts/run.py --dry-run --no-ai`
- Rebuild legacy site bundle: `python3 .codex/skills/rss-daily-report/scripts/build_site.py`
- Web dev server: `cd web && pnpm run dev`

## Coding Style & Naming Conventions

- Python 3.10+; 4-space indentation; prefer small helpers and explicit control flow (see `scripts/run.py`).
- Type hints are expected for new functions and dataclasses.
- Avoid heavy dependencies (keep the pipeline portable).
- Frontend: Vue3 + TypeScript；样式使用 Tailwind（见 `web/vite.config.ts` 与 `web/tailwind.config.cjs`）。

## Testing Guidelines

No dedicated Python test suite yet. Before opening a PR:

- Syntax check: `python3 -m compileall .`
- Smoke run (low budget): `python3 .codex/skills/rss-daily-report/scripts/run.py --dry-run --per-feed-limit 5 --max-items 10 --no-ai`
- Web checks: `cd web && npm run type-check && npm run lint`

## Commit & Pull Request Guidelines

- Use Conventional Commits when possible (repo history includes `feat:`): `feat: ...`, `fix: ...`, `docs: ...`.
- PRs should include: motivation, impact, exact verification commands, and expected output changes.
- Do not commit secrets. Configure AI via env vars: `OPENAI_API_KEY` and (optional) `OPENAI_MODEL`. Avoid committing large generated artifacts unless the PR is specifically about sample outputs.

# Repository Guidelines

## Project Structure & Module Organization

- `.codex/skills/rss-daily-report/`: publishable skill root.
  - `scripts/run.py`: main pipeline (fetch → de-dup → score → optional AI → Markdown/JSON).
  - `sources.md`: default RSS/Atom source list (one per line).
  - `cache.json`: de-dup/cache state (updated by runs).
  - `references/`: examples and docs for source formats.
- `.claude/agents/`: agent personas/prompts (used by some host environments).
- `RSS源.md`: curated RSS catalog (Markdown table).
- `my/`: personal lists (e.g., `my/RSS.md` is “one key per line” for platform/source selection).
- `NewsReport/`: generated reports and structured data (e.g., `NewsReport/data/*.json`).
- `site/`: static reader UI; `site/assets/data.js` is generated from `NewsReport/data`.

## Build, Test, and Development Commands

This repo runs as scripts (no build step) and intentionally keeps dependencies minimal.

- Install deps: `python3 -m pip install requests`
- Generate today’s report: `python3 .codex/skills/rss-daily-report/scripts/run.py`
- Generate a date: `python3 .codex/skills/rss-daily-report/scripts/run.py YYYY-MM-DD`
- Use the repo catalog + selection keys:
  - `python3 .codex/skills/rss-daily-report/scripts/run.py --sources RSS源.md --select-keys-file my/RSS.md --group-by platform`
- Dry run (no files written): `python3 .codex/skills/rss-daily-report/scripts/run.py --dry-run`
- Disable AI even if configured: `python3 .codex/skills/rss-daily-report/scripts/run.py --no-ai`
- Rebuild site data only: `python3 .codex/skills/rss-daily-report/scripts/build_site.py`
- View locally: open `site/index.html` directly (no server required).

## Coding Style & Naming Conventions

- Python 3.10+; 4-space indentation.
- Match existing style in `scripts/run.py`: type hints, `dataclass` models, small explicit helpers, readable control flow.
- Prefer descriptive names and avoid clever one-liners; keep the skill portable by avoiding heavy new dependencies.

## Testing Guidelines

There is no dedicated test framework yet. Before opening a PR:

- Syntax check: `python3 -m compileall .`
- Smoke run on a small budget: `python3 .codex/skills/rss-daily-report/scripts/run.py --dry-run --per-feed-limit 5 --max-items 10`

## Commit & Pull Request Guidelines

- Use Conventional Commits when possible (repo history includes `feat:`): `feat: ...`, `fix: ...`, `docs: ...`.
- PRs should include: motivation, impact, exact verification commands, and expected output changes.
- Do not commit secrets. Configure AI via env vars: `OPENAI_API_KEY` and (optional) `OPENAI_MODEL`. Avoid committing large generated artifacts unless the PR is specifically about sample outputs.

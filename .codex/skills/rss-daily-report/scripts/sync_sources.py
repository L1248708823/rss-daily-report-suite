#!/usr/bin/env python3
"""
sync_sources
============

将 `my/sources.checklist.md` 中勾选的条目同步生成 `my/sources.md`。

Why:
- 让“选源”只有一个入口（checklist），避免 key 文件 + 多份 sources 文件并存导致混乱。
- 对知乎/V2EX/雪球等多端点平台：保留多个端点，但统一归到同一 platform 组，抓完再去重。
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Optional, Tuple


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://[^\s\]\)]+", text or "")
    return m.group(0).strip() if m else None


def infer_platform(name: str, url: str) -> str:
    n = normalize_ws(name)
    # strip short notes like "（不稳定）" / "(unstable)" to keep platform keys stable
    n = re.sub(r"（[^）]{1,32}）", "", n)
    n = re.sub(r"\([^)]{1,32}\)", "", n)
    n = normalize_ws(n).strip("：:|｜-—– ")
    u = (url or "").lower()

    # High-priority explicit families
    if n.startswith("V2EX"):
        return "V2EX"
    if n.startswith("知乎"):
        return "知乎"
    if n.startswith("雪球"):
        return "雪球"
    if "hellogithub" in n.lower():
        return "HelloGitHub 月刊"

    # Blog-like canonical keys
    if "coolshell" in n.lower() or "酷 壳" in n:
        return "CoolShell"
    if "codingnow" in u or n.startswith("云风"):
        return "云风"
    if "diygod" in n.lower():
        return "DIYGod"

    # Split by common separators (take the left as group)
    for sep in [" - ", " — ", " – ", "｜", "|"]:
        if sep in n:
            left = normalize_ws(n.split(sep, 1)[0])
            if left:
                return left

    return n or (re.sub(r"^https?://", "", url).split("/")[0] if url else "未知来源")


def parse_checklist(path: str) -> List[Tuple[str, str, str]]:
    """
    Returns list of (name, platform, url) for checked items.
    """

    lines = open(path, "r", encoding="utf-8").read().splitlines()
    out: List[Tuple[str, str, str]] = []
    for raw in lines:
        m = re.match(r"^\s*-\s*\[([xX ])\]\s*(.+?)\s*$", raw)
        if not m:
            continue
        checked = m.group(1).lower() == "x"
        if not checked:
            continue
        rest = m.group(2)
        url = extract_url(rest)
        if not url:
            continue

        # Name: try split by full-width '｜' first, then fall back to text before URL.
        name = rest
        if "｜" in rest:
            name = rest.split("｜", 1)[0]
        else:
            idx = rest.find(url)
            if idx > 0:
                name = rest[:idx]
        name = normalize_ws(name).strip("：:|｜-—– ")
        if not name:
            name = re.sub(r"^https?://", "", url).split("/")[0]

        platform = infer_platform(name, url)
        out.append((name, platform, url))
    return out


def write_sources(path: str, entries: List[Tuple[str, str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"

    seen_urls: set[str] = set()
    lines: List[str] = []
    lines.append("# AUTO-GENERATED. DO NOT EDIT.\n")
    lines.append("# Source: my/sources.checklist.md\n")
    lines.append("# Format: Name|platform=Platform<TAB>URL\n")
    lines.append("\n")

    for name, platform, url in entries:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        lines.append(f"{name}|platform={platform}\t{url}\n")

    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.replace(tmp, path)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync my/sources.md from my/sources.checklist.md.")
    parser.add_argument("--checklist", default=os.path.join(REPO_ROOT, "my", "sources.checklist.md"))
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "my", "sources.md"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    checklist = os.path.abspath(args.checklist)
    out_path = os.path.abspath(args.out)
    if not os.path.exists(checklist):
        raise SystemExit(f"checklist not found: {checklist}")

    entries = parse_checklist(checklist)
    if args.dry_run:
        for name, platform, url in entries:
            print(f"{name} | platform={platform} | {url}")
        return 0

    write_sources(out_path, entries)
    print(f"Wrote: {out_path} ({len(entries)} checked items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

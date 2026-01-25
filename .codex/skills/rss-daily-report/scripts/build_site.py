#!/usr/bin/env python3
"""
build_site
==========

将本地 NewsReport/data 下的 JSON 汇总成 site/assets/data.js，供静态站点直接打开阅读。
不依赖三方库（stdlib only）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from typing import Any, Dict, List, Tuple


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
    os.replace(tmp, path)


def load_all_days(data_dir: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    index_path = os.path.join(data_dir, "index.json")
    days: List[Dict[str, Any]] = []
    if os.path.exists(index_path):
        try:
            days = list((read_json(index_path).get("days") or []))
        except Exception:
            days = []

    # 兜底：没有 index.json 的情况下按文件名扫
    if not days:
        for fn in os.listdir(data_dir):
            if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", fn):
                days.append({"date": fn[:-5]})
        days.sort(key=lambda x: x["date"], reverse=True)

    items: List[Dict[str, Any]] = []
    for d in days:
        date_str = str(d.get("date") or "").strip()
        if not date_str:
            continue
        p = os.path.join(data_dir, f"{date_str}.json")
        if not os.path.exists(p):
            continue
        try:
            obj = read_json(p)
            day_items = obj.get("items") or []
            if isinstance(day_items, list):
                items.extend([x for x in day_items if isinstance(x, dict)])
        except Exception:
            continue

    return days, items


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build local reading site data.js from NewsReport/data JSON.")
    parser.add_argument("--data-dir", default=os.path.join(REPO_ROOT, "NewsReport", "data"))
    parser.add_argument("--site-dir", default=os.path.join(REPO_ROOT, "site"))
    args = parser.parse_args(argv)

    data_dir = os.path.abspath(args.data_dir)
    site_dir = os.path.abspath(args.site_dir)
    out_js = os.path.join(site_dir, "assets", "data.js")

    if not os.path.isdir(data_dir):
        raise SystemExit(f"data-dir not found: {data_dir}")

    days, items = load_all_days(data_dir)
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "days": days,
        "items": items,
    }

    js = "// Generated from NewsReport/data (local).\n"
    js += "window.__NEWS_DATA__ = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    write_text(out_js, js)
    print(f"Wrote: {out_js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


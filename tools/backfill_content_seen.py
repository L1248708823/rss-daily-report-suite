#!/usr/bin/env python3
# Backfill permanent content keys from existing NewsReport/data/*.json into cache.json

import glob
import hashlib
import json
import os
import re
import email.utils
from datetime import datetime


REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_DIR, "NewsReport", "data")
CACHE_PATH = os.path.join(REPO_DIR, ".codex", "skills", "rss-daily-report", "cache.json")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

    parsed = urlsplit(url)
    if not parsed.query:
        return url
    q = parse_qsl(parsed.query, keep_blank_values=True)
    q = [(k, v) for (k, v) in q if not k.lower().startswith("utm_")]
    new_query = urlencode(q)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def title_exact_fingerprint(title: str) -> str:
    t = normalize_ws(title or "").lower()
    t = t[:200]
    return hashlib.sha1(t.encode("utf-8", errors="ignore")).hexdigest()


def parse_published_date(s: str) -> str | None:
    s = normalize_ws(s or "")
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d is not None:
            return d.date().isoformat()
    except Exception:
        pass
    try:
        d2 = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d2.date().isoformat()
    except Exception:
        return None


def ensure_cache_shape(cache: dict) -> dict:
    cache.setdefault("schema_version", "1.0")
    cache.setdefault("description", "rss-daily-report cache")
    cache.setdefault("last_run", {})
    cache.setdefault("source_stats", {"_comment": "per-feed stats keyed by feed URL"})
    cache.setdefault(
        "content_seen",
        {"_comment": "permanent content keys (guid/url/title+date) to prevent cross-day repeats", "entries": {}},
    )
    cache.setdefault("article_history", {"_comment": "daily published items"})
    cache.setdefault("source_health", {"_comment": "per-feed health state keyed by feed URL", "entries": {}})
    return cache


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def main() -> None:
    # Start fresh to avoid carrying legacy cache fields.
    cache = ensure_cache_shape({})
    content_entries = cache["content_seen"].setdefault("entries", {})

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    files = [p for p in files if not p.endswith("index.json")]

    added = 0
    for path in files:
        data = load_json(path)
        date_str = data.get("date")
        if not date_str:
            # fallback: infer from filename
            date_str = os.path.basename(path).replace(".json", "")
        items = data.get("items") or []
        for it in items:
            title = it.get("title") or ""
            url = safe_url(it.get("url") or "")
            published = it.get("published") or ""
            pub_date = parse_published_date(published)
            keys = []
            if url:
                keys.append(f"url:{url}")
            if pub_date:
                keys.append(f"title_date:{title_exact_fingerprint(title)}|{pub_date}")
            for k in keys:
                # keep earliest date_added
                if k in content_entries:
                    existing = content_entries.get(k) or {}
                    existing_date = existing.get("date_added")
                    if existing_date and date_str and existing_date <= date_str:
                        continue
                content_entries[k] = {
                    "date_added": date_str,
                    "title": title,
                    "url": url,
                    "source": it.get("source") or it.get("platform"),
                }
                added += 1

    write_json(CACHE_PATH, cache)
    print(f"backfill complete: {added} content keys added")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
rss-daily-report
================

Publishable Codex Skill runner: RSS/Atom -> de-dup -> classify -> (optional AI) -> Markdown report.

Key properties for sharing with others:
  - Self-contained: only relies on this skill directory + a user-provided sources list file.
  - Minimal deps: stdlib + requests.
  - Clear, learnable code: explicit data models and step-by-step pipeline.

Typical usage:
  python3 .codex/skills/rss-daily-report/scripts/run.py --sources sources.md
  python3 .codex/skills/rss-daily-report/scripts/run.py 2026-01-22 --sources sources.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import json
import os
import random
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# -----------------------------
# Paths (relative to this skill)
# -----------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))

DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "NewsReport")
DEFAULT_CACHE_PATH = os.path.join(SKILL_DIR, "cache.json")
DEFAULT_REPO_CATALOG_PATH = os.path.join(REPO_ROOT, "RSS源.md")
DEFAULT_REPO_KEYS_PATH = os.path.join(REPO_ROOT, "my", "RSS.md")
DEFAULT_REPO_CONFIG_PATH = os.path.join(REPO_ROOT, "my", "config.json")
DEFAULT_REPO_SITE_DIR = os.path.join(REPO_ROOT, "site")


# -----------------------------
# Networking (short timeouts)
# -----------------------------

# connect timeout, read timeout
DEFAULT_REQUEST_TIMEOUT: Tuple[float, float] = (5.0, 12.0)


def force_requests_ipv4() -> None:
    """
    Some environments have no IPv6 route, but DNS still returns AAAA first,
    leading to "Network is unreachable" on a subset of sites.
    Best-effort: tell urllib3 to prefer IPv4.
    """

    try:
        import urllib3.util.connection as urllib3_cn  # type: ignore
    except Exception:
        try:
            import requests.packages.urllib3.util.connection as urllib3_cn  # type: ignore
        except Exception:
            return
    try:
        urllib3_cn.allowed_gai_family = lambda: socket.AF_INET  # type: ignore[attr-defined]
    except Exception:
        return


def http_get_text(
    url: str,
    *,
    timeout: Tuple[float, float] = DEFAULT_REQUEST_TIMEOUT,
    retries: int = 0,
    retry_sleep_ms: int = 0,
    proxies: Optional[Dict[str, str]] = None,
) -> str:
    """
    Fetch URL as text.
    - short timeouts so one slow feed won't block the whole report
    - do NOT always raise on non-2xx because some endpoints return bodies with 3xx/4xx
      (we'll attempt to parse; if it fails, it's treated as a failed source).
    """

    last_err: Optional[BaseException] = None
    for attempt in range(max(0, int(retries)) + 1):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                allow_redirects=True,
                proxies=proxies,
            )
            return r.text or ""
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt >= max(0, int(retries)):
                raise
            if int(retry_sleep_ms) > 0:
                time.sleep(max(0.0, float(retry_sleep_ms)) / 1000.0)
    if last_err:
        raise last_err
    return ""


def http_get_bytes(
    url: str,
    *,
    timeout: Tuple[float, float] = DEFAULT_REQUEST_TIMEOUT,
    retries: int = 0,
    retry_sleep_ms: int = 0,
    proxies: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    Fetch URL as bytes.
    Using bytes for XML allows ElementTree to respect the XML declaration encoding,
    avoiding mojibake when servers omit/lie about HTTP charset headers.
    """

    last_err: Optional[BaseException] = None
    for attempt in range(max(0, int(retries)) + 1):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                allow_redirects=True,
                proxies=proxies,
            )
            return r.content or b""
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt >= max(0, int(retries)):
                raise
            if int(retry_sleep_ms) > 0:
                time.sleep(max(0.0, float(retry_sleep_ms)) / 1000.0)
    if last_err:
        raise last_err
    return b""

def parse_github_trending_top10(html: str) -> List[Dict[str, str]]:
    """
    Best-effort parser for https://github.com/trending HTML.
    Returns at most 10 repos with basic metadata.
    """

    if not html:
        return []

    # GitHub Trending uses <article class="Box-row"> per repo (as of 2026-01).
    articles = re.findall(r"<article\b[^>]*\bBox-row\b[^>]*>.*?</article>", html, flags=re.S | re.I)
    out: List[Dict[str, str]] = []
    for a in articles:
        if len(out) >= 10:
            break

        # Repo slug like "owner/repo"
        slug = ""
        m_slug = re.search(r'href="\s*/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s*"', a)
        if m_slug:
            slug = m_slug.group(1).strip()
        if not slug:
            continue

        desc = ""
        m_desc = re.search(r"<p\b[^>]*>.*?</p>", a, flags=re.S | re.I)
        if m_desc:
            desc = strip_html(m_desc.group(0))
        desc = normalize_ws(desc)

        lang = ""
        m_lang = re.search(r'itemprop="programmingLanguage"[^>]*>\s*([^<]+)\s*<', a, flags=re.S | re.I)
        if m_lang:
            lang = normalize_ws(m_lang.group(1))

        stars = ""
        m_stars = re.search(r'href="\s*/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/stargazers"[^>]*>\s*([0-9,]+)\s*<', a)
        if m_stars:
            stars = normalize_ws(m_stars.group(1))

        stars_today = ""
        m_today = re.search(r"([0-9,]+)\s+stars\s+today", a, flags=re.S | re.I)
        if m_today:
            stars_today = normalize_ws(m_today.group(1))

        parts: List[str] = []
        if stars:
            parts.append(f"⭐ {stars}")
        if stars_today:
            parts.append(f"今日 +{stars_today}")
        if lang:
            parts.append(lang)
        if desc:
            parts.append(desc)

        out.append(
            {
                "slug": slug,
                "url": f"https://github.com/{slug}",
                "description": " • ".join(parts) if parts else slug,
            }
        )
    return out


def fetch_github_trending_source(
    source: FeedSource,
    *,
    date_str: str,
    retries: int = 0,
    retry_sleep_ms: int = 0,
    proxies: Optional[Dict[str, str]] = None,
) -> List[FeedEntry]:
    html = http_get_text(
        source.url,
        timeout=(5.0, 18.0),
        retries=retries,
        retry_sleep_ms=retry_sleep_ms,
        proxies=proxies,
    )
    repos = parse_github_trending_top10(html)
    out: List[FeedEntry] = []
    for r in repos:
        out.append(
            FeedEntry(
                source_name=source.name,
                source_url=source.url,
                platform="GitHub",
                title=r["slug"],
                url=safe_url(r["url"]),
                description=normalize_ws(r.get("description") or ""),
                published=date_str,
                enclosure_type=None,
            )
        )
    return out


# -----------------------------
# Data models
# -----------------------------


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    # Optional user-defined "platform heat" weight.
    # Can be set in sources.md via: Name|80<TAB>URL
    weight: float = 0.0
    # Optional per-feed fetch cap override (takes precedence over --per-feed-limit).
    # Can be set in sources.md via: Name|limit=15<TAB>URL (or: Name|80|limit=15<TAB>URL)
    per_feed_limit: Optional[int] = None
    # Optional fallback endpoints (tried in order after url).
    # Can be set in sources.md via: Name|fallback=https://...|fallback=https://...<TAB>URL
    fallback_urls: Tuple[str, ...] = ()


@dataclass
class FeedEntry:
    source_name: str
    source_url: str
    # Group label for "platform" mode.
    # By default equals source_name; when using --select-keys-file, it can become the matched key.
    platform: str
    title: str
    url: str
    description: str
    published: Optional[str] = None
    enclosure_type: Optional[str] = None


@dataclass
class EnrichedEntry:
    entry: FeedEntry
    category: str
    carrier: str  # article / video / podcast / project / post / other
    quality_score: float
    keywords: List[str]
    summary: str
    key_points: List[str]
    title_zh: Optional[str] = None


# -----------------------------
# Small helpers
# -----------------------------


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_mostly_english(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # If it contains CJK, treat as not mostly English.
    if re.search(r"[\u4e00-\u9fff]", t):
        return False
    letters = sum(1 for ch in t if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    # Ignore short tokens like "AI", "GPU" etc.
    if letters < 8:
        return False
    non_space = sum(1 for ch in t if not ch.isspace())
    return (letters / max(1, non_space)) >= 0.45


def split_sentences(text: str) -> List[str]:
    """
    Best-effort sentence splitter for both Chinese and English.
    """

    t = normalize_ws(text)
    if not t:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+", t)
    out: List[str] = []
    for p in parts:
        s = normalize_ws(p).strip()
        if s:
            out.append(s)
    return out


def clean_fallback_point(text: str) -> str:
    """
    Remove common boilerplate/noise from feed descriptions.
    This is a best-effort heuristic used only when AI is disabled/unavailable.
    """

    t = normalize_ws(text)
    if not t:
        return ""

    # Common CTA / boilerplate fragments.
    for frag in [
        "查看知乎原文",
        "查看原文",
        "查看全文",
        "阅读原文",
        "阅读全文",
        "点击查看",
        "点击阅读",
    ]:
        t = t.replace(frag, " ")
    t = normalize_ws(t)

    # Remove stock tickers and dense wrappers like $XYZ(SH000001)$.
    t = re.sub(r"\$[^$]{1,40}\$", " ", t)
    t = normalize_ws(t)

    # Remove leading "首发：" / "作者：" labels.
    t = re.sub(r"^(首发|作者|来源)\s*[:：]\s*", "", t, flags=re.I)
    t = normalize_ws(t)

    # Remove leading author signature like "张三， xxx" (keep the remaining clause if any).
    t = re.sub(r"^[^，,]{1,18}[，,]\s*", "", t)
    t = normalize_ws(t)

    return t


def title_bigrams(title: str) -> List[str]:
    """
    Extract Chinese bigrams from a title for weak relevance scoring in fallback mode.
    """

    t = normalize_ws(title)
    chunks = re.findall(r"[\u4e00-\u9fff]+", t)
    if not chunks:
        return []
    stop = {
        "什么",
        "为什么",
        "怎么",
        "如何",
        "是否",
        "可以",
        "有的",
        "一个",
        "哪些",
        "不会",
        "会不",
        "到底",
        "真的",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "中国",
    }
    out: List[str] = []
    seen: set[str] = set()
    for c in chunks:
        if len(c) < 2:
            continue
        for i in range(len(c) - 1):
            bg = c[i : i + 2]
            if bg in stop:
                continue
            if bg in seen:
                continue
            seen.add(bg)
            out.append(bg)
    return out[:20]

def strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    return normalize_ws(text)


def sanitize_xml_bytes(xml_bytes: bytes) -> bytes:
    """
    Remove control characters that are illegal in XML 1.0.
    Helps with a subset of feeds that embed stray bytes and break strict parsers.
    """

    if not xml_bytes:
        return xml_bytes
    bad = set(range(0x00, 0x20)) - {0x09, 0x0A, 0x0D}
    return bytes(b for b in xml_bytes if b not in bad)


def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return url
    q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    q = [(k, v) for (k, v) in q if not k.lower().startswith("utm_")]
    new_query = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def title_fingerprint(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)
    t = t[:120]
    return hashlib.sha1(t.encode("utf-8", errors="ignore")).hexdigest()


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def write_report_data_json(
    *,
    data_dir: str,
    date_str: str,
    items: List[EnrichedEntry],
    meta: Dict[str, Any],
) -> Tuple[str, str]:
    os.makedirs(data_dir, exist_ok=True)
    day_path = os.path.join(data_dir, f"{date_str}.json")
    payload = {
        "date": date_str,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "meta": meta,
        "items": [
            {
                "date": date_str,
                "platform": it.entry.platform or it.entry.source_name,
                "source": it.entry.source_name,
                "source_url": it.entry.source_url,
                "title": it.entry.title,
                "title_zh": it.title_zh,
                "url": it.entry.url,
                "published": it.entry.published,
                "category": it.category,
                "carrier": it.carrier,
                "quality_score": round(float(it.quality_score), 2),
                "keywords": list(it.keywords or []),
                "summary": it.summary,
                "key_points": list(it.key_points or []),
            }
            for it in items
        ],
    }
    write_json(day_path, payload)

    days: List[Dict[str, Any]] = []
    for fn in sorted(os.listdir(data_dir)):
        if fn == "index.json":
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}\.json$", fn):
            continue
        p = os.path.join(data_dir, fn)
        try:
            obj = read_json(p)
            d = str(obj.get("date") or fn[:-5])
            n = len(obj.get("items") or [])
            days.append({"date": d, "count": n})
        except Exception:
            continue
    index_path = os.path.join(data_dir, "index.json")
    write_json(
        index_path,
        {
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "days": sorted(days, key=lambda x: x["date"], reverse=True),
        },
    )
    return day_path, index_path


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
    os.replace(tmp, path)


def write_site_data_js(*, site_dir: str, data_dir: str) -> str:
    """
    Generate site/assets/data.js from NewsReport/data JSONs.
    This keeps the website fully static (openable via file://).
    """

    site_dir = os.path.abspath(site_dir)
    data_dir = os.path.abspath(data_dir)
    out_js = os.path.join(site_dir, "assets", "data.js")

    days: List[Dict[str, Any]] = []
    index_path = os.path.join(data_dir, "index.json")
    if os.path.exists(index_path):
        try:
            days = list((read_json(index_path).get("days") or []))
        except Exception:
            days = []

    if not days and os.path.isdir(data_dir):
        for fn in os.listdir(data_dir):
            if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", fn):
                days.append({"date": fn[:-5]})
        days.sort(key=lambda x: x.get("date", ""), reverse=True)

    items: List[Dict[str, Any]] = []
    for d in days:
        date_str = normalize_ws(str(d.get("date") or ""))
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

    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "days": days,
        "items": items,
    }
    js = "// Generated from NewsReport/data (local).\n"
    js += "window.__NEWS_DATA__ = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    write_text(out_js, js)
    return out_js


def ensure_cache_shape(cache: Dict[str, Any]) -> Dict[str, Any]:
    cache.setdefault("schema_version", "1.0")
    cache.setdefault("description", "rss-daily-report cache")
    cache.setdefault("last_run", {})
    cache.setdefault("source_stats", {"_comment": "per-feed stats keyed by feed URL"})
    cache.setdefault("url_cache", {"_ttl_hours": 168, "entries": {}})
    cache.setdefault("title_hashes", {"_ttl_hours": 168, "entries": {}})
    cache.setdefault("article_history", {"_comment": "daily published items"})
    return cache


def prune_ttl(entries: Dict[str, Any], ttl_hours: int, today: dt.date) -> Dict[str, Any]:
    keep: Dict[str, Any] = {}
    ttl_days = max(1, int(ttl_hours // 24))
    for k, v in (entries or {}).items():
        try:
            added = dt.date.fromisoformat(v.get("date_added"))
        except Exception:
            continue
        if (today - added).days <= ttl_days:
            keep[k] = v
    return keep


def load_cache(path: str) -> Dict[str, Any]:
    cache = read_json(path) if os.path.exists(path) else {}
    cache = ensure_cache_shape(cache)
    today = dt.date.today()
    cache["url_cache"]["entries"] = prune_ttl(
        cache["url_cache"].get("entries", {}),
        int(cache["url_cache"].get("_ttl_hours", 168)),
        today,
    )
    cache["title_hashes"]["entries"] = prune_ttl(
        cache["title_hashes"].get("entries", {}),
        int(cache["title_hashes"].get("_ttl_hours", 168)),
        today,
    )
    return cache


# -----------------------------
# sources.md parsing
# -----------------------------


def parse_sources_file(path: str) -> List[FeedSource]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    def extract_urls(text: str) -> List[str]:
        # Stop at whitespace / closing bracket / closing paren to handle Markdown links:
        # [text](https://example.com/feed) or [https://example.com/feed](https://example.com/feed)
        return re.findall(r"https?://[^\s\]\)]+", text or "")

    # If this file looks like a Markdown table catalog (e.g. RSS源.md),
    # only parse rows under the "名称|RSS源|..." table to avoid grabbing
    # unrelated guide links above the table.
    looks_like_table_catalog = any(("| 名称" in ln and "RSS" in ln) for ln in raw_lines)
    if looks_like_table_catalog:
        sources: List[FeedSource] = []
        seen: set[str] = set()
        in_table = False
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                continue
            if not in_table:
                if line.startswith("|") and ("名称" in line) and ("RSS" in line):
                    in_table = True
                continue
            # skip separator row like: | --- | --- | --- |
            if re.match(r"^\|\s*-{3,}\s*\|", line):
                continue
            if not line.startswith("|"):
                # end of table
                break

            cells = [normalize_ws(c) for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            name_cell = cells[0]
            rss_cell = cells[1]
            urls = extract_urls(rss_cell)
            if not urls:
                continue
            # Prefer the link target in Markdown, which often appears last.
            url = urls[-1].strip()
            if url in seen:
                continue
            seen.add(url)
            name = name_cell or (urllib.parse.urlsplit(url).netloc or url)
            sources.append(FeedSource(name=name, url=url))
        return sources

    # Default: one URL per line (optionally with "Name<TAB>URL")
    def parse_name_meta(raw_name: str) -> Tuple[str, float, Optional[int], Tuple[str, ...]]:
        """
        Parse optional metadata from the name cell.

        Supported:
          - Name|80                   -> weight=80
          - Name|limit=15             -> per_feed_limit=15
          - Name|80|limit=15          -> both
          - Name|fallback=https://... -> fallback_urls
        """

        raw_name = normalize_ws(raw_name or "")
        if not raw_name:
            return "", 0.0, None, ()

        parts = [normalize_ws(x) for x in raw_name.split("|") if normalize_ws(x)]
        if not parts:
            return "", 0.0, None, ()

        name = parts[0]
        weight = 0.0
        per_feed_limit: Optional[int] = None
        fallback_urls: List[str] = []

        for seg in parts[1:]:
            if re.fullmatch(r"[0-9]+(?:\\.[0-9]+)?", seg):
                try:
                    weight = float(seg)
                except Exception:
                    weight = 0.0
                continue

            m_lim = re.match(r"^(?:limit|per_feed_limit)\\s*=\\s*([0-9]+)$", seg, flags=re.I)
            if m_lim:
                try:
                    per_feed_limit = max(1, int(m_lim.group(1)))
                except Exception:
                    per_feed_limit = None
                continue

            m_fb = re.match(r"^(?:fallback|alt|mirror)\\s*=\\s*(https?://.+)$", seg, flags=re.I)
            if m_fb:
                u = normalize_ws(m_fb.group(1))
                if u.startswith("http"):
                    fallback_urls.append(u)
                continue

        # de-dup while keeping order
        dedup_fb: List[str] = []
        seen_fb: set[str] = set()
        for u in fallback_urls:
            if u in seen_fb:
                continue
            seen_fb.add(u)
            dedup_fb.append(u)

        return name, weight, per_feed_limit, tuple(dedup_fb)

    sources2: List[FeedSource] = []
    seen2: set[str] = set()
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        urls = extract_urls(line)
        if not urls:
            continue
        url = urls[-1].strip()
        # If the line contains multiple URLs, try to avoid obvious "viewer" links.
        if len(urls) > 1:
            for cand in reversed(urls):
                try:
                    dom = (urllib.parse.urlsplit(cand).netloc or "").lower()
                except Exception:
                    continue
                if dom and ("webfollow.cc" not in dom) and ("chromewebstore.google.com" not in dom):
                    url = cand.strip()
                    break
        idx = line.find(url)
        raw_name = normalize_ws(line[:idx].strip()) if idx >= 0 else ""
        name, weight, per_feed_limit, fallback_urls = parse_name_meta(raw_name)
        if not name:
            name = urllib.parse.urlsplit(url).netloc or url
        if url in seen2:
            continue
        seen2.add(url)
        sources2.append(
            FeedSource(name=name, url=url, weight=weight, per_feed_limit=per_feed_limit, fallback_urls=fallback_urls)
        )
    return sources2


def read_keys_file(path: str) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    keys: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Keep spaces inside a key; only split by punctuation commonly used as separators.
            parts = re.split(r"[，,、;；]+", line)
            for p in parts:
                k = normalize_ws(p)
                if k:
                    keys.append(k)
    # de-dup while keeping order
    out: List[str] = []
    seen: set[str] = set()
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def text_contains_key(text: str, key: str) -> bool:
    if not text or not key:
        return False
    # If the key has ASCII letters, do a case-insensitive match.
    if re.search(r"[A-Za-z]", key):
        return key.lower() in text.lower()
    return key in text


def source_matches_any_key(src: FeedSource, keys: List[str]) -> bool:
    if not keys:
        return True
    hay = f"{src.name} {src.url}".lower()
    for k in keys:
        if not k:
            continue
        if re.search(r"[A-Za-z]", k):
            if k.lower() in hay:
                return True
            continue
        if text_contains_key(src.name, k):
            return True
        if (not re.search(r"[A-Za-z]", k)) and text_contains_key(src.url, k):
            return True
    return False


def source_matches_key(src: FeedSource, key: str) -> bool:
    return source_matches_any_key(src, [key])


def choose_platform_key_for_source(src: FeedSource, keys: List[str]) -> Optional[str]:
    """
    When multiple keys match a source, prefer the longest (more specific) key;
    tie-break by the order in keys.
    """

    matches: List[Tuple[int, int, str]] = []
    for i, k in enumerate(keys):
        if source_matches_key(src, k):
            matches.append((len(k), -i, k))
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][2]


def parse_published_dt(entry: FeedEntry) -> Optional[dt.datetime]:
    """
    Best-effort parsing for RSS pubDate / Atom updated.
    Used for "recent" sorting in per-platform top-N mode.
    """

    s = normalize_ws(entry.published or "")
    if not s:
        return None
    try:
        # RSS: RFC 2822 / 822
        d = email.utils.parsedate_to_datetime(s)
        if d is None:
            return None
        # Normalize to UTC-naive for comparable ordering.
        if d.tzinfo is not None:
            d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return d
    except Exception:
        pass
    try:
        # Atom: ISO-8601
        d2 = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d2.tzinfo is not None:
            d2 = d2.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return d2
    except Exception:
        return None


# -----------------------------
# RSS/Atom parsing
# -----------------------------


def parse_feed(xml_bytes: bytes) -> List[Tuple[str, str, str, Optional[str], Optional[str]]]:
    """
    Return list:
      (title, link, description, published, enclosure_type)
    """

    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        # Best-effort repair for malformed feeds (most commonly illegal control chars).
        root = ET.fromstring(sanitize_xml_bytes(xml_bytes))
    tag = root.tag.lower()

    if tag.endswith("rss"):
        chan = root.find("channel")
        if chan is None:
            return []
        out = []
        for item in chan.findall("item"):
            title = normalize_ws(item.findtext("title") or "")
            link = normalize_ws(item.findtext("link") or "")
            desc = item.findtext("description") or ""
            if not desc:
                for child in item:
                    if child.tag.lower().endswith("encoded") and (child.text or "").strip():
                        desc = child.text
                        break
            pub = normalize_ws(item.findtext("pubDate") or "") or None

            enclosure = item.find("enclosure")
            enclosure_type = enclosure.attrib.get("type") if enclosure is not None else None

            if title and link:
                out.append((title, link, strip_html(desc), pub, enclosure_type))
        return out

    if tag.endswith("feed"):
        ns = {"a": re.match(r"\{(.+)\}", root.tag).group(1)} if root.tag.startswith("{") else {}
        entries = root.findall("a:entry", ns) if ns else root.findall("entry")
        out = []
        for e in entries:
            title = normalize_ws(
                e.findtext("a:title", default="", namespaces=ns) if ns else e.findtext("title", default="")
            )
            link = ""
            link_el = e.find("a:link", ns) if ns else e.find("link")
            if link_el is not None:
                link = normalize_ws(link_el.attrib.get("href") or "")

            summary = e.findtext("a:summary", default="", namespaces=ns) if ns else e.findtext("summary", default="")
            content = e.findtext("a:content", default="", namespaces=ns) if ns else e.findtext("content", default="")
            desc = strip_html(summary or content or "")

            updated = normalize_ws(
                e.findtext("a:updated", default="", namespaces=ns) if ns else e.findtext("updated", default="")
            ) or None

            if title and link:
                out.append((title, link, desc, updated, None))
        return out

    return []


def fetch_and_parse_source(
    source: FeedSource,
    *,
    per_feed_limit: int,
    retries: int = 0,
    retry_sleep_ms: int = 0,
    proxies: Optional[Dict[str, str]] = None,
) -> List[FeedEntry]:
    timeout = DEFAULT_REQUEST_TIMEOUT
    dom = (urllib.parse.urlsplit(source.url).netloc or "").lower()
    if "v2ex.com" in dom:
        timeout = (10.0, 18.0)
    elif "rsshub.app" in dom:
        timeout = (8.0, 18.0)

    candidates: List[str] = [source.url]
    for u in source.fallback_urls:
        if u and u not in candidates:
            candidates.append(u)

    last_err: Optional[BaseException] = None
    last_url: Optional[str] = None
    items: List[Tuple[str, str, str, Optional[str], Optional[str]]] = []
    for u in candidates:
        last_url = u
        try:
            xml_bytes = http_get_bytes(
                u,
                timeout=timeout,
                retries=retries,
                retry_sleep_ms=retry_sleep_ms,
                proxies=proxies,
            )
            items = parse_feed(xml_bytes)
            if items:
                break
            # If the endpoint returns non-feed HTML (e.g., WAF block page), treat as failure and try fallback.
            if b"<html" in (xml_bytes or b"").lower():
                raise ValueError("non-feed HTML response")
        except Exception as e:
            last_err = e
            items = []
            continue
    if not items:
        if last_err:
            raise RuntimeError(f"failed after {len(candidates)} endpoint(s), last={last_url}: {last_err}")
        raise RuntimeError(f"failed after {len(candidates)} endpoint(s)")

    out: List[FeedEntry] = []
    for title, link, desc, pub, enclosure_type in items[:per_feed_limit]:
        out.append(
            FeedEntry(
                source_name=source.name,
                source_url=source.url,
                platform=source.name,
                title=title,
                url=safe_url(link),
                description=normalize_ws(desc),
                published=pub,
                enclosure_type=enclosure_type,
            )
        )
    return out


# -----------------------------
# Classification (topic + carrier)
# -----------------------------


CATEGORY_ORDER = ["技术", "商业/产品", "生活", "时事", "财经", "娱乐", "其他"]
GROUP_BY_CHOICES = ["platform", "topic", "none"]


def infer_platform_base_weight(*, source_name: str, source_url: str) -> float:
    """
    RSS/Atom 本身通常没有“阅读量/点赞/热搜指数”等真实热度指标。
    这里用一个可解释的“平台基线权重”做兜底：按平台类型给一个默认排序倾向。
    用户可在 sources.md 里用 Name|80 覆盖/微调。
    """

    name = (source_name or "").lower()
    domain = (urllib.parse.urlsplit(source_url).netloc or "").lower()

    # Hotlists / mainstream platforms
    if "weibo" in domain or "微博" in name:
        return 100.0
    if "zhihu" in domain or "知乎" in name:
        return 90.0

    # Tech/product/media
    if "36kr" in domain or "36氪" in name:
        return 80.0
    if "github.com" in domain or "github" in name:
        return 60.0
    if "sspai" in domain or "少数派" in name:
        return 70.0
    if "xueqiu" in domain or "雪球" in name:
        return 65.0
    if "ruanyifeng" in domain or "阮一峰" in name:
        return 55.0
    if "v2ex" in domain or "v2ex" in name:
        return 55.0

    # News / others
    if "zaobao" in domain or "早报" in name:
        return 50.0
    if "telegram" in name:
        return 35.0

    return 0.0


def compute_platform_heat(
    *,
    cache: Dict[str, Any],
    sources: List[FeedSource],
    today: dt.date,
    window_days: int,
    group_for_source: Optional[Any] = None,
) -> Dict[str, float]:
    """
    平台热度 = 基线权重 + 最近 window_days 天被收录次数（从 cache.article_history 统计）。
    说明：这是“可计算”的近似热度，并不等价于真实阅读量/热搜指数。
    """

    window_days = max(1, int(window_days))

    # Base weights (infer + per-source override), aggregated by group.
    base: Dict[str, float] = {}
    for s in sources:
        group = group_for_source(s) if callable(group_for_source) else s.name
        w = max(0.0, float(s.weight or 0.0))
        w = max(w, infer_platform_base_weight(source_name=s.name, source_url=s.url))
        base[str(group)] = max(base.get(str(group), 0.0), w)

    # Recent history counts.
    counts: Dict[str, int] = {}
    hist = cache.get("article_history", {})
    if isinstance(hist, dict):
        for d_str, day_items in hist.items():
            if not isinstance(d_str, str) or d_str.startswith("_"):
                continue
            try:
                d = dt.date.fromisoformat(d_str)
            except Exception:
                continue
            delta = (today - d).days
            if delta < 0 or delta >= window_days:
                continue
            if not isinstance(day_items, list):
                continue
            for it in day_items:
                if not isinstance(it, dict):
                    continue
                g = it.get("platform") or it.get("source")
                if not g:
                    continue
                counts[str(g)] = counts.get(str(g), 0) + 1

    out: Dict[str, float] = {}
    for k, w in base.items():
        out[k] = float(w) + float(counts.get(k, 0))
    # Also keep counts for any historical sources no longer in sources list.
    for k, c in counts.items():
        out.setdefault(k, float(c))
    return out


def carrier_from_entry(entry: FeedEntry) -> str:
    url = entry.url.lower()
    domain = urllib.parse.urlsplit(entry.url).netloc.lower()

    if entry.enclosure_type:
        t = entry.enclosure_type.lower()
        if t.startswith("audio/"):
            return "播客"
        if t.startswith("video/"):
            return "视频"

    if "github.com" in domain:
        return "项目"
    if "youtube.com" in domain or "bilibili.com" in domain:
        return "视频"
    if "news.ycombinator.com/item" in url or "v2ex.com/t" in url:
        return "帖子"
    return "文章"


def contains_any(text: str, words: Iterable[str]) -> bool:
    t = text.lower()
    for w in words:
        if w and w.lower() in t:
            return True
    return False


def classify_topic(entry: FeedEntry) -> str:
    """
    Rule-based, explainable classification.
    You can fork/extend this for your own taste.
    """

    text = f"{entry.source_name} {entry.title} {entry.description}"
    domain = urllib.parse.urlsplit(entry.url).netloc.lower()
    source = entry.source_name

    # Strong source hints (only when the source is almost single-topic).
    if any(k in source for k in ("阮一峰",)) or domain in {"www.ruanyifeng.com"}:
        return "技术"
    if any(k in source for k in ("V2EX",)) or domain in {"v2ex.com"}:
        return "技术"
    if any(k in source for k in ("36氪", "36kr", "Product")) or domain in {"www.36kr.com", "36kr.com"}:
        return "商业/产品"

    # Keyword rules (weaker than source rules).
    tech_kw = [
        "ai",
        "llm",
        "agent",
        "开源",
        "编程",
        "python",
        "rust",
        "go",
        "kubernetes",
        "数据库",
        "安全",
        "漏洞",
        "前端",
        "后端",
        "算法",
        "架构",
        "云",
        "macos",
        "windows",
        "docker",
        "git",
    ]
    biz_kw = ["融资", "ipo", "估值", "收购", "并购", "市场", "商业", "产品", "运营", "用户", "增长", "创业", "电商"]
    finance_kw = ["股票", "基金", "美股", "a股", "港股", "投资", "经济", "利率", "通胀", "财报", "央行", "比特币", "黄金"]
    news_kw = ["国际", "外交", "政府", "法院", "选举", "总统", "部长", "警方", "通报", "突发", "战争", "冲突"]
    life_kw = ["健康", "运动", "睡眠", "习惯", "心理", "育儿", "饮食", "旅行", "自驾", "租车", "穿衣", "穿搭", "指南", "复盘", "避坑"]
    ent_kw = ["电影", "电视剧", "综艺", "游戏", "音乐", "动画", "4k", "蓝光"]

    if contains_any(text, finance_kw):
        return "财经"
    if contains_any(text, biz_kw):
        return "商业/产品"
    if contains_any(text, news_kw):
        return "时事"
    if contains_any(text, ent_kw):
        return "娱乐"
    if contains_any(text, life_kw):
        return "生活"
    if contains_any(text, tech_kw):
        return "技术"

    return "其他"


# -----------------------------
# Scoring / de-dup
# -----------------------------


def derive_keywords(entry: FeedEntry, max_n: int = 6) -> List[str]:
    text = f"{entry.title} {entry.description}"
    raw = re.findall(r"[A-Za-z][A-Za-z0-9+_.-]{1,24}", text)
    stop = {"the", "and", "for", "with", "from", "this", "that", "your", "now", "how", "what", "into", "are"}
    freq: Dict[str, int] = {}
    for w in raw:
        lw = w.lower()
        if lw in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return [w for (w, _) in ranked[:max_n]]


def score_entry(entry: FeedEntry, category: str, carrier: str) -> float:
    score = 3.0
    text = f"{entry.title} {entry.description}".strip()

    if len(text) < 30:
        score -= 0.6
    if category in {"技术", "财经"}:
        score += 0.3
    if carrier == "项目":
        score += 0.4

    return max(1.0, min(5.0, score))


def dedupe_entries(entries: List[FeedEntry], cache: Dict[str, Any], *, date_str: str) -> List[FeedEntry]:
    url_seen = set((cache.get("url_cache", {}).get("entries") or {}).keys())
    title_seen = set((cache.get("title_hashes", {}).get("entries") or {}).keys())

    allow_url: set[str] = set()
    allow_title: set[str] = set()
    day_hist = cache.get("article_history", {}).get(date_str)
    if isinstance(day_hist, list):
        for x in day_hist:
            if isinstance(x, dict):
                if x.get("url"):
                    allow_url.add(str(x["url"]))
                if x.get("title_hash"):
                    allow_title.add(str(x["title_hash"]))

    out: List[FeedEntry] = []
    local_title_seen: set[str] = set()
    local_url_seen: set[str] = set()
    for e in entries:
        u = safe_url(e.url)
        th = title_fingerprint(e.title)

        if u in local_url_seen or th in local_title_seen:
            continue
        if (u in url_seen) and (u not in allow_url):
            continue
        if (th in title_seen) and (th not in allow_title):
            continue

        local_url_seen.add(u)
        local_title_seen.add(th)
        out.append(FeedEntry(**{**e.__dict__, "url": u}))

    return out


# -----------------------------
# Optional AI enrichment (OpenAI)
# -----------------------------


def openai_chat_json(api_key: str, model: str, messages: List[Dict[str, str]], timeout_s: float = 30.0) -> Dict[str, Any]:
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def maybe_ai_enrich(
    entry: FeedEntry,
    *,
    category: str,
    carrier: str,
    enable_ai: bool,
    model: str,
) -> Optional[Tuple[str, List[str], List[str], float, Optional[str]]]:
    if not enable_ai:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    need_title_zh = is_mostly_english(entry.title)
    system = (
        "你是一个日报编辑。根据输入信息输出严格 JSON（不要 Markdown，不要多余字段）。"
        "要求：摘要 2-4 句中文；要点最多 3 条；关键词 3-6 个；质量评分 1-5（可小数）。"
        "要点必须是对内容的具体提炼（包含具体名词/事实/结论），不要输出模板化建议"
        "（例如：'建议先扫一遍'、'收藏+打标签' 之类）。"
        + ("原标题主要为英文时，额外输出 title_zh（中文标题翻译，尽量简洁）。" if need_title_zh else "")
    )
    user_obj = {
        "source": entry.source_name,
        "title": entry.title,
        "description": entry.description,
        "url": entry.url,
        "category_hint": category,
        "carrier_hint": carrier,
        "published": entry.published,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_obj, ensure_ascii=False)},
        {
            "role": "user",
            "content": (
                "{\"summary\":\"...\",\"key_points\":[\"...\"],\"keywords\":[\"...\"],\"quality_score\":4.2"
                + (",\"title_zh\":\"...\"" if need_title_zh else "")
                + "}"
            ),
        },
    ]

    try:
        resp = openai_chat_json(api_key=api_key, model=model, messages=messages, timeout_s=35.0)
        content = resp["choices"][0]["message"]["content"]
        data = json.loads(content)
        summary = normalize_ws(str(data.get("summary") or ""))
        key_points = [normalize_ws(str(x)) for x in (data.get("key_points") or [])][:3]
        key_points = [x for x in key_points if x]
        keywords = [normalize_ws(str(x)) for x in (data.get("keywords") or [])][:6]
        keywords = [x for x in keywords if x]
        q = float(data.get("quality_score") or 3.0)
        q = max(1.0, min(5.0, q))
        title_zh = normalize_ws(str(data.get("title_zh") or "")) if need_title_zh else ""
        if title_zh and title_zh.lower() == entry.title.lower():
            title_zh = ""
        if not summary:
            return None
        return summary, key_points, keywords, q, (title_zh or None)
    except Exception:
        return None


def fallback_summary(entry: FeedEntry) -> Tuple[str, List[str]]:
    summary = normalize_ws(entry.description or entry.title)
    if len(summary) > 260:
        summary = summary[:260].rstrip() + "…"
    sents = split_sentences(entry.description or "")
    bigrams = title_bigrams(entry.title)
    scored: List[Tuple[int, int, str]] = []
    for raw in sents:
        s = clean_fallback_point(raw).strip().strip("。！？.!?").strip()
        if not s:
            continue
        if len(s) < 12:
            continue
        score = 0
        if bigrams:
            for bg in bigrams:
                if bg and bg in s:
                    score += 1
        scored.append((score, len(s), s))

    # Prefer sentences that overlap with title; fall back to longer (more informative) ones.
    scored.sort(key=lambda x: (-x[0], -x[1]))
    points: List[str] = []
    for score, _, s in scored:
        if score == 0 and points:
            # Once we already have some relevant points, avoid filling the rest with unrelated noise.
            continue
        if len(s) > 80:
            s = s[:80].rstrip() + "…"
        if s not in points:
            points.append(s)
        if len(points) >= 3:
            break

    if not points:
        points = [clean_fallback_point(entry.title)[:80] or normalize_ws(entry.title)[:80]]

    return summary, points[:3]


# -----------------------------
# Rendering
# -----------------------------


def render_entry_md(idx: int, e: EnrichedEntry) -> str:
    domain = urllib.parse.urlsplit(e.entry.url).netloc or e.entry.source_name
    source_label = e.entry.source_name or domain
    stars = "⭐" * int(round(e.quality_score))

    lines: List[str] = []
    if e.title_zh and e.title_zh != e.entry.title:
        lines.append(f"### {idx}. {e.title_zh}\n")
        lines.append(f"- **原标题**：{e.entry.title}")
    else:
        lines.append(f"### {idx}. {e.entry.title}\n")
    lines.append(f"- **摘要**：{e.summary}")
    lines.append(f"- **分类**：`{e.category}`  |  **载体**：`{e.carrier}`")
    if e.key_points:
        lines.append("- **要点**：")
        for i, kp in enumerate(e.key_points[:3], 1):
            lines.append(f"  {i}. {kp}")
    lines.append(f"- **来源**：[{source_label}]({e.entry.url})")
    if e.keywords:
        lines.append("- **关键词**：" + " ".join(f"`{k}`" for k in e.keywords[:8]))
    lines.append(f"- **评分**：{stars} ({int(round(e.quality_score))}/5)\n")
    return "\n".join(lines)


def build_report(
    *,
    date_str: str,
    sources: List[FeedSource],
    items: List[EnrichedEntry],
    duration_seconds: int,
    group_by: str,
    platform_heat: Dict[str, float],
    platform_heat_window_days: int,
    selected_keys: List[str],
    per_platform_limit: int,
    platform_sources: Dict[str, List[FeedSource]],
    success_source_urls: set[str],
    failed_source_urls: set[str],
    skipped_source_urls: set[str],
    errors: List[str],
    foreign_section_title: Optional[str],
    foreign_section_sources: List[FeedSource],
    foreign_section_success_urls: set[str],
    foreign_section_failed_urls: set[str],
    foreign_section_skipped_urls: set[str],
    foreign_section_errors: List[str],
    foreign_section_items: List[EnrichedEntry],
    foreign_section_limit: int,
) -> str:
    if group_by not in GROUP_BY_CHOICES:
        group_by = "platform"

    used_sources = sorted({s.name for s in sources})

    def group_header_line() -> str:
        if group_by == "topic":
            return "> 分组：按类目（topic）  "
        if group_by == "none":
            return "> 分组：不分组（flat，按平台热度排序）  "
        return f"> 分组：按平台热度（窗口 {max(1, int(platform_heat_window_days))} 天）  "

    lines: List[str] = []
    lines.append(f"# RSS Daily Report（{date_str}）\n")
    lines.append(f"> 信息源：{len(sources)} 个 | 收录：{len(items)} 条  ")
    lines.append(group_header_line())
    if selected_keys:
        lines.append(f"> 平台 key：{len(selected_keys)} 个 | 每平台 Top：{max(0, int(per_platform_limit))}  ")
    lines.append(f"> 生成耗时：~{max(1, int(round(duration_seconds / 60)))} 分钟\n")
    lines.append("---\n")

    if selected_keys:
        lines.append("## RSS/Atom 条目字段说明\n")
        lines.append(
            "- 本脚本从 RSS/Atom 解析并使用的字段：`source_name`（源名称）`source_url`（源地址）`title`（标题）`url`（链接）`description`（description/summary/content 清洗）`published`（pubDate/updated）`enclosure_type`（enclosure@type，可用于判断音频/视频）"
        )
        lines.append("- 常见但本脚本当前未解析/未使用的字段：作者（author）、分类/标签（category）、GUID/ID、图片/附件（media/enclosure url）、评论链接等（不同源差异很大）\n")
        lines.append("---\n")

    if selected_keys and group_by == "platform":
        lines.append("## 抓取明细\n")
        for k in selected_keys:
            srcs = platform_sources.get(k, [])
            ok = sum(1 for s in srcs if s.url in success_source_urls)
            bad = sum(1 for s in srcs if s.url in failed_source_urls)
            skipped = sum(1 for s in srcs if s.url in skipped_source_urls)
            lines.append(f"- **{k}**：源 {len(srcs)} 个（成功 {ok} / 失败 {bad} / 未收集 {skipped}）")
            # avoid huge logs in the report; show up to 8 endpoints
            for s in srcs[:8]:
                if s.url in failed_source_urls:
                    status = "失败"
                elif s.url in skipped_source_urls:
                    status = "未收集"
                elif s.url in success_source_urls:
                    status = "成功"
                else:
                    status = "未知"
                lines.append(f"  - {status}：{s.name} — {s.url}")
            if len(srcs) > 8:
                lines.append(f"  - … 另有 {len(srcs) - 8} 个源未展开")
        if errors:
            lines.append("\n## 失败原因（节选）\n")
            for e in errors[:10]:
                lines.append(f"- {normalize_ws(str(e))}")
        lines.append("\n---\n")

    idx = 1
    if group_by == "topic":
        by_cat: Dict[str, List[EnrichedEntry]] = {}
        for it in items:
            by_cat.setdefault(it.category, []).append(it)
        for cat in by_cat:
            by_cat[cat].sort(key=lambda x: (-x.quality_score, x.entry.title.lower()))

        for cat in CATEGORY_ORDER:
            group = by_cat.get(cat, [])
            if not group:
                continue
            lines.append(f"## {cat}\n")
            for it in group:
                lines.append(render_entry_md(idx, it))
                idx += 1
            lines.append("---\n")
    elif group_by == "none":
        # Keep the order provided by main() (typically already sorted).
        for it in items:
            lines.append(render_entry_md(idx, it))
            idx += 1
        lines.append("---\n")
    else:
        by_platform: Dict[str, List[EnrichedEntry]] = {}
        for it in items:
            by_platform.setdefault(it.entry.platform or it.entry.source_name or "未知来源", []).append(it)
        for p in by_platform:
            by_platform[p].sort(key=lambda x: (-x.quality_score, x.entry.title.lower()))

        def p_sort_key(p: str) -> Tuple[float, str]:
            return (-float(platform_heat.get(p, 0.0)), p)

        for platform in sorted(by_platform.keys(), key=p_sort_key):
            group = by_platform.get(platform, [])
            if not group:
                continue
            heat = platform_heat.get(platform, 0.0)
            heat_str = str(int(round(heat))) if heat >= 1 else f"{heat:.1f}".rstrip("0").rstrip(".")
            lines.append(f"## {platform}（热度 {heat_str}）\n")
            for it in group:
                lines.append(render_entry_md(idx, it))
                idx += 1
            lines.append("---\n")

    if foreign_section_title:
        title = foreign_section_title
        limit = max(1, int(foreign_section_limit))
        lines.append(f"## {title}（随机抽取 {len(foreign_section_sources)} 个源，去重后保留 {limit} 条）\n")
        if foreign_section_sources:
            lines.append("- **抽取源**：")
            for s in foreign_section_sources:
                if s.url in foreign_section_failed_urls:
                    status = "失败"
                elif s.url in foreign_section_skipped_urls:
                    status = "未收集"
                elif s.url in foreign_section_success_urls:
                    status = "成功"
                else:
                    status = "未知"
                lines.append(f"  - {status}：{s.name} — {s.url}")
        if foreign_section_errors:
            lines.append("- **失败原因（节选）**：")
            for e in foreign_section_errors[:6]:
                lines.append(f"  - {normalize_ws(str(e))}")
        lines.append("")

        shown = foreign_section_items[:limit]
        if not shown:
            lines.append("- （没有可展示的条目：可能是源失效/超时/都被去重过滤）\n")
        else:
            for it in shown:
                lines.append(render_entry_md(idx, it))
                idx += 1
        lines.append("---\n")

    lines.append("*Generated by rss-daily-report*  ")
    lines.append("*Sources: " + ", ".join(used_sources) + "*\n")
    return "\n".join(lines)


# -----------------------------
# Main
# -----------------------------


def parse_date_arg(date_str: Optional[str]) -> str:
    if not date_str:
        return dt.date.today().isoformat()
    dt.date.fromisoformat(date_str)
    return date_str


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    # Optional JSON config (repo-friendly). CLI flags always override config.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None, help="Optional JSON config file.")
    pre.add_argument("--no-config", action="store_true", help="Disable auto loading my/config.json.")
    pre_args, _ = pre.parse_known_args(argv)

    cfg_path: Optional[str] = None
    if not bool(pre_args.no_config):
        cfg_path = (
            str(pre_args.config)
            if pre_args.config
            else (DEFAULT_REPO_CONFIG_PATH if os.path.exists(DEFAULT_REPO_CONFIG_PATH) else None)
        )

    cfg_defaults: Dict[str, Any] = {}
    if cfg_path:
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict) and isinstance(obj.get("defaults"), dict):
                cfg_defaults = dict(obj.get("defaults") or {})
        except Exception:
            cfg_defaults = {}

    def cfg_get(key: str, fallback: Any) -> Any:
        v = cfg_defaults.get(key, fallback)
        return fallback if v is None else v

    parser = argparse.ArgumentParser(description="Generate a daily report from RSS/Atom feeds.")
    parser.add_argument("date", nargs="?", help="Optional date: YYYY-MM-DD (default: today)")
    parser.add_argument("--config", default=cfg_path, help="Optional JSON config file (default: my/config.json if exists).")
    parser.add_argument("--no-config", action="store_true", help="Disable auto loading my/config.json.")
    parser.add_argument(
        "--sources",
        action="append",
        help="sources list file (repeatable). Supports simple list or a Markdown table catalog.",
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory (default: NewsReport/)")
    parser.add_argument(
        "--max-items",
        type=int,
        default=cfg_defaults.get("max_items", None),
        help="Max published items overall (default: 50; set 0 for unlimited).",
    )
    parser.add_argument(
        "--per-feed-limit",
        type=int,
        default=int(cfg_get("per_feed_limit", 10)),
        help="Max items per feed to consider (default: 10)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=float(cfg_get("min_score", 2.6)),
        help="Minimum score to include (default: 2.6)",
    )
    parser.add_argument(
        "--time-budget",
        type=int,
        default=int(cfg_get("time_budget", 120)),
        help="Max wall time budget in seconds (default: 120)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(cfg_get("retries", 0)),
        help="Retry count for network errors per endpoint (default: 0).",
    )
    parser.add_argument(
        "--retry-sleep-ms",
        type=int,
        default=int(cfg_get("retry_sleep_ms", 0)),
        help="Sleep between retries in milliseconds (default: 0).",
    )
    parser.add_argument(
        "--proxy",
        default=str(cfg_get("proxy", "") or ""),
        help="Optional HTTP proxy URL applied to both http/https (e.g. http://127.0.0.1:7890).",
    )
    parser.add_argument(
        "--prefer-ipv4",
        dest="prefer_ipv4",
        action="store_true",
        default=None,
        help="Prefer IPv4 for requests (helps in IPv6-unreachable environments). Default: enabled in repo auto-mode.",
    )
    parser.add_argument(
        "--no-prefer-ipv4",
        dest="prefer_ipv4",
        action="store_false",
        default=None,
        help="Do not force IPv4 preference.",
    )
    parser.add_argument(
        "--group-by",
        choices=GROUP_BY_CHOICES,
        default=str(cfg_get("group_by", "platform")),
        help="Report grouping mode: platform (default), topic, none",
    )
    parser.add_argument(
        "--platform-heat-window-days",
        type=int,
        default=int(cfg_get("platform_heat_window_days", 30)),
        help="Platform heat lookback window days (default: 30, only for --group-by platform)",
    )
    parser.add_argument(
        "--per-platform-limit",
        type=int,
        default=int(cfg_get("per_platform_limit", 0)),
        help="When --group-by platform: keep top N items per platform (default: 0 = disabled).",
    )
    parser.add_argument(
        "--platform-top-by",
        choices=["recent", "quality"],
        default=str(cfg_get("platform_top_by", "recent")),
        help="When using --per-platform-limit: select top items by recent (default) or quality.",
    )
    parser.add_argument(
        "--select-keys-file",
        default=cfg_defaults.get("select_keys_file", None),
        help="Optional file of platform keywords (one per line) to filter sources by name/url.",
    )
    parser.add_argument(
        "--select-key",
        action="append",
        default=None,
        help="Optional platform keyword (repeatable) to filter sources by name/url.",
    )
    parser.add_argument(
        "--github-top10",
        dest="github_top10",
        action="store_true",
        default=None,
        help="Include GitHub Trending top 10 (default: enabled in repo auto-mode).",
    )
    parser.add_argument(
        "--no-github-top10",
        dest="github_top10",
        action="store_false",
        default=None,
        help="Disable GitHub Trending top 10.",
    )
    parser.add_argument(
        "--github-trending-since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="GitHub Trending window (default: daily).",
    )
    parser.add_argument(
        "--export-json",
        dest="export_json",
        action="store_true",
        default=None,
        help="Write structured JSON data under NewsReport/data (default: enabled).",
    )
    parser.add_argument(
        "--no-export-json",
        dest="export_json",
        action="store_false",
        default=None,
        help="Disable writing structured JSON data.",
    )
    parser.add_argument(
        "--build-site",
        dest="build_site",
        action="store_true",
        default=None,
        help="Update local reading site under ./site (default: enabled in repo auto-mode).",
    )
    parser.add_argument(
        "--no-build-site",
        dest="build_site",
        action="store_false",
        default=None,
        help="Disable updating local reading site.",
    )
    parser.add_argument(
        "--site-dir",
        default=DEFAULT_REPO_SITE_DIR,
        help="Site output directory (default: ./site).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write report/cache files")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI even if OPENAI_API_KEY is set")
    parser.add_argument("--openai-model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), help="OpenAI model")
    parser.add_argument(
        "--foreign-news-section",
        action="store_true",
        help="Add a separate section by randomly sampling foreign-news feeds (source name/url keyword match).",
    )
    parser.add_argument(
        "--foreign-source-key",
        action="append",
        default=None,
        help="Keyword for identifying foreign-news sources (repeatable).",
    )
    parser.add_argument(
        "--foreign-sample-feeds",
        type=int,
        default=3,
        help="How many foreign-news feed URLs to randomly sample (default: 3).",
    )
    parser.add_argument(
        "--foreign-section-limit",
        type=int,
        default=10,
        help="How many items to keep in the foreign-news section (default: 10).",
    )
    parser.add_argument(
        "--foreign-seed",
        default=None,
        help="Optional random seed for foreign-news sampling (default: deterministic by date).",
    )
    args = parser.parse_args(argv)

    # Apply config-only defaults that are awkward to express in argparse defaults.
    # (e.g. --sources is "append", and some flags use tri-state None/True/False.)
    if not args.sources:
        cfg_sources = cfg_defaults.get("sources")
        if isinstance(cfg_sources, list) and cfg_sources:
            args.sources = [str(x).strip() for x in cfg_sources if str(x).strip()]

    for tri_flag in ["prefer_ipv4", "github_top10", "export_json", "build_site"]:
        if getattr(args, tri_flag, None) is None and isinstance(cfg_defaults.get(tri_flag), bool):
            setattr(args, tri_flag, bool(cfg_defaults.get(tri_flag)))

    proxies: Optional[Dict[str, str]] = None
    proxy = normalize_ws(str(getattr(args, "proxy", "") or ""))
    if proxy:
        proxies = {"http": proxy, "https": proxy}

    date_str = parse_date_arg(args.date)
    os.makedirs(args.out_dir, exist_ok=True)

    # Repo-friendly defaults:
    # - If this repo has RSS源.md + my/RSS.md and user didn't pass --sources,
    #   auto use them so keys like “知乎 / V2EX / 雪球 …” actually get fetched.
    # - Otherwise fall back to the skill's own sources.md (publishable behavior).
    auto_mode = False
    if not args.sources:
        if os.path.exists(DEFAULT_REPO_CATALOG_PATH) and os.path.exists(DEFAULT_REPO_KEYS_PATH):
            args.sources = [DEFAULT_REPO_CATALOG_PATH]
            if not args.select_keys_file:
                args.select_keys_file = DEFAULT_REPO_KEYS_PATH
            auto_mode = True
        else:
            args.sources = [os.path.join(SKILL_DIR, "sources.md")]

    # Auto-mode = 更偏“全量抓取再精选”的体验：不改用户显式传参，只在默认值时适度放宽。
    if auto_mode:
        if int(args.time_budget) == 120:
            args.time_budget = 240
        if int(args.per_feed_limit) == 10:
            args.per_feed_limit = 30
        if args.prefer_ipv4 is None:
            args.prefer_ipv4 = True

    if bool(args.prefer_ipv4):
        force_requests_ipv4()

    sources_files = args.sources
    all_sources: List[FeedSource] = []
    seen_urls: set[str] = set()
    for p in sources_files:
        for s in parse_sources_file(p):
            if s.url in seen_urls:
                continue
            seen_urls.add(s.url)
            all_sources.append(s)

    sources = list(all_sources)

    selected_keys: List[str] = []
    if args.select_keys_file:
        selected_keys.extend(read_keys_file(args.select_keys_file))
    if args.select_key:
        selected_keys.extend([normalize_ws(x) for x in args.select_key if normalize_ws(x)])
    # de-dup while keeping order
    if selected_keys:
        deduped: List[str] = []
        seen_k: set[str] = set()
        for k in selected_keys:
            if k in seen_k:
                continue
            seen_k.add(k)
            deduped.append(k)
        selected_keys = deduped

    if selected_keys:
        # One key = one platform group. Include all matched sources as redundancy,
        # then de-dup entries later (URL + title hash) to avoid missing items due to failures.
        platform_for_source_url: Dict[str, str] = {}
        filtered_sources: List[FeedSource] = []
        for s in sources:
            k = choose_platform_key_for_source(s, selected_keys)
            if not k:
                continue
            platform_for_source_url[s.url] = k
            filtered_sources.append(s)
        sources = filtered_sources
        if not sources:
            raise SystemExit(f"No sources matched the selected keys: {selected_keys}")
        matched = set(platform_for_source_url.values())
        missing = [k for k in selected_keys if k not in matched]
        if missing:
            print(f"Warning: no sources matched keys: {missing}", file=sys.stderr)
    else:
        platform_for_source_url = {}

    enable_github_top10 = bool(args.github_top10) if args.github_top10 is not None else bool(auto_mode)
    if enable_github_top10:
        gh_url = f"https://github.com/trending?since={args.github_trending_since}"
        if gh_url not in {s.url for s in sources}:
            gh_src = FeedSource(name="GitHub Trending", url=gh_url, weight=60.0)
            sources.append(gh_src)
            all_sources.append(gh_src)
            platform_for_source_url.setdefault(gh_url, "GitHub")

    cache = load_cache(DEFAULT_CACHE_PATH)
    t0 = time.time()
    platform_heat = compute_platform_heat(
        cache=cache,
        sources=sources,
        today=dt.date.fromisoformat(date_str),
        window_days=int(args.platform_heat_window_days),
        group_for_source=(lambda s: platform_for_source_url.get(s.url, s.name)),
    )

    entries: List[FeedEntry] = []
    errors: List[str] = []
    success_source_urls: set[str] = set()
    failed_source_urls: set[str] = set()
    skipped_source_urls: set[str] = set()
    platform_sources: Dict[str, List[FeedSource]] = {}
    for s in sources:
        plat = platform_for_source_url.get(s.url, s.name)
        platform_sources.setdefault(str(plat), []).append(s)

    def fetch_one(src: FeedSource) -> List[FeedEntry]:
        if src.url.startswith("https://github.com/trending"):
            items = fetch_github_trending_source(
                src,
                date_str=date_str,
                retries=int(args.retries),
                retry_sleep_ms=int(args.retry_sleep_ms),
                proxies=proxies,
            )
        else:
            per_feed_limit = int(src.per_feed_limit) if src.per_feed_limit else int(args.per_feed_limit)
            items = fetch_and_parse_source(
                src,
                per_feed_limit=per_feed_limit,
                retries=int(args.retries),
                retry_sleep_ms=int(args.retry_sleep_ms),
                proxies=proxies,
            )
        plat = platform_for_source_url.get(src.url)
        if plat:
            for it in items:
                it.platform = plat
        return items

    # Concurrency cap: be polite to the network.
    max_workers = min(12, max(4, len(sources)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_src = {ex.submit(fetch_one, src): src for src in sources}
        done: set[Any] = set()
        for fut in as_completed(future_to_src):
            if (time.time() - t0) > float(args.time_budget):
                for pf, ps in future_to_src.items():
                    if pf not in done:
                        skipped_source_urls.add(ps.url)
                break
            src = future_to_src[fut]
            done.add(fut)
            try:
                entries.extend(fut.result())
                success_source_urls.add(src.url)
            except Exception as e:
                errors.append(f"{src.name} ({src.url}): {e}")
                failed_source_urls.add(src.url)

    entries = dedupe_entries(entries, cache, date_str=date_str)

    enable_ai = (not args.no_ai) and bool(os.getenv("OPENAI_API_KEY"))
    enriched: List[EnrichedEntry] = []
    for e in entries:
        carrier = carrier_from_entry(e)
        category = classify_topic(e)
        q = score_entry(e, category, carrier)
        if q < float(args.min_score):
            continue

        ai = maybe_ai_enrich(e, category=category, carrier=carrier, enable_ai=enable_ai, model=args.openai_model)
        if ai:
            summary, key_points, keywords, q2, title_zh = ai
            enriched.append(
                EnrichedEntry(
                    entry=e,
                    category=category,
                    carrier=carrier,
                    quality_score=q2,
                    keywords=keywords,
                    summary=summary,
                    key_points=key_points,
                    title_zh=title_zh,
                )
            )
        else:
            summary, key_points = fallback_summary(e)
            enriched.append(
                EnrichedEntry(
                    entry=e,
                    category=category,
                    carrier=carrier,
                    quality_score=q,
                    keywords=derive_keywords(e),
                    summary=summary,
                    key_points=key_points,
                )
            )

    if args.group_by in {"platform", "none"}:
        enriched.sort(
            key=lambda x: (
                -float(platform_heat.get(x.entry.platform or x.entry.source_name or "未知来源", 0.0)),
                -x.quality_score,
                x.entry.title.lower(),
            )
        )
    elif args.group_by == "topic":
        enriched.sort(key=lambda x: (-x.quality_score, x.category, x.entry.title.lower()))
    else:
        enriched.sort(key=lambda x: (-x.quality_score, x.entry.title.lower()))

    per_platform_limit = max(0, int(args.per_platform_limit))
    if selected_keys and args.group_by == "platform" and per_platform_limit == 0:
        per_platform_limit = 10
    max_items_arg = args.max_items
    if max_items_arg is None:
        # Keep legacy behavior unless user explicitly turns on per-platform top-N.
        max_items = 0 if (args.group_by == "platform" and per_platform_limit > 0) else 50
    else:
        max_items = int(max_items_arg)
    if max_items < 0:
        max_items = 50

    if args.group_by == "platform" and per_platform_limit > 0:
        by_platform: Dict[str, List[EnrichedEntry]] = {}
        for it in enriched:
            by_platform.setdefault(it.entry.platform or it.entry.source_name or "未知来源", []).append(it)

        def within_platform_sort_key(it: EnrichedEntry) -> Tuple[Any, ...]:
            pub = parse_published_dt(it.entry) or dt.datetime.min
            pub_ts = (
                pub.replace(tzinfo=dt.timezone.utc).timestamp() if pub != dt.datetime.min else float("-inf")
            )
            if args.platform_top_by == "quality":
                return (-it.quality_score, -pub_ts, it.entry.title.lower())
            return (-pub_ts, -it.quality_score, it.entry.title.lower())

        for p in by_platform:
            by_platform[p].sort(key=within_platform_sort_key)
            by_platform[p] = by_platform[p][:per_platform_limit]

        def p_sort_key(p: str) -> Tuple[float, str]:
            return (-float(platform_heat.get(p, 0.0)), p)

        published: List[EnrichedEntry] = []
        for p in sorted(by_platform.keys(), key=p_sort_key):
            published.extend(by_platform[p])
        if max_items > 0:
            published = published[: max(1, max_items)]
    else:
        published = enriched if max_items == 0 else enriched[: max(1, max_items)]

    # -----------------------------
    # Optional: foreign-news section
    # -----------------------------

    foreign_section_title: Optional[str] = None
    foreign_section_sources: List[FeedSource] = []
    foreign_section_entries: List[FeedEntry] = []
    foreign_section_enriched: List[EnrichedEntry] = []
    foreign_section_success_urls: set[str] = set()
    foreign_section_failed_urls: set[str] = set()
    foreign_section_skipped_urls: set[str] = set()
    foreign_section_errors: List[str] = []
    foreign_section_limit = max(1, int(args.foreign_section_limit))

    if bool(args.foreign_news_section):
        foreign_section_title = "国外时政"
        foreign_keys = args.foreign_source_key or [
            "国际",
            "world",
            "foreign",
            "realtime/world",
            "/world",
            "global",
            "外交",
            "worldnews",
        ]
        candidates = [s for s in all_sources if source_matches_any_key(s, foreign_keys)]
        candidates = [s for s in candidates if s.url]
        if candidates:
            seed_str = str(args.foreign_seed or date_str)
            rng = random.Random(hashlib.sha1(seed_str.encode("utf-8", errors="ignore")).hexdigest())
            rng.shuffle(candidates)
            k = max(1, int(args.foreign_sample_feeds))
            foreign_section_sources = candidates[: min(k, len(candidates))]

            def fetch_foreign_one(src: FeedSource) -> List[FeedEntry]:
                per_feed_limit = int(src.per_feed_limit) if src.per_feed_limit else int(args.per_feed_limit)
                items = fetch_and_parse_source(
                    src,
                    per_feed_limit=per_feed_limit,
                    retries=int(args.retries),
                    retry_sleep_ms=int(args.retry_sleep_ms),
                    proxies=proxies,
                )
                for it in items:
                    it.platform = foreign_section_title or src.name
                return items

            max_workers2 = min(6, max(1, len(foreign_section_sources)))
            with ThreadPoolExecutor(max_workers=max_workers2) as ex2:
                f2s = {ex2.submit(fetch_foreign_one, s): s for s in foreign_section_sources}
                done2: set[Any] = set()
                for fut in as_completed(f2s):
                    # Use the same overall time budget; don't block the whole run.
                    if (time.time() - t0) > float(args.time_budget):
                        for pf, ps in f2s.items():
                            if pf not in done2:
                                foreign_section_skipped_urls.add(ps.url)
                        break
                    src = f2s[fut]
                    done2.add(fut)
                    try:
                        foreign_section_entries.extend(fut.result())
                        foreign_section_success_urls.add(src.url)
                    except Exception as e:
                        foreign_section_errors.append(f"{src.name} ({src.url}): {e}")
                        foreign_section_failed_urls.add(src.url)

            foreign_section_entries = dedupe_entries(foreign_section_entries, cache, date_str=date_str)

            # Reuse existing enrichment/scoring pipeline.
            foreign_section_enriched = []
            for e in foreign_section_entries:
                carrier = carrier_from_entry(e)
                category = classify_topic(e)
                q = score_entry(e, category, carrier)
                if q < float(args.min_score):
                    continue
                ai = maybe_ai_enrich(
                    e,
                    category=category,
                    carrier=carrier,
                    enable_ai=enable_ai,
                    model=args.openai_model,
                )
                if ai:
                    summary, key_points, keywords, q2, title_zh = ai
                    foreign_section_enriched.append(
                        EnrichedEntry(
                            entry=e,
                            category=category,
                            carrier=carrier,
                            quality_score=q2,
                            keywords=keywords,
                            summary=summary,
                            key_points=key_points,
                            title_zh=title_zh,
                        )
                    )
                else:
                    summary, key_points = fallback_summary(e)
                    foreign_section_enriched.append(
                        EnrichedEntry(
                            entry=e,
                            category=category,
                            carrier=carrier,
                            quality_score=q,
                            keywords=derive_keywords(e),
                            summary=summary,
                            key_points=key_points,
                        )
                    )

            def recent_sort_key(it: EnrichedEntry) -> Tuple[float, float, str]:
                pub = parse_published_dt(it.entry) or dt.datetime.min
                pub_ts = pub.replace(tzinfo=dt.timezone.utc).timestamp() if pub != dt.datetime.min else float("-inf")
                return (-pub_ts, -it.quality_score, it.entry.title.lower())

            foreign_section_enriched.sort(key=recent_sort_key)

    duration_seconds = int(time.time() - t0)
    report_md = build_report(
        date_str=date_str,
        sources=sources,
        items=published,
        duration_seconds=duration_seconds,
        group_by=str(args.group_by),
        platform_heat=platform_heat,
        platform_heat_window_days=int(args.platform_heat_window_days),
        selected_keys=selected_keys,
        per_platform_limit=per_platform_limit,
        platform_sources=platform_sources,
        success_source_urls=success_source_urls,
        failed_source_urls=failed_source_urls,
        skipped_source_urls=skipped_source_urls,
        errors=errors,
        foreign_section_title=foreign_section_title,
        foreign_section_sources=foreign_section_sources,
        foreign_section_success_urls=foreign_section_success_urls,
        foreign_section_failed_urls=foreign_section_failed_urls,
        foreign_section_skipped_urls=foreign_section_skipped_urls,
        foreign_section_errors=foreign_section_errors,
        foreign_section_items=foreign_section_enriched,
        foreign_section_limit=foreign_section_limit,
    )

    if args.dry_run:
        try:
            print(report_md)
        except BrokenPipeError:
            # When piping to `head`, stdout may close early. Treat as success.
            return 0
        return 0

    out_path = os.path.join(args.out_dir, f"{date_str}-rss-daily-report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    cache["last_run"] = {
        "date": date_str,
        "duration_seconds": duration_seconds,
        "items_collected": len(entries),
        "items_published": len(published),
        "sources_used": [s.url for s in sources],
        "errors": errors[:100],
    }

    url_entries = cache["url_cache"].setdefault("entries", {})
    title_entries = cache["title_hashes"].setdefault("entries", {})
    for it in published:
        url_entries[it.entry.url] = {"date_added": date_str}
        title_entries[title_fingerprint(it.entry.title)] = {"date_added": date_str}

    hist = cache.setdefault("article_history", {"_comment": "daily published items"})
    hist[date_str] = [
        {
            "source": it.entry.source_name,
            "platform": it.entry.platform or it.entry.source_name,
            "title": it.entry.title,
            "title_hash": title_fingerprint(it.entry.title),
            "url": it.entry.url,
            "category": it.category,
            "carrier": it.carrier,
            "quality_score": round(it.quality_score, 2),
        }
        for it in published
    ]

    stats = cache.setdefault("source_stats", {"_comment": "per-feed stats keyed by feed URL"})
    for s in sources:
        st = stats.get(s.url) or {"total_fetches": 0, "success_count": 0, "last_fetch": None, "last_success": None}
        st["total_fetches"] = int(st.get("total_fetches") or 0) + 1
        if s.url not in failed_source_urls:
            st["success_count"] = int(st.get("success_count") or 0) + 1
            st["last_success"] = date_str
        st["last_fetch"] = date_str
        stats[s.url] = st

    write_json(DEFAULT_CACHE_PATH, cache)

    print(f"Wrote report: {out_path}")
    print(f"Updated cache: {DEFAULT_CACHE_PATH}")
    enable_export_json = bool(args.export_json) if args.export_json is not None else True
    data_dir = os.path.join(args.out_dir, "data")
    if enable_export_json:
        day_json_path, index_json_path = write_report_data_json(
            data_dir=data_dir,
            date_str=date_str,
            items=published,
            meta={
                "group_by": str(args.group_by),
                "selected_keys": selected_keys,
                "per_platform_limit": int(per_platform_limit),
                "min_score": float(args.min_score),
                "duration_seconds": int(duration_seconds),
                "items_collected": int(len(entries)),
                "items_published": int(len(published)),
                "sources_used": [s.url for s in sources],
            },
        )
        print(f"Wrote data: {day_json_path}")
        print(f"Updated data index: {index_json_path}")

    enable_build_site = bool(args.build_site) if args.build_site is not None else bool(auto_mode)
    if enable_build_site:
        try:
            site_js = write_site_data_js(site_dir=str(args.site_dir), data_dir=str(data_dir))
            print(f"Updated site data: {site_js}")
        except Exception as e:
            print(f"Warning: failed to update site data: {e}", file=sys.stderr)
    if errors:
        print(f"Some sources failed (showing up to 5): {errors[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
    os.replace(tmp, path)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_mostly_english(text: str) -> bool:
    t = normalize_ws(text)
    if not t:
        return False
    if re.search(r"[\u4e00-\u9fff]", t):
        return False
    letters = sum(1 for ch in t if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    if letters < 8:
        return False
    non_space = sum(1 for ch in t if not ch.isspace())
    return (letters / max(1, non_space)) >= 0.45


def split_sentences(text: str) -> List[str]:
    t = normalize_ws(text)
    if not t:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+", t)
    out: List[str] = []
    for p in parts:
        s = normalize_ws(p)
        if s:
            out.append(s)
    return out


def clip(text: str, max_len: int) -> str:
    t = normalize_ws(text)
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def looks_like_roundup(title: str, source: str, platform: str) -> bool:
    t = normalize_ws(title)
    s = normalize_ws(source)
    p = normalize_ws(platform)
    keys = [
        "热榜",
        "榜单",
        "Top",
        "top",
        "Trending",
        "trending",
        "周报",
        "日报",
        "月报",
        "盘点",
        "合集",
        "汇总",
        "快讯",
        "要闻",
        "简报",
        "今日",
        "本周",
        "本月",
    ]
    if any(k in t for k in keys):
        return True
    if any(k in s for k in ("知乎热榜", "GitHub Trending")):
        return True
    if any(k in p for k in ("知乎", "GitHub")) and any(k in t for k in ("热榜", "Trending", "trending")):
        return True
    return False


def parse_published_dt(published: str) -> Optional[dt.datetime]:
    p = normalize_ws(published)
    if not p:
        return None
    # RFC2822 / RFC822
    try:
        d = email.utils.parsedate_to_datetime(p)
        if isinstance(d, dt.datetime):
            return d
    except Exception:
        pass
    # ISO-ish
    try:
        d = dt.datetime.fromisoformat(p.replace("Z", "+00:00"))
        return d
    except Exception:
        return None


def recency_bonus(*, report_day: dt.date, published: Optional[str]) -> float:
    if not published:
        return 0.0
    d = parse_published_dt(published)
    if not d:
        return 0.0
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    pub_day = d.astimezone(dt.timezone.utc).date()
    delta = (report_day - pub_day).days
    if delta < 0:
        return -0.2
    if delta <= 2:
        return 0.45
    if delta <= 7:
        return 0.15
    if delta <= 14:
        return -0.75
    if delta <= 30:
        return -1.0
    return -1.6


def promo_penalty(title: str, summary: str) -> float:
    t = normalize_ws(title)
    s = normalize_ws(summary)
    text = f"{t} {s}"
    keys = ["报名", "申领", "席位", "限量", "邀您", "峰会", "大会", "研讨会", "直播", "购票", "优惠", "领取", "登记", "赞助"]
    if any(k in text for k in keys):
        return -1.1
    return 0.0


def basic_zh_title_fallback(title: str) -> str:
    """
    不依赖外部服务的“尽力翻译”：
    - 用小词典把常见结构翻成中文
    - 未知词保留英文（保证可读）
    """

    t = normalize_ws(title)
    if not t:
        return ""

    # Keep common proper nouns / acronyms as-is.
    dict_pairs: List[Tuple[str, str]] = [
        ("How to", "如何"),
        ("how to", "如何"),
        ("Why", "为什么"),
        ("what", "什么"),
        ("What", "什么"),
        ("Guide", "指南"),
        ("guide", "指南"),
        ("Release", "发布"),
        ("release", "发布"),
        ("Announce", "宣布"),
        ("announces", "宣布"),
        ("announced", "宣布"),
        ("New", "新的"),
        ("new", "新的"),
        ("Update", "更新"),
        ("update", "更新"),
        ("Security", "安全"),
        ("security", "安全"),
        ("Vulnerability", "漏洞"),
        ("vulnerability", "漏洞"),
        ("Open source", "开源"),
        ("open source", "开源"),
        ("OpenAI", "OpenAI"),
        ("AI", "AI"),
        ("LLM", "LLM"),
        ("GPU", "GPU"),
        ("Python", "Python"),
        ("Rust", "Rust"),
        ("Go", "Go"),
        ("JavaScript", "JavaScript"),
    ]
    out = t
    for a, b in dict_pairs:
        out = out.replace(a, b)
    # Light punctuation normalization for better Chinese reading.
    out = out.replace(":", "：")
    if out == t:
        return f"{t}（英文原题）"
    return out


def basic_zh_summary_fallback(*, title_zh: str, summary: str) -> str:
    """
    英文摘要兜底：尽量中文化表达，但不承诺完整翻译。
    """

    s = normalize_ws(summary)
    if not s:
        return ""
    if not is_mostly_english(s):
        return s
    lead = clip(split_sentences(s)[0] if split_sentences(s) else s, 120)
    base = normalize_ws(title_zh) or "这条内容"
    return f"{base}。要点：{lead}"


def rewrite_roundup_summary(*, title: str, summary: str, platform: str, source: str) -> str:
    s = normalize_ws(summary)
    if not s:
        return f"合集/热榜：来自 {platform or source} 的聚合内容。"
    # Make the function idempotent: if already rewritten, don't wrap again.
    if s.startswith("合集/热榜（") or s.startswith("合集/热榜："):
        s = re.sub(r"^合集/热榜（[^)]*）[:：]?", "", s).strip()
        s = re.sub(r"^合集/热榜[:：]?", "", s).strip()
    points: List[str] = []
    # Try list-like patterns first.
    for part in re.split(r"(?:\\n|\\r|\\t|；|;)", summary):
        p = normalize_ws(part)
        if not p:
            continue
        if re.match(r"^\\s*(?:\\d+\\s*[、.。)]|[-*])\\s+", p):
            p = re.sub(r"^\\s*(?:\\d+\\s*[、.。)]|[-*])\\s+", "", p).strip()
            if p and not re.fullmatch(r"[\\W_]*\\d*[\\W_]*", p):
                points.append(p)
        if len(points) >= 3:
            break
    if not points:
        # Fallback: pick first 2 sentences.
        points = split_sentences(s)[:2]
    cleaned: List[str] = []
    for p in points:
        x = normalize_ws(p)
        x = re.sub(r"^\\s*\\d+\\s*[、.。)]\\s*", "", x).strip()
        if not x or re.fullmatch(r"[\\W_]*\\d*[\\W_]*", x):
            continue
        cleaned.append(clip(x, 60))
    points = cleaned
    head = normalize_ws(platform or source or "来源")
    if points:
        joined = "；".join(points)
        return f"合集/热榜（{head}）：{joined}"
    return f"合集/热榜（{head}）：{clip(s, 140)}"


def category_bonus(category: str) -> float:
    c = normalize_ws(category)
    if c == "技术":
        return 1.1
    if c == "财经":
        return 0.6
    if c == "商业/产品":
        return 0.3
    if c == "时事":
        return 0.1
    return 0.0


def info_density_bonus(title: str, summary: str) -> float:
    t = normalize_ws(title)
    s = normalize_ws(summary)
    score = 0.0
    if len(s) < 40:
        score -= 0.4
    elif 80 <= len(s) <= 220:
        score += 0.4
    elif len(s) > 360:
        score -= 0.2

    if re.search(r"\\d", f"{t} {s}"):
        score += 0.15
    if any(k in f"{t} {s}" for k in ("开源", "漏洞", "安全", "发布", "财报", "利率", "通胀", "GPU", "LLM", "AI")):
        score += 0.15
    if any(k in t for k in ("为什么", "如何", "指南", "复盘", "剖析")):
        score += 0.1
    return score


def infer_focus_tag(item: Dict[str, Any]) -> str:
    category = normalize_ws(str(item.get("category") or ""))
    title = normalize_ws(str(item.get("title_zh") or item.get("title") or ""))
    summary = normalize_ws(str(item.get("summary") or ""))
    text = f"{title} {summary}"

    if category == "技术":
        return "tech"
    if category == "财经":
        return "finance"

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
        "docker",
        "git",
        "模型",
        "智能体",
    ]
    finance_kw = ["股票", "基金", "美股", "a股", "港股", "投资", "经济", "利率", "通胀", "财报", "央行", "比特币", "黄金", "大宗"]
    low_value_ent = ["电影", "电视剧", "综艺", "里番", "蓝光", "烂片", "手游", "抽奖"]

    lower = text.lower()
    if "product hunt" in lower or "producthunt" in lower or "ph今日热榜" in text or "ph 今日热榜" in text:
        return "tech"

    def contains_any(haystack: str, haystack_lower: str, needles: Iterable[str]) -> bool:
        for n in needles:
            nn = str(n)
            if not nn:
                continue
            if re.fullmatch(r"[A-Za-z0-9+_.-]{1,32}", nn):
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(nn.lower())}(?![A-Za-z0-9])", haystack_lower):
                    return True
            else:
                if nn in haystack:
                    return True
        return False

    if contains_any(text, lower, tech_kw):
        return "tech"
    if contains_any(text, lower, finance_kw):
        return "finance"
    if any(k in text for k in low_value_ent):
        return "ent"
    return "other"


@dataclass(frozen=True)
class Pick:
    idx: int
    url: str
    score: float


def compute_pick_score(item: Dict[str, Any]) -> float:
    quality = item.get("quality_score")
    q = float(quality) if isinstance(quality, (int, float)) else 0.0
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    category = str(item.get("category") or "")
    platform = str(item.get("platform") or "")
    source = str(item.get("source") or "")
    published = str(item.get("published") or "")

    score = q + category_bonus(category) + info_density_bonus(title, summary)
    score += promo_penalty(title, summary)
    # Recency: strongly prefer items close to the report day.
    report_day = dt.date.today()
    try:
        report_day = dt.date.fromisoformat(str(item.get("date") or "").strip()) or report_day
    except Exception:
        pass
    score += recency_bonus(report_day=report_day, published=published)

    is_roundup = looks_like_roundup(title, source, platform)
    if is_roundup:
        # Roundups are useful but rarely serve as the lead story.
        score -= 0.35
    tag = infer_focus_tag(item)
    # Developer-first: de-prioritize purely entertainment-ish items unless they are clearly valuable.
    if tag == "ent":
        score -= 0.6
    if is_mostly_english(title) and not normalize_ws(str(item.get("title_zh") or "")):
        score -= 0.15
    return score


def pick_items(
    *,
    items: List[Dict[str, Any]],
    lead_n: int,
    top_n: int,
    max_per_platform: int = 3,
    max_per_source: int = 1,
    min_top_tech: int = 2,
) -> Tuple[List[int], List[int]]:
    ranked: List[Pick] = []
    for i, it in enumerate(items):
        url = str(it.get("url") or "")
        if not url:
            continue
        ranked.append(Pick(idx=i, url=url, score=compute_pick_score(it)))
    ranked.sort(key=lambda x: (-x.score, x.url))

    exclude: set[int] = set()
    per_platform: Dict[str, int] = {}
    per_source: Dict[str, int] = {}

    def take(target_n: int, *, only: Optional[callable] = None) -> List[int]:
        out: List[int] = []

        def can_take(it: Dict[str, Any], *, relaxed: bool) -> bool:
            if relaxed:
                return True
            platform = str(it.get("platform") or "").strip()
            source = str(it.get("source") or "").strip()
            if platform and per_platform.get(platform, 0) >= max_per_platform:
                return False
            if source and per_source.get(source, 0) >= max_per_source:
                return False
            return True

        def apply_take(it: Dict[str, Any]) -> None:
            platform = str(it.get("platform") or "").strip()
            source = str(it.get("source") or "").strip()
            if platform:
                per_platform[platform] = per_platform.get(platform, 0) + 1
            if source:
                per_source[source] = per_source.get(source, 0) + 1

        # Two-pass: strict caps then relaxed (if not enough).
        for relaxed in (False, True):
            for p in ranked:
                if p.idx in exclude or p.idx in out:
                    continue
                it = items[p.idx]
                if only is not None and not bool(only(it)):
                    continue
                if not can_take(it, relaxed=relaxed):
                    continue
                out.append(p.idx)
                exclude.add(p.idx)
                apply_take(it)
                if len(out) >= target_n:
                    return out
            if len(out) >= target_n:
                return out
        return out

    def lead_only(it: Dict[str, Any]) -> bool:
        tag = infer_focus_tag(it)
        if tag not in {"tech", "finance"}:
            return False
        title = str(it.get("title") or "")
        platform = str(it.get("platform") or "")
        source = str(it.get("source") or "")
        if looks_like_roundup(title, source, platform):
            return False
        if promo_penalty(title, str(it.get("summary") or "")) < 0:
            return False
        return True

    lead = take(lead_n, only=lead_only)
    if len(lead) < lead_n:
        # Reset and retry without the tech-only constraint.
        exclude.clear()
        per_platform.clear()
        per_source.clear()
        lead = take(lead_n)

    want_tech = max(0, min(int(min_top_tech), int(top_n)))
    top: List[int] = []
    if want_tech:
        top.extend(take(want_tech, only=lambda it: infer_focus_tag(it) == "tech"))
    if len(top) < top_n:
        # Prefer keeping the section "developer useful": tech/finance first, then fallback to anything.
        remain = top_n - len(top)
        top.extend(take(remain, only=lambda it: infer_focus_tag(it) in {"tech", "finance"}))
    if len(top) < top_n:
        top.extend(take(top_n - len(top)))
    return lead, top


def apply_pins_and_localize(
    *,
    day: Dict[str, Any],
    lead_idx: List[int],
    top_idx: List[int],
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = list(day.get("items") or [])
    lead_set, top_set = set(lead_idx), set(top_idx)

    for i, it in enumerate(items):
        it["pin"] = "lead" if i in lead_set else ("top" if i in top_set else None)

        if i not in lead_set and i not in top_set:
            continue

        title = str(it.get("title") or "")
        platform = str(it.get("platform") or "")
        source = str(it.get("source") or "")
        summary = str(it.get("summary") or "")

        title_zh = normalize_ws(str(it.get("title_zh") or ""))
        if not title_zh and is_mostly_english(title):
            it["title_zh"] = basic_zh_title_fallback(title)
            title_zh = normalize_ws(str(it.get("title_zh") or ""))

        if looks_like_roundup(title, source, platform):
            if not normalize_ws(summary).startswith("合集/热榜"):
                it["summary"] = rewrite_roundup_summary(title=title, summary=summary, platform=platform, source=source)
        else:
            it["summary"] = basic_zh_summary_fallback(title_zh=title_zh or title, summary=summary) or normalize_ws(summary)

    meta = day.get("meta") if isinstance(day.get("meta"), dict) else {}
    meta = dict(meta)
    meta["editor_picks"] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "lead_n": len(lead_idx),
        "top_n": len(top_idx),
        "lead_urls": [items[i].get("url") for i in lead_idx if 0 <= i < len(items)],
        "top_urls": [items[i].get("url") for i in top_idx if 0 <= i < len(items)],
        "note": "rule-based offline; prefers tech/finance and high information density",
    }
    day["meta"] = meta
    day["items"] = items
    return day


PICKS_START = "<!-- editorial-picks:start -->"
PICKS_END = "<!-- editorial-picks:end -->"


def render_picks_md(*, lead: Sequence[Dict[str, Any]], top: Sequence[Dict[str, Any]]) -> str:
    def line_for(it: Dict[str, Any]) -> str:
        title = normalize_ws(str(it.get("title_zh") or it.get("title") or ""))
        platform = normalize_ws(str(it.get("platform") or ""))
        category = normalize_ws(str(it.get("category") or ""))
        score = it.get("quality_score")
        score_s = f"{score:.2f}" if isinstance(score, (int, float)) else ""
        url = normalize_ws(str(it.get("url") or ""))
        meta = " · ".join([x for x in (platform, category, score_s and f"评分 {score_s}") if x])
        meta = f"（{meta}）" if meta else ""
        return f"- **{title}**{meta} — {url}"

    def summary_for(it: Dict[str, Any]) -> str:
        s = clip(str(it.get("summary") or ""), 140)
        return f"  - 摘要：{s}" if s else ""

    lines: List[str] = [PICKS_START, "## 头条"]
    for it in lead:
        lines.append(line_for(it))
        s = summary_for(it)
        if s:
            lines.append(s)
    lines.append("")
    lines.append("## 精选")
    for it in top:
        lines.append(line_for(it))
        s = summary_for(it)
        if s:
            lines.append(s)
    lines.append(PICKS_END)
    return "\n".join(lines).strip() + "\n"


def upsert_picks_block(report_md: str, picks_block: str) -> str:
    md = report_md
    if PICKS_START in md and PICKS_END in md:
        pre, rest = md.split(PICKS_START, 1)
        _, post = rest.split(PICKS_END, 1)
        return pre.rstrip() + "\n\n" + picks_block.strip() + "\n\n" + post.lstrip()

    # Insert after the first horizontal rule (---) and before the first section.
    marker = "\n---\n\n"
    pos = md.find(marker)
    if pos >= 0:
        insert_at = pos + len(marker)
        return md[:insert_at] + picks_block.strip() + "\n\n" + md[insert_at:]
    # Fallback: prepend.
    return picks_block.strip() + "\n\n" + md.lstrip()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pick editorial lead/top items and write back to JSON + Markdown.")
    parser.add_argument("date", nargs="?", default="", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--lead-n", type=int, default=1, help="How many lead items to pin (default: 1)")
    parser.add_argument("--top-n", type=int, default=5, help="How many top items to pin (default: 5)")
    parser.add_argument("--min-top-tech", type=int, default=2, help="Ensure at least N tech items in top picks when possible (default: 2)")
    parser.add_argument("--day-json", default="", help="Path to day JSON (default: NewsReport/data/YYYY-MM-DD.json)")
    parser.add_argument("--report-md", default="", help="Path to report Markdown (default: NewsReport/YYYY-MM-DD-rss-daily-report.md)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    date_str = normalize_ws(str(args.date or ""))
    if not date_str:
        date_str = dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(date_str)
    except Exception:
        raise SystemExit(f"Invalid date: {date_str} (expected YYYY-MM-DD)")

    day_json_path = args.day_json or os.path.join(REPO_ROOT, "NewsReport", "data", f"{date_str}.json")
    report_md_path = args.report_md or os.path.join(REPO_ROOT, "NewsReport", f"{date_str}-rss-daily-report.md")

    day = read_json(day_json_path)
    items = list(day.get("items") or [])
    if not items:
        raise SystemExit(f"No items found in {day_json_path}")

    lead_n = max(1, int(args.lead_n))
    top_n = max(0, int(args.top_n))
    min_top_tech = max(0, int(args.min_top_tech))
    lead_idx, top_idx = pick_items(items=items, lead_n=lead_n, top_n=top_n, min_top_tech=min_top_tech)

    day = apply_pins_and_localize(day=day, lead_idx=lead_idx, top_idx=top_idx)
    write_json(day_json_path, day)

    lead_items = [day["items"][i] for i in lead_idx if 0 <= i < len(day["items"])]
    top_items = [day["items"][i] for i in top_idx if 0 <= i < len(day["items"])]
    picks_block = render_picks_md(lead=lead_items, top=top_items)

    if os.path.exists(report_md_path):
        report = read_text(report_md_path)
        updated = upsert_picks_block(report, picks_block)
        write_text(report_md_path, updated)

    print(f"Pinned lead={len(lead_items)} top={len(top_items)} in {day_json_path}")
    if os.path.exists(report_md_path):
        print(f"Updated report: {report_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

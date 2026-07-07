#!/usr/bin/env python3
"""job-searcher :: KOWORK collector — self-contained, read-only.

Collects recent public postings from KOWORK's (kowork.kr) English jobs-for-
foreigners listing and prints a normalized JSON array (see docs/SCHEMA.md). No
login, no save, no apply — a plain GET of the public `/en` listing only. The
listing is server-rendered but only the first page (~15 postings) is in the
static HTML; more requires a browser (infinite scroll). The listing does not
accept a GET keyword, so `--query` filters client-side by title/company
substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "developer" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "kowork"
BASE = "https://kowork.kr"
LIST_URL = BASE + "/en"

_POST = re.compile(r"/en/post/(\d+)")
_LOGO_ALT = re.compile(r"job-list-(.*?)-logo")
_DEADLINE = re.compile(r"(D-\d+|D-DAY|Always|Closed|마감)", re.IGNORECASE)
_EMP = re.compile(r"(Full[\s-]?Time|Part[\s-]?Time|Contract|Intern(?:ship)?|Freelance|Temporary)", re.IGNORECASE)


@dataclass
class JobPosting:
    source: str
    external_id: str | None
    url: str
    title: str
    company: str | None
    location: str | None
    employment_type: str | None
    posted_at: str | None
    deadline: str | None
    salary: str | None
    snippet: str | None
    collected_at: str


def _fetch(url: str, timeout: int) -> str:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.get(url, impersonate="safari", timeout=timeout)
    resp.raise_for_status()
    return resp.text


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    html = _fetch(LIST_URL, timeout)
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("a[href*='/en/post/']"):
        m = _POST.search(card.get("href", ""))
        post_id = m.group(1) if m else None
        if not post_id or post_id in seen:
            continue
        tit = card.select_one("p.line-clamp-2") or card.find("p")
        title = tit.get_text(strip=True) if tit else ""
        if not title:
            continue
        img = card.find("img")
        company = None
        if img and img.get("alt"):
            am = _LOGO_ALT.search(img["alt"])
            if am:
                company = am.group(1).strip() or None
        # Metadata pills (visa / location / type / category) appear twice
        # (desktop + mobile blocks); dedup on text, keep first-seen order.
        tags: list[str] = []
        for p in card.select("p[class*='rounded']"):
            t = p.get_text(strip=True)
            if t and t not in tags:
                tags.append(t)
        emp = next((t for t in tags if _EMP.fullmatch(t) or _EMP.match(t)), None)
        loc = next((t for t in tags if "," in t), None)
        dl = _DEADLINE.search(card.get_text(" ", strip=True))
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        seen.add(post_id)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=post_id,
                url=f"{BASE}/en/post/{post_id}",
                title=title,
                company=company,
                location=loc,
                employment_type=emp,
                posted_at=None,
                deadline=dl.group(0) if dl else None,
                salary=None,
                snippet=", ".join(tags) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from KOWORK (jobs for foreigners in Korea).")
    ap.add_argument("--query", "-q", default=None,
                    help="filter the listing by title/company substring (client-side)")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.timeout)
    except Exception as exc:  # network / parse failure — honest, no fabrication
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings"
          + (f" for query={args.query!r}" if args.query else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

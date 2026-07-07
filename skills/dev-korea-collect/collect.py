#!/usr/bin/env python3
"""job-searcher :: Dev Korea collector — self-contained, read-only.

Collects recent public postings from Dev Korea's (dev-korea.com) jobs listing
and prints a normalized JSON array (see docs/SCHEMA.md). The listing is
server-rendered HTML, so this is a plain GET of the public /jobs page only — no
login, no save, no apply. `--query` filters the listing client-side by
title/company/location/tag substring (the site's own search box is JS-only, so
the server returns the same first page regardless of query params).

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "data" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "dev-korea"
BASE = "https://dev-korea.com"
LISTING_URL = BASE + "/jobs"

_SLUG = re.compile(r"/jobs/([\w-]+)")


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

    html = _fetch(LISTING_URL, timeout)
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("li.dk-border"):
        # title anchor: the /jobs/<slug> anchor that wraps a text paragraph
        title_a = None
        for a in card.select('a[href^="/jobs/"]'):
            if a.find("p"):
                title_a = a
                break
        if title_a is None:
            continue
        m = _SLUG.search(title_a.get("href", ""))
        slug = m.group(1) if m else None
        if not slug or slug in seen:
            continue
        title_p = title_a.find("p")
        title = title_p.get_text(strip=True) if title_p else title_a.get_text(strip=True)
        if not title:
            continue

        corp = card.select_one('a[href^="/companies/"] p') or card.select_one('a[href^="/companies/"]')
        company = corp.get_text(strip=True) if corp else None

        # meta line e.g. "Seoul (On-site) • Full-time"
        meta_p = card.select_one("p.mt-3")
        location = employment_type = None
        if meta_p:
            parts = [p.strip() for p in meta_p.get_text(" ", strip=True).split("•") if p.strip()]
            if parts:
                location = parts[0]
            if len(parts) > 1:
                employment_type = parts[1]

        tags = [li.get_text(strip=True) for li in card.select("ul li") if li.get_text(strip=True)]
        snippet = ", ".join(tags) or None

        haystack = " ".join(filter(None, [title, company, location, employment_type, snippet])).lower()
        if needle and needle not in haystack:
            continue

        seen.add(slug)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=slug,
                url=f"{BASE}/jobs/{slug}",
                title=title,
                company=company,
                location=location,
                employment_type=employment_type,
                posted_at=None,
                deadline=None,
                salary=None,
                snippet=snippet,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Dev Korea.")
    ap.add_argument("--query", "-q", default=None, help="filter listing by title/company/tag substring")
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

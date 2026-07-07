#!/usr/bin/env python3
"""job-seeker :: We Work Remotely collector — self-contained, read-only.

Collects recent public remote postings from We Work Remotely's public RSS feed
and prints a normalized JSON array (see docs/SCHEMA.md). RSS is a first-class
public interface, so this is a plain GET of a published feed — no login, save,
or apply. `--query` filters the feed client-side by title/company substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "engineer" --limit 20
    python3 collect.py --category remote-programming-jobs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

SOURCE = "weworkremotely"
BASE = "https://weworkremotely.com"
MAIN_FEED = BASE + "/remote-jobs.rss"
CATEGORY_FEED = BASE + "/categories/{cat}.rss"

_SLUG = re.compile(r"/remote-jobs/([^/?#]+)")


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


def _iso(rfc822: str | None) -> str | None:
    if not rfc822:
        return None
    try:
        return parsedate_to_datetime(rfc822).date().isoformat()
    except (TypeError, ValueError):
        return None


def collect(query: str | None, limit: int, category: str | None = None, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    feed = CATEGORY_FEED.format(cat=category) if category else MAIN_FEED
    soup = BeautifulSoup(_fetch(feed, timeout), "xml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []

    for item in soup.find_all("item"):
        raw_title = (item.title.text if item.title else "").strip()
        link = (item.link.text if item.link else "").strip()
        if not raw_title or not link:
            continue
        # WWR titles are "Company: Role"
        if ": " in raw_title:
            company, title = raw_title.split(": ", 1)
        else:
            company, title = None, raw_title
        if needle and needle not in raw_title.lower():
            continue
        slug = _SLUG.search(link)
        region = item.find("region")
        jtype = item.find("type")
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=slug.group(1) if slug else None,
                url=link,
                title=title.strip(),
                company=company.strip() if company else None,
                location=region.text.strip() if region and region.text else None,
                employment_type=jtype.text.strip() if jtype and jtype.text else None,
                posted_at=_iso(item.pubDate.text if item.pubDate else None),
                deadline=None,
                salary=None,
                snippet=None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from We Work Remotely.")
    ap.add_argument("--query", "-q", default=None, help="filter feed by title/company substring")
    ap.add_argument("--category", "-c", default=None,
                    help="category feed slug, e.g. remote-programming-jobs")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.category, args.timeout)
    except Exception as exc:
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings"
          + (f" for query={args.query!r}" if args.query else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

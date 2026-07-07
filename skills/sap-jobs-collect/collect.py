#!/usr/bin/env python3
"""job-seeker :: SAP Jobs collector — self-contained, read-only.

Collects public postings from SAP's SuccessFactors careers board for the Seoul
listing and prints a normalized JSON array (see docs/SCHEMA.md). The Seoul
listing page is server-rendered as an HTML results table, so this is a plain GET
of the public page — no login, no save, no apply. `--query` filters the parsed
rows client-side by title/location substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --limit 20
    python3 collect.py --query "architect"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "sap-jobs"
BASE = "https://jobs.sap.com"
# The Seoul listing (SuccessFactors "go" category page); server-rendered table.
LISTING_URL = BASE + "/go/SAP-Jobs-in-Seoul/944001/"

_REQ_ID = re.compile(r"/(\d+)/?$")  # trailing numeric req id in the job href


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

    soup = BeautifulSoup(_fetch(LISTING_URL, timeout), "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for row in soup.select("tr.data-row"):
        link = row.select_one("span.jobTitle.hidden-phone a.jobTitle-link") \
            or row.select_one("a.jobTitle-link")
        if not link:
            continue
        href = link.get("href", "")
        title = link.get_text(strip=True)
        loc_el = row.select_one("td.colLocation span.jobLocation") \
            or row.select_one("span.jobLocation")
        location = loc_el.get_text(strip=True) if loc_el else None
        m = _REQ_ID.search(href.rstrip("/") + "/")
        req = m.group(1) if m else None
        if req and req in seen:
            continue
        if req:
            seen.add(req)
        if needle and needle not in f"{title} {location or ''}".lower():
            continue
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=req,
                url=(BASE + href) if href.startswith("/") else href,
                title=title,
                company="SAP",
                location=location,
                employment_type=None,
                posted_at=None,
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
    ap = argparse.ArgumentParser(description="Collect public postings from SAP Jobs (Seoul).")
    ap.add_argument("--query", "-q", default=None, help="filter rows by title/location substring")
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

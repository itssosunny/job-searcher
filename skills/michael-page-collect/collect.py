#!/usr/bin/env python3
"""job-searcher :: Michael Page collector — self-contained, read-only.

Attempts to collect public postings from Michael Page's (michaelpage.com) job
search and print a normalized JSON array (see docs/SCHEMA.md). This is a plain,
best-effort GET of the public search page only — no login, no save, no apply.

Michael Page renders its result list client-side (Salesforce/thunderhead), so a
plain fetch returns an empty search shell with no server-rendered postings, and
the origin is slow/flaky (a single request can take 60–120s or time out). When
the listing cannot be enumerated by fetch, this collector says so honestly:
it prints an empty JSON array on stdout and a `needs_browser` note on stderr,
and exits 1. It parses the `/job-detail/<slug>/ref/<id>` pattern if the page
ever serves postings server-side, so it upgrades cleanly without faking data.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "engineering" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "michaelpage"
BASE = "https://www.michaelpage.com"
LISTING_URL = BASE + "/job-search"
# A location filter (e.g. Korea) narrows the search when a query is supplied.
LISTING_URL_Q = BASE + "/job-search?search={q}&location=korea"

# Detail links look like /job-detail/<slug>/ref/<id>
_DETAIL = re.compile(r"/job-detail/[^/?#]+/ref/([^/?#]+)")


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


def _fetch(url: str, timeout: int, tries: int = 3) -> str:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    last: Exception | None = None
    for i in range(tries):
        try:
            resp = creq.get(url, impersonate="safari", timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 — retry slow/flaky origin
            last = exc
            if i < tries - 1:
                time.sleep(2)
    raise last  # type: ignore[misc]


def collect(query: str | None, limit: int, timeout: int = 90) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    url = LISTING_URL_Q.format(q=quote(query)) if query else LISTING_URL
    soup = BeautifulSoup(_fetch(url, timeout), "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for a in soup.select("a[href*='/job-detail/']"):
        href = a.get("href", "")
        m = _DETAIL.search(href)
        if not m:
            continue
        ref = m.group(1)
        if ref in seen:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title:
            continue
        seen.add(ref)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=ref,
                url=BASE + href if href.startswith("/") else href,
                title=title,
                company=None,
                location=None,
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
    ap = argparse.ArgumentParser(description="Collect public postings from Michael Page (best-effort).")
    ap.add_argument("--query", "-q", default=None, help="search keyword (location filter: Korea)")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=90, help="per-request timeout; origin is slow")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.timeout)
    except Exception as exc:  # network / timeout — flaky origin, honest report
        print(json.dumps({
            "source": SOURCE,
            "error": str(exc),
            "needs_browser": True,
            "reason": "fetch failed (slow/flaky origin); listing is JS-rendered — use a real browser",
            "postings": [],
        }), file=sys.stderr)
        print("[]")
        return 1

    data = [asdict(p) for p in postings]
    if not data:
        # Fetched fine, but the result list is populated client-side: nothing to
        # enumerate. Don't fabricate — say a browser is needed.
        print(json.dumps({
            "source": SOURCE,
            "needs_browser": True,
            "reason": "no server-rendered postings; result list is loaded via JS — use a real browser",
            "postings": [],
        }), file=sys.stderr)
        print("[]")
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings"
          + (f" for query={args.query!r}" if args.query else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

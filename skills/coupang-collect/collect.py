#!/usr/bin/env python3
"""job-searcher :: Coupang collector — self-contained, read-only.

Collects current public postings from Coupang's careers board and prints a
normalized JSON array (see docs/SCHEMA.md). Coupang runs a Greenhouse-backed
board, so this reads the published Greenhouse jobs JSON API — a plain GET of a
public endpoint, no login/save/apply. `--query` filters the board client-side
by title/location substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "engineer" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "coupang"
BASE = "https://www.coupang.jobs"
# Coupang's careers board is Greenhouse (board token "coupang").
API_URL = "https://boards-api.greenhouse.io/v1/boards/coupang/jobs"
DETAIL_URL = BASE + "/kr/jobs/{id}/?gh_jid={id}"


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


def _fetch_json(url: str, timeout: int) -> dict:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.get(url, impersonate="safari", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    data = _fetch_json(API_URL, timeout)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []

    for job in data.get("jobs", []):
        title = (job.get("title") or "").strip()
        jid = job.get("id")
        if not title or jid is None:
            continue
        loc = (job.get("location") or {}).get("name")
        if needle and needle not in f"{title} {loc or ''}".lower():
            continue
        first_pub = job.get("first_published")
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=str(jid),
                url=DETAIL_URL.format(id=jid),
                title=title,
                company=job.get("company_name"),
                location=loc,
                employment_type=None,
                posted_at=first_pub[:10] if first_pub else None,
                deadline=job.get("application_deadline"),
                salary=None,
                snippet=None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Coupang.")
    ap.add_argument("--query", "-q", default=None, help="filter by title/location substring")
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

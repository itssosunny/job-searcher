#!/usr/bin/env python3
"""job-searcher :: Wanted collector — self-contained, read-only.

Collects recent public postings from Wanted's (원티드) public jobs JSON API and
prints a normalized JSON array (see docs/SCHEMA.md). The API is the site's own
public listing interface, so this is a plain GET — no login, save, or apply.

Standalone usage:
    pip install curl_cffi
    python3 collect.py --query "데이터 엔지니어" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "wanted"
BASE = "https://www.wanted.co.kr"
# Wanted's own public jobs API. keyword optional; job.latest_order = newest first.
API_URL = (
    BASE + "/api/v4/jobs?country=kr&job_sort=job.latest_order&years=-1"
    "&limit={limit}&keyword={q}"
)


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


def _fetch_json(url: str, timeout: int):
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi")
    resp = creq.get(url, impersonate="safari", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _location(addr: dict | None) -> str | None:
    if not addr:
        return None
    parts = [addr.get("location"), addr.get("district")]
    joined = " ".join(p for p in parts if p)
    return joined or (addr.get("full_location") or None)


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    payload = _fetch_json(API_URL.format(limit=limit, q=quote(query)), timeout)
    rows = payload.get("data") or []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for job in rows:
        jid = job.get("id")
        if jid is None:
            continue
        jid = str(jid)
        if jid in seen:
            continue
        seen.add(jid)
        company = (job.get("company") or {}).get("name")
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=jid,
                url=f"{BASE}/wd/{jid}",
                title=job.get("position") or "",
                company=company,
                location=_location(job.get("address")),
                employment_type=None,       # not exposed by this endpoint
                posted_at=None,             # not exposed by this endpoint
                deadline=job.get("due_time"),
                salary=None,                # 'reward' is a referral bounty, not salary
                snippet=None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Wanted.")
    ap.add_argument("--query", "-q", default="개발자", help="search keyword")
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
    print(f"{SOURCE}: {len(data)} postings for query={args.query!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""job-searcher :: Toss Career collector — self-contained, read-only.

Collects current public postings from Toss's careers board and prints a
normalized JSON array (see docs/SCHEMA.md). The toss.im/career page renders its
list client-side (JS), but the same list is served by Toss's public careers JSON
API, so this is a plain GET of that endpoint — no login, save, or apply.
`--query` filters the list client-side by title/company/location substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "server" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "toss-career"
BASE = "https://toss.im"
# The toss.im/career list is populated client-side from this public careers API.
API_URL = "https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs"

_GH_JID = re.compile(r"gh_jid=(\d+)")


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
    resp = creq.get(url, impersonate="safari", timeout=timeout,
                    headers={"Referer": BASE + "/career"})
    resp.raise_for_status()
    return resp.json()


def _meta(job: dict) -> dict:
    return {m.get("name"): m.get("value") for m in (job.get("metadata") or [])}


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    data = _fetch_json(API_URL, timeout)
    if data.get("resultType") != "SUCCESS":
        raise RuntimeError(f"unexpected API response: {data.get('error') or data.get('resultType')}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []

    for job in data.get("success", []):
        title = (job.get("title") or "").strip()
        url = job.get("absolute_url") or ""
        if not title or not url:
            continue
        loc = (job.get("location") or {}).get("name")
        company = job.get("company_name")
        if needle and needle not in f"{title} {company or ''} {loc or ''}".lower():
            continue
        meta = _meta(job)
        emp = meta.get("Employment_Type")
        category = next((v for k, v in meta.items() if k and "Job Category" in k), None)
        m = _GH_JID.search(url)
        first_pub = job.get("first_published")
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=m.group(1) if m else (str(job["id"]) if job.get("id") is not None else None),
                url=url,
                title=title,
                company=company,
                location=loc,
                employment_type=emp,
                posted_at=first_pub[:10] if first_pub else None,
                deadline=job.get("application_deadline"),
                salary=None,
                snippet=category,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Toss Career.")
    ap.add_argument("--query", "-q", default=None, help="filter by title/company/location substring")
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

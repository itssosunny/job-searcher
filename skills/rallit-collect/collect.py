#!/usr/bin/env python3
"""job-seeker :: Rallit collector — self-contained, read-only.

Collects recent public postings from Rallit's (랠릿) public position JSON API and
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

SOURCE = "rallit"
BASE = "https://www.rallit.com"
# Rallit's own public position API. pageNumber is 1-based.
API_URL = BASE + "/api/v1/position?keyword={q}&pageNumber=1&pageSize={size}"

# Sentinel dates the API uses to mean "no bound / always open" — not real dates.
_SENTINELS = {"1970-01-01", "9999-12-31"}


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


def _date(val: str | None) -> str | None:
    if not val or val in _SENTINELS:
        return None
    return val


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    size = max(1, min(limit, 100))
    payload = _fetch_json(API_URL.format(q=quote(query), size=size), timeout)
    data = payload.get("data") or {}
    rows = data.get("items") or []
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
        skills = [s.strip() for s in (job.get("jobSkillKeywords") or []) if s and s.strip()]
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=jid,
                url=job.get("url") or f"{BASE}/positions/{jid}",
                title=job.get("title") or "",
                company=job.get("companyName"),
                location=job.get("addressRegion"),
                employment_type=None,               # not exposed (status is hiring-state)
                posted_at=_date(job.get("startedAt")),
                deadline=_date(job.get("endedAt")),
                salary=None,                        # 'joinReward' is a referral bounty, not salary
                snippet=", ".join(skills) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Rallit.")
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

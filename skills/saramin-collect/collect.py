#!/usr/bin/env python3
"""job-seeker :: Saramin collector — self-contained, read-only.

Collects recent public postings from Saramin's (사람인) keyword search and prints
a normalized JSON array (see docs/SCHEMA.md). No login, no save, no apply — a
plain GET of the public search page only.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "데이터 엔지니어" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "saramin"
BASE = "https://www.saramin.co.kr"
SEARCH_URL = BASE + "/zf_user/search/recruit?searchword={q}&recruitSort=relation"

_REC = re.compile(r"rec_idx=(\d+)")


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


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    html = _fetch(SEARCH_URL.format(q=quote(query)), timeout)
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("div.item_recruit"):
        tit = card.select_one(".area_job .job_tit a") or card.select_one(".job_tit a")
        if not tit:
            continue
        m = _REC.search(tit.get("href", ""))
        rec = m.group(1) if m else None
        if not rec or rec in seen:
            continue
        seen.add(rec)
        corp = card.select_one(".area_corp .corp_name a") or card.select_one(".corp_name a")
        conds = [s.get_text(strip=True) for s in card.select(".job_condition span") if s.get_text(strip=True)]
        date = card.select_one(".job_date .date")
        sectors = [s.get_text(strip=True) for s in card.select(".job_sector a")]
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=rec,
                url=f"{BASE}/zf_user/jobs/relay/view?rec_idx={rec}",
                title=(tit.get("title") or tit.get_text(strip=True)),
                company=corp.get_text(strip=True) if corp else None,
                location=conds[0] if conds else None,
                employment_type=conds[-1] if conds else None,
                posted_at=None,
                deadline=date.get_text(strip=True) if date else None,
                salary=None,
                snippet=", ".join(sectors[:5]) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Saramin.")
    ap.add_argument("--query", "-q", default="개발자", help="search keyword")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.timeout)
    except Exception as exc:
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings for query={args.query!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

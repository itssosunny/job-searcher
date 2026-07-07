#!/usr/bin/env python3
"""job-seeker :: CJ Careers collector — self-contained, read-only.

Collects current public postings from CJ's recruit portal and prints a
normalized JSON array (see docs/SCHEMA.md). CJ's root is a frameset; the
server-rendered listing lives in the main frame `/recruit/ko/main/main/main.fo`,
so this is a plain GET of that public frame only. No login, save, or apply.

`--query` filters the returned postings client-side by title/company substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "ENM" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "cj-recruit"
BASE = "https://recruit.cj.net"
# CJ's root is a frameset; the listing is server-rendered in the main frame.
LIST_URL = BASE + "/recruit/ko/main/main/main.fo"
DETAIL_URL = BASE + "/recruit/ko/recruit/recruit/bestDetail.fo?zz_jo_num={id}"

_JO_NUM = re.compile(r"zz_jo_num=([A-Za-z0-9]+)")


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

    for a in soup.select("a.btn-filter[href*='bestDetail']"):
        m = _JO_NUM.search(a.get("href", ""))
        if not m:
            continue
        jo = m.group(1)
        if jo in seen:
            continue
        tit = a.select_one("p.tit")
        title = tit.get_text(strip=True) if tit else None
        if not title:
            continue
        seen.add(jo)
        comp = a.select_one("span.company")
        jtype = a.select_one("span.type")   # 경력 / 신입 (as shown)
        badge = a.select_one("span.badge")  # e.g. 상시 (rolling)
        period = a.select_one("p.period")   # e.g. "2026.07.07 ~ 채용시까지"
        company = comp.get_text(strip=True) if comp else None
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        tags = [t.get_text(strip=True) for t in (badge, jtype) if t and t.get_text(strip=True)]
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=jo,
                url=DETAIL_URL.format(id=jo),
                title=title,
                company=company,
                location=None,
                employment_type=None,
                posted_at=None,
                deadline=period.get_text(" ", strip=True) if period else None,
                salary=None,
                snippet=", ".join(tags) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from CJ Careers.")
    ap.add_argument("--query", "-q", default=None, help="filter by title/company substring")
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

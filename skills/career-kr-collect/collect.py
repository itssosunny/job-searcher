#!/usr/bin/env python3
"""job-searcher :: Career.co.kr collector — self-contained, read-only.

Collects recent public postings from Career.co.kr's public jobs listing and
prints a normalized JSON array (see docs/SCHEMA.md). No login, no save, no apply
— a plain GET of the public `/jobs/` listing only. The listing does not accept a
GET keyword, so `--query` filters the fetched listing client-side by
title/company substring (like the WeWorkRemotely feed collector).

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "개발자" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "career"
BASE = "https://job.career.co.kr"
LIST_URL = BASE + "/jobs/"

_VIEW = re.compile(r"/recruit/view/(\d+)")
_EMP = re.compile(r"(정규직|계약직|인턴|파견직|프리랜서|병역특례|위촉직|아르바이트|일용직|파트타임|무기계약직)")
_REGION = re.compile(
    r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주|전국)"
    r"(?:\s?[가-힣]+[시군구])?|전\s?지역"
)
_DEADLINE = re.compile(r"(D-\d+|오늘마감|내일마감|채용시|상시|수시|~\s?\d{1,2}[./]\d{1,2})")


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

    rows = [tr for tr in soup.select("tbody tr") if tr.select_one("a[href*='/recruit/view/']")]
    for row in rows:
        link = row.select_one("a[href*='/recruit/view/']")
        m = _VIEW.search(link.get("href", ""))
        rec = m.group(1) if m else None
        title = link.get_text(strip=True)
        if not rec or not title or rec in seen:
            continue
        cells = [c.get_text(" ", strip=True) for c in row.select("td")]
        # td layout: [company, title(+#sectors), career/edu, type+region, deadline+posted]
        company = cells[0] if cells else None
        detail = cells[3] if len(cells) > 3 else ""
        tail = cells[-1] if cells else ""
        sectors = re.findall(r"#[^\s#]+", cells[1]) if len(cells) > 1 else []
        emp = _EMP.search(detail) or _EMP.search(" ".join(cells))
        loc = _REGION.search(detail) or _REGION.search(" ".join(cells))
        dl = _DEADLINE.search(tail)
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        seen.add(rec)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=rec,
                url=f"{BASE}/recruit/view/{rec}",
                title=title,
                company=company or None,
                location=loc.group(0) if loc else None,
                employment_type=emp.group(0) if emp else None,
                posted_at=None,
                deadline=dl.group(0) if dl else None,
                salary=None,
                snippet=", ".join(sectors[:5]) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Career.co.kr.")
    ap.add_argument("--query", "-q", default=None,
                    help="filter the listing by title/company substring (client-side)")
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

#!/usr/bin/env python3
"""job-searcher :: JobKorea collector — self-contained, read-only.

Collects recent public postings from JobKorea's keyword search page and prints
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

SOURCE = "jobkorea"
BASE = "https://www.jobkorea.co.kr"
SEARCH_URL = BASE + "/Search/?stext={q}"

_GNO = re.compile(r"GI_Read/(\d+)")
_REGION = re.compile(
    r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"(?:\s?[가-힣]+[시군구])?"
)
_SALARY = re.compile(r"연봉\s?[\d,]+\s?~?\s?[\d,]*\s?만원|회사내규|면접\s?후\s?결정")
_DEADLINE = re.compile(r"(D-\d+|오늘마감|내일마감|~\s?\d{1,2}[./]\d{1,2}|상시)")


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

    for card in soup.select("div.shadow-list"):
        anchors = card.select("a[href*='GI_Read']")
        gno = None
        for a in anchors:
            m = _GNO.search(a.get("href", ""))
            if m:
                gno = m.group(1)
                break
        if not gno or gno in seen:
            continue
        named = [a.get_text(strip=True) for a in anchors if a.get_text(strip=True)]
        if not named:
            continue
        seen.add(gno)
        title = named[0]
        company = named[1] if len(named) > 1 else None
        meta = card.get_text(" ", strip=True)
        loc = _REGION.search(meta)
        sal = _SALARY.search(meta)
        dl = _DEADLINE.search(meta)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=gno,
                url=f"{BASE}/Recruit/GI_Read/{gno}",
                title=title,
                company=company,
                location=loc.group(0) if loc else None,
                employment_type=None,
                posted_at=None,
                deadline=dl.group(0) if dl else None,
                salary=sal.group(0) if sal else None,
                snippet=meta[:200] or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from JobKorea.")
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

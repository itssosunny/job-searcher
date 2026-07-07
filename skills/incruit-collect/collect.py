#!/usr/bin/env python3
"""job-seeker :: Incruit collector — self-contained, read-only.

Collects recent public postings from Incruit's (인크루트) keyword search and
prints a normalized JSON array (see docs/SCHEMA.md). No login, no save, no apply
— a plain GET of the public search page only.

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

SOURCE = "incruit"
BASE = "https://www.incruit.com"
JOB_HOST = "https://job.incruit.com"
SEARCH_URL = "https://search.incruit.com/list/search.asp?col=job&kw={q}"

_JOB = re.compile(r"jobpost\.asp\?job=(\d+)")
_REGION = re.compile(
    r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"(?:\s?[가-힣]+[시군구])?"
)
_EMP = re.compile(r"(정규직|계약직|인턴|파견직|프리랜서|병역특례|위촉직|아르바이트|일용직|파트타임)")
_SALARY = re.compile(r"연봉\s?[\d,]+\s?~?\s?[\d,]*\s?만원|회사내규|면접\s?후\s?결정")
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
    # Incruit serves EUC-KR/CP949; decode from raw bytes, not resp.text.
    return resp.content.decode("cp949", errors="replace")


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    html = _fetch(SEARCH_URL.format(q=quote(query)), timeout)
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for row in soup.select("ul.c_row"):
        tit = row.select_one("a[href*='jobpost.asp?job=']")
        if not tit:
            continue
        m = _JOB.search(tit.get("href", ""))
        job_id = m.group(1) if m else None
        title = tit.get_text(strip=True)
        if not job_id or not title or job_id in seen:
            continue
        seen.add(job_id)
        corp = row.select_one("a.cpname")
        meta = row.get_text(" ", strip=True)
        loc = _REGION.search(meta)
        emp = _EMP.search(meta)
        sal = _SALARY.search(meta)
        dl = _DEADLINE.search(meta)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=job_id,
                url=f"{JOB_HOST}/jobdb_info/jobpost.asp?job={job_id}",
                title=title,
                company=corp.get_text(strip=True) if corp else None,
                location=loc.group(0) if loc else None,
                employment_type=emp.group(0) if emp else None,
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
    ap = argparse.ArgumentParser(description="Collect public postings from Incruit.")
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

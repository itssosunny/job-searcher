#!/usr/bin/env python3
"""job-searcher :: Incruit collector — self-contained, read-only.

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
    deadline_date: str | None
    status: str
    salary: str | None
    snippet: str | None
    collected_at: str


# --- deadline -> (deadline_date, status) : job-searcher shared rule (F1 inline) ---
# Copy verbatim into each collect.py; keep byte-identical across skills.
import re as _re
from datetime import date as _date, datetime as _dt, timedelta as _td

_JS_ISO = _re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
_JS_RFC = _re.compile(r"(\d{1,2})\s+([A-Za-z]{3})\s+(20\d{2})")
_JS_MD  = _re.compile(r"~?\s*(\d{1,2})[./](\d{1,2})")
_JS_DN  = _re.compile(r"D-\s*(\d+)", _re.I)
_JS_ROLL= _re.compile(r"상시|수시|채용시|공고시|open\s*until\s*filled|always", _re.I)
_JS_TDY = _re.compile(r"오늘\s*마감|today", _re.I)
_JS_TMR = _re.compile(r"내일\s*마감", _re.I)


def _derive_status(deadline_raw, collected_at):
    """(deadline_date_iso|None, status). Pure; collected_at ISO string is 'today'.
    For a `start ~ end` range the LAST concrete date (the close) is used; a rolling
    marker to the right of the last date (or with no date) means open-ended."""
    try:
        today = _dt.fromisoformat(str(collected_at).replace("Z", "+00:00")).date()
    except Exception:
        today = _date.today()
    if not deadline_raw:
        return None, "unknown"
    s = str(deadline_raw).strip()
    dl = None; pos = -1
    for m in _JS_ISO.finditer(s):
        try:
            d = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if m.end() > pos: dl, pos = d, m.end()
        except ValueError: pass
    if dl is None:
        m = _JS_RFC.search(s)
        if m:
            try: dl, pos = _dt.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").date(), m.end()
            except ValueError: pass
    if dl is None:
        m = _JS_DN.search(s)
        if m: dl, pos = today + _td(days=int(m.group(1))), m.end()
    if dl is None:
        m = _JS_TMR.search(s)
        if m: dl, pos = today + _td(days=1), m.end()
    if dl is None:
        m = _JS_TDY.search(s)
        if m: dl, pos = today, m.end()
    if dl is None:
        for m in _JS_MD.finditer(s):
            try:
                cand = _date(today.year, int(m.group(1)), int(m.group(2)))
                if cand < today - _td(days=1): cand = _date(today.year + 1, int(m.group(1)), int(m.group(2)))
                if m.end() > pos: dl, pos = cand, m.end()
            except ValueError: pass
    roll = _JS_ROLL.search(s)
    if roll and (dl is None or roll.start() > pos):
        return None, "rolling"
    if dl is None:
        return None, "unknown"
    days = (dl - today).days
    status = "closed" if days < 0 else ("closing_soon" if days <= 3 else "open")
    return dl.isoformat(), status


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
        _dl = dl.group(0) if dl else None
        _dd, _st = _derive_status(_dl, now)
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
                deadline=_dl,
                deadline_date=_dd,
                status=_st,
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

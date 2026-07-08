#!/usr/bin/env python3
"""job-searcher :: WorldJobPlus collector — self-contained, read-only.

Collects public overseas-job postings from WorldJobPlus (월드잡플러스), the Korea
HRD (한국산업인력공단) overseas-employment portal, and prints a normalized JSON
array (see docs/SCHEMA.md). The listing endpoint is server-rendered, so this is a
plain GET/POST of the public list page — no login, no save, no apply. `--query`
and `--location` filter the parsed rows client-side (title/employer, country).

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --limit 20
    python3 collect.py --query "engineer" --location 일본
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "worldjobplus"
BASE = "https://www.worldjob.or.kr"
LIST_URL = BASE + "/advnc/cnttNewList.do"
PAGE_SIZE = 50  # showItemListCount supports 10/20/30/50

_GOVIEW = re.compile(r"goView1?\('(E\d+)'")


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


def _fetch(page: int, timeout: int) -> str:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.post(
        LIST_URL,
        data={"showItemListCount": str(PAGE_SIZE), "pageIndex": str(page)},
        impersonate="safari",
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip() or None


def _parse(html: str, now: str):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for box in soup.select("div.post-box"):
        title_a = box.select_one("h5.mb4 a")
        if not title_a:
            continue
        m = _GOVIEW.search(title_a.get("href", ""))
        eid = m.group(1) if m else None
        title = _clean(title_a.get_text(" ", strip=True))
        emp_a = box.select_one("p.mb8 a")
        employer = _clean(emp_a.get_text(" ", strip=True)) if emp_a else None
        nation_img = box.select_one(".nation-box img")
        country = None
        if nation_img and nation_img.get("alt"):
            country = nation_img["alt"].replace("국기", "").strip() or None
        day = box.select_one(".day-box")
        deadline = _clean(day.get_text(" ", strip=True)) if day else None

        conds = [_clean(p.get_text(" ", strip=True))
                 for p in box.select(".post-condition-box p")]
        conds = [c for c in conds if c]
        salary = next((c for c in conds if "연봉" in c or "만원" in c or "시급" in c), None)
        etype = next((re.sub(r"[\[\]]", "", c).strip()
                      for c in conds if c.startswith("[")), None)
        details = [_clean(li.get_text(" ", strip=True))
                   for li in box.select(".post-info-box ul li")]
        details = [d for d in details if d]
        extras = [c for c in conds if c not in (salary, f"[ {etype} ]") and not c.startswith("[")]
        snippet = ", ".join(details + extras) or None

        _dd, _st = _derive_status(deadline, now)
        yield JobPosting(
            source=SOURCE,
            external_id=eid,
            url=LIST_URL,  # detail is a JS popup with no plain-GET URL; id is in external_id
            title=title or "",
            company=employer,
            location=country,
            employment_type=etype,
            posted_at=None,
            deadline=deadline,
            deadline_date=_dd,
            status=_st,
            salary=salary,
            snippet=snippet,
            collected_at=now,
        )


def collect(query: str | None, limit: int, location: str | None = None,
            timeout: int = 25) -> list[JobPosting]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    q = query.lower() if query else None
    loc = location.lower() if location else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    page = 1
    empty_streak = 0
    while len(out) < limit and page <= 40:
        rows = list(_parse(_fetch(page, timeout), now))
        if not rows:
            empty_streak += 1
            if empty_streak >= 1:
                break
        for p in rows:
            key = p.external_id or p.title
            if key in seen:
                continue
            seen.add(key)
            if q and q not in f"{p.title} {p.company or ''}".lower():
                continue
            if loc and loc not in (p.location or "").lower():
                continue
            out.append(p)
            if len(out) >= limit:
                break
        page += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from WorldJobPlus.")
    ap.add_argument("--query", "-q", default=None, help="filter rows by title/employer substring")
    ap.add_argument("--location", "-l", default=None, help="filter rows by country substring (e.g. 일본)")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.location, args.timeout)
    except Exception as exc:  # network / parse failure — honest, no fabrication
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings"
          + (f" for query={args.query!r}" if args.query else "")
          + (f" location={args.location!r}" if args.location else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

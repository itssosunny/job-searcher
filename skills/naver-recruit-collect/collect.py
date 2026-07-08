#!/usr/bin/env python3
"""job-searcher :: NAVER Careers collector — self-contained, read-only.

Collects current public postings from NAVER Careers (recruit.navercorp.com) and
prints a normalized JSON array (see docs/SCHEMA.md). The public listing page
(`/rcrt/list.do`) renders its cards client-side from a JSON endpoint
(`/rcrt/loadJobList.do`); this collector calls that same public endpoint with a
plain GET — no login, save, or apply.

The endpoint's `sw` (search word) parameter is a real server-side filter, so
`--query` narrows results at the source.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "AI" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "naver"
BASE = "https://recruit.navercorp.com"
LIST_PAGE = BASE + "/rcrt/list.do"
# JSON endpoint the list page's drawJobList() consumes; `sw` = search word.
API_URL = BASE + "/rcrt/loadJobList.do?sw={q}&firstIndex={start}"
VIEW_URL = BASE + "/rcrt/view.do?annoId={anno}"


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


def _fetch_json(url: str, timeout: int) -> dict:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.get(
        url,
        impersonate="safari",
        timeout=timeout,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": LIST_PAGE},
    )
    resp.raise_for_status()
    return resp.json()


def _iso_ymd(ymd: str | None) -> str | None:
    """`20260713` -> `2026-07-13`; anything else -> the raw value or None."""
    if not ymd:
        return None
    d = str(ymd).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return d or None


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sw = quote(query) if query else ""
    out: list[JobPosting] = []
    seen: set[str] = set()
    start = 0
    # The endpoint pages via firstIndex; loop until we have `limit`, the source
    # is exhausted, or a safety cap trips.
    for _ in range(50):
        data = _fetch_json(API_URL.format(q=sw, start=start), timeout)
        rows = data.get("list") or []
        if not rows:
            break
        total = data.get("totalSize")
        for r in rows:
            anno = r.get("annoId")
            if anno is None:
                continue
            anno = str(anno)
            if anno in seen:
                continue
            seen.add(anno)
            tags = [
                r.get("classCdNm"),
                r.get("subJobCdNm"),
                r.get("entTypeCdNm"),
                r.get("reqTypeCdNm"),
            ]
            snippet = ", ".join(t for t in tags if t) or None
            dl_text = _iso_ymd(r.get("endYmd"))
            dd, st = _derive_status(dl_text, now)
            out.append(
                JobPosting(
                    source=SOURCE,
                    external_id=anno,
                    url=r.get("jobDetailLink") or VIEW_URL.format(anno=anno),
                    title=(r.get("annoSubject") or "").strip(),
                    company=r.get("sysCompanyCdNm") or None,
                    location=None,  # only a workAreaCd code is exposed, no label
                    employment_type=r.get("empTypeCdNm") or None,
                    posted_at=_iso_ymd(r.get("staYmd")),
                    deadline=dl_text,
                    deadline_date=dd,
                    status=st,
                    salary=None,
                    snippet=snippet,
                    collected_at=now,
                )
            )
            if len(out) >= limit:
                return out
        start += len(rows)
        if isinstance(total, int) and start >= total:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from NAVER Careers.")
    ap.add_argument("--query", "-q", default=None,
                    help="server-side search word (`sw`); default lists all open postings")
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

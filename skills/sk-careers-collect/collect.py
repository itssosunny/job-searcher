#!/usr/bin/env python3
"""job-searcher :: SK Careers collector — self-contained, read-only.

Collects current public postings from SK Careers (skcareers.com) and prints a
normalized JSON array (see docs/SCHEMA.md). The public recruit page (`/Recruit`)
renders its cards client-side from a JSON endpoint (`POST /Recruit/GetRecruitList`);
this collector calls that same public endpoint with empty filters — no login,
save, or apply.

The endpoint's `searchText` parameter is a real server-side filter, so `--query`
narrows results at the source (the value is percent-encoded to mirror the site's
own `encodeURIComponent` call).

Note: this endpoint is rate-sensitive. When the source is throttling it returns
an HTML 404 error page instead of JSON; the collector retries a few times with
backoff and, if still blocked, reports an honest error rather than fabricating.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --limit 20
    python3 collect.py --query "반도체" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "sk"
BASE = "https://www.skcareers.com"
RECRUIT_PAGE = BASE + "/Recruit"
API_URL = BASE + "/Recruit/GetRecruitList"
DETAIL_URL = BASE + "/Recruit/Detail/{id}"

# The seven form fields the site's own script posts; all empty = list everything.
_EMPTY_PARAMS = {
    "sort": "", "searchText": "", "corpCode": "", "jobRole": "",
    "recruitType": "", "workingType": "", "workingRegion": "",
}
_AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": RECRUIT_PAGE,
    "Origin": BASE,
}


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


def _fetch_list(query: str | None, timeout: int, attempts: int = 4) -> dict:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")

    params = dict(_EMPTY_PARAMS)
    if query:
        # mirror the site's encodeURIComponent(searchText) before form-encoding
        params["searchText"] = quote(query)

    last = ""
    for i in range(attempts):
        sess = creq.Session(impersonate="safari")
        sess.get(RECRUIT_PAGE, timeout=timeout)  # warm cookies (_culture etc.)
        resp = sess.post(API_URL, data=params, headers=_AJAX_HEADERS, timeout=timeout)
        ctype = resp.headers.get("content-type") or ""
        if resp.status_code == 200 and "json" in ctype:
            return resp.json()
        last = f"HTTP {resp.status_code} ({ctype or 'no content-type'})"
        if i < attempts - 1:
            time.sleep(2 * (i + 1))
    raise RuntimeError(
        f"GetRecruitList did not return JSON after {attempts} tries "
        f"(last: {last}); the source is likely rate-limiting this endpoint."
    )


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    data = _fetch_list(query, timeout)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for r in (data.get("list") or []):
        nid = r.get("noticeID")
        if nid is None:
            continue
        nid = str(nid)
        if nid in seen:
            continue
        seen.add(nid)
        remain = r.get("remainDay")
        deadline = f"D-{remain}" if isinstance(remain, int) else None
        tags = [r.get("jobRole"), r.get("recruitType")]
        snippet = ", ".join(t for t in tags if t) or None
        _dd, _st = _derive_status(deadline, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=nid,
                url=DETAIL_URL.format(id=nid),
                title=(r.get("title") or "").strip(),
                company=r.get("corpName") or None,
                location=r.get("workingArea") or None,
                employment_type=r.get("workingType") or None,
                posted_at=None,
                deadline=deadline,
                deadline_date=_dd,
                status=_st,
                salary=None,
                snippet=snippet,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from SK Careers.")
    ap.add_argument("--query", "-q", default=None,
                    help="server-side search word (`searchText`); default lists all open postings")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.timeout)
    except Exception as exc:  # network / parse / throttle — honest, no fabrication
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings"
          + (f" for query={args.query!r}" if args.query else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

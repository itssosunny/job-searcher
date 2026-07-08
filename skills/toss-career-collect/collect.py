#!/usr/bin/env python3
"""job-searcher :: Toss Career collector — self-contained, read-only.

Collects current public postings from Toss's careers board and prints a
normalized JSON array (see docs/SCHEMA.md). The toss.im/career page renders its
list client-side (JS), but the same list is served by Toss's public careers JSON
API, so this is a plain GET of that endpoint — no login, save, or apply.
`--query` filters the list client-side by title/company/location substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "server" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "toss-career"
BASE = "https://toss.im"
# The toss.im/career list is populated client-side from this public careers API.
API_URL = "https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs"

_GH_JID = re.compile(r"gh_jid=(\d+)")


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
    resp = creq.get(url, impersonate="safari", timeout=timeout,
                    headers={"Referer": BASE + "/career"})
    resp.raise_for_status()
    return resp.json()


def _meta(job: dict) -> dict:
    return {m.get("name"): m.get("value") for m in (job.get("metadata") or [])}


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    data = _fetch_json(API_URL, timeout)
    if data.get("resultType") != "SUCCESS":
        raise RuntimeError(f"unexpected API response: {data.get('error') or data.get('resultType')}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []

    for job in data.get("success", []):
        title = (job.get("title") or "").strip()
        url = job.get("absolute_url") or ""
        if not title or not url:
            continue
        loc = (job.get("location") or {}).get("name")
        company = job.get("company_name")
        if needle and needle not in f"{title} {company or ''} {loc or ''}".lower():
            continue
        meta = _meta(job)
        emp = meta.get("Employment_Type")
        category = next((v for k, v in meta.items() if k and "Job Category" in k), None)
        m = _GH_JID.search(url)
        first_pub = job.get("first_published")
        _dl = job.get("application_deadline")
        _dd, _st = _derive_status(_dl, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=m.group(1) if m else (str(job["id"]) if job.get("id") is not None else None),
                url=url,
                title=title,
                company=company,
                location=loc,
                employment_type=emp,
                posted_at=first_pub[:10] if first_pub else None,
                deadline=_dl,
                deadline_date=_dd,
                status=_st,
                salary=None,
                snippet=category,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Toss Career.")
    ap.add_argument("--query", "-q", default=None, help="filter by title/company/location substring")
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

#!/usr/bin/env python3
"""job-searcher :: Daijob collector — self-contained, read-only.

Collects recent public postings from Daijob's (daijob.com) English job search —
bilingual jobs in Japan — and prints a normalized JSON array (see
docs/SCHEMA.md). The search-result listing is server-rendered, so this is a
plain GET of the public search page only. No login, no save, no apply.
`--query` maps to Daijob's free-word search (`kw`).

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "engineer" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "daijob"
BASE = "https://www.daijob.com"
# `kw` is the free-word search param; `in_japan=true` scopes to jobs in Japan.
SEARCH_URL = BASE + "/en/jobs/search?in_japan=true&pg=0"
SEARCH_URL_Q = BASE + "/en/jobs/search?kw={q}&in_japan=true&pg=0"

_DETAIL = re.compile(r"/en/jobs/detail/(\d+)")


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
    return resp.text


def _dd_for(card, label: str) -> str | None:
    """Return the text of the <dd> whose preceding <dt> matches `label`."""
    for dt in card.select("dl dt"):
        if dt.get_text(" ", strip=True).lower().startswith(label.lower()):
            dd = dt.find_next_sibling("dd")
            if dd:
                txt = " ".join(dd.get_text(" ", strip=True).split())
                return txt or None
    return None


def collect(query: str | None, limit: int, timeout: int = 30) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    url = SEARCH_URL_Q.format(q=quote(query)) if query else SEARCH_URL
    soup = BeautifulSoup(_fetch(url, timeout), "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("article.job-card"):
        tit = card.select_one("h2.job-card__title a")
        if not tit:
            continue
        m = _DETAIL.search(tit.get("href", ""))
        rec = m.group(1) if m else None
        if not rec or rec in seen:
            continue
        seen.add(rec)

        # company: the header link that is not the title (also a /detail/ anchor)
        comp = card.select_one(".job-card__header-info a[href*='/en/jobs/detail/']")
        desc = _dd_for(card, "Job Description")
        _dd, _st = _derive_status(None, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=rec,
                url=f"{BASE}/en/jobs/detail/{rec}",
                title=" ".join(tit.get_text(" ", strip=True).split()),
                company=comp.get_text(" ", strip=True) if comp else None,
                location=_dd_for(card, "Location"),
                employment_type=None,
                posted_at=None,
                deadline=None,
                deadline_date=_dd,
                status=_st,
                salary=_dd_for(card, "Salary"),
                snippet=desc[:200] if desc else None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Daijob.")
    ap.add_argument("--query", "-q", default=None, help="free-word search keyword (Daijob 'kw')")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=30)
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

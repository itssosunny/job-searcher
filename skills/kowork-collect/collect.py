#!/usr/bin/env python3
"""job-searcher :: KOWORK collector — self-contained, read-only.

Collects recent public postings from KOWORK's (kowork.kr) English jobs-for-
foreigners listing and prints a normalized JSON array (see docs/SCHEMA.md). No
login, no save, no apply — a plain GET of the public `/en` listing only. The
listing is server-rendered but only the first page (~15 postings) is in the
static HTML; more requires a browser (infinite scroll). The listing does not
accept a GET keyword, so `--query` filters client-side by title/company
substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "developer" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "kowork"
BASE = "https://kowork.kr"
LIST_URL = BASE + "/en"

_POST = re.compile(r"/en/post/(\d+)")
_LOGO_ALT = re.compile(r"job-list-(.*?)-logo")
_DEADLINE = re.compile(r"(D-\d+|D-DAY|Always|Closed|마감)", re.IGNORECASE)
_EMP = re.compile(r"(Full[\s-]?Time|Part[\s-]?Time|Contract|Intern(?:ship)?|Freelance|Temporary)", re.IGNORECASE)


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


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    html = _fetch(LIST_URL, timeout)
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("a[href*='/en/post/']"):
        m = _POST.search(card.get("href", ""))
        post_id = m.group(1) if m else None
        if not post_id or post_id in seen:
            continue
        tit = card.select_one("p.line-clamp-2") or card.find("p")
        title = tit.get_text(strip=True) if tit else ""
        if not title:
            continue
        img = card.find("img")
        company = None
        if img and img.get("alt"):
            am = _LOGO_ALT.search(img["alt"])
            if am:
                company = am.group(1).strip() or None
        # Metadata pills (visa / location / type / category) appear twice
        # (desktop + mobile blocks); dedup on text, keep first-seen order.
        tags: list[str] = []
        for p in card.select("p[class*='rounded']"):
            t = p.get_text(strip=True)
            if t and t not in tags:
                tags.append(t)
        emp = next((t for t in tags if _EMP.fullmatch(t) or _EMP.match(t)), None)
        loc = next((t for t in tags if "," in t), None)
        dl = _DEADLINE.search(card.get_text(" ", strip=True))
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        seen.add(post_id)
        _dl = dl.group(0) if dl else None
        _dd, _st = _derive_status(_dl, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=post_id,
                url=f"{BASE}/en/post/{post_id}",
                title=title,
                company=company,
                location=loc,
                employment_type=emp,
                posted_at=None,
                deadline=_dl,
                deadline_date=_dd,
                status=_st,
                salary=None,
                snippet=", ".join(tags) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from KOWORK (jobs for foreigners in Korea).")
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

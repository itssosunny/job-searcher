#!/usr/bin/env python3
"""job-searcher :: Japan Dev collector — self-contained, read-only.

Collects recent public postings from Japan Dev's (japan-dev.com) job listing —
IT jobs in Japan for English speakers — and prints a normalized JSON array (see
docs/SCHEMA.md). The listing is server-rendered, so this is a plain GET of the
public `/jobs` page only. No login, no save, no apply. `--query` filters the
listing client-side by title/company substring.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "backend" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "japandev"
BASE = "https://japan-dev.com"
LISTING_URL = BASE + "/jobs"

_SLUG = re.compile(r"/jobs/[^/?#]+/([^/?#]+)")
_WS = re.compile(r"\s+")


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


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    t = _WS.sub(" ", text).strip()
    return t or None


def collect(query: str | None, limit: int, timeout: int = 30) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_fetch(LISTING_URL, timeout), "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("li.job-item"):
        a = card.select_one("a.job-item__title")
        if not a:
            continue
        href = a.get("href", "")
        m = _SLUG.search(href)
        slug = m.group(1) if m else None
        if not slug or slug in seen:
            continue
        title = _clean(a.get_text(" ", strip=True))
        if not title:
            continue

        # company: the logo alt is the clean display name; fall back to the
        # /companies/<slug> link or the contract-type label.
        logo = card.select_one("img.company-logo__inner")
        company = _clean(logo.get("alt")) if logo else None
        if not company:
            clink = card.select_one("a[href^='/companies/']")
            if clink and clink.get("href"):
                company = clink["href"].rsplit("/", 1)[-1].replace("-", " ").title() or None

        # location / salary come from icon-labelled tag rows
        location = None
        for tag in card.select(".job-tags .job__tag"):
            icon = tag.select_one("img.job__tag-icon")
            desc = tag.select_one(".job__tag-desc")
            if not desc:
                continue
            alt = (icon.get("alt") or "").lower() if icon else ""
            if "location" in alt and location is None:
                location = _clean(desc.get_text(" ", strip=True))

        # top tags carry salary (¥…), remote status, and other badges
        toptags = [_clean(t.get_text(" ", strip=True)) for t in card.select(".job-top-tag-list__job-top-tag")]
        toptags = [t for t in toptags if t]
        salary = next((t for t in toptags if "¥" in t), None)
        employment_type = next((t for t in toptags if "remote" in t.lower() or "onsite" in t.lower()), None)

        techs = [_clean(t.get_text(" ", strip=True)) for t in card.select(".technology-list li")]
        techs = [t for t in techs if t]
        badges = [t for t in toptags if t not in (salary, employment_type)]
        snippet = ", ".join(badges + techs)[:200] or None

        seen.add(slug)
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        _dd, _st = _derive_status(None, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=slug,
                url=BASE + href if href.startswith("/") else href,
                title=title,
                company=company,
                location=location,
                employment_type=employment_type,
                posted_at=None,
                deadline=None,
                deadline_date=_dd,
                status=_st,
                salary=salary,
                snippet=snippet,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Japan Dev.")
    ap.add_argument("--query", "-q", default=None, help="filter listing by title/company substring")
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

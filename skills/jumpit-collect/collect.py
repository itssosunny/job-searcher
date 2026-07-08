#!/usr/bin/env python3
"""job-searcher :: Jumpit collector — self-contained, read-only.

Collects recent public postings from Jumpit's (점핏) public positions API and
prints a normalized JSON array (see docs/SCHEMA.md). The API is the site's own
public listing interface (returns XML), so this is a plain GET — no login, save,
or apply.

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

SOURCE = "jumpit"
BASE = "https://jumpit.saramin.co.kr"
# Jumpit's own public positions API (returns XML). sort=reg_dt = newest first.
API_URL = "https://jumpit-api.saramin.co.kr/api/positions?sort=reg_dt&highlight=false&keyword={q}"

_SPAN = re.compile(r"</?span[^>]*>")


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


def _texts(parent, tag: str) -> list[str]:
    # A wrapper tag (e.g. <locations>) holds one same-named child per value;
    # collect the text of its direct children.
    block = parent.find(tag, recursive=False)
    if not block:
        return []
    return [c.get_text(strip=True) for c in block.find_all(True, recursive=False)
            if c.get_text(strip=True)]


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    xml = _fetch(API_URL.format(q=quote(query)), timeout)
    soup = BeautifulSoup(xml, "xml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    # The <result><positions> block wraps one <positions> per job; a job node is
    # any <positions> that has a direct <id> child.
    for node in soup.find_all("positions"):
        id_tag = node.find("id", recursive=False)
        if not id_tag:
            continue
        pid = id_tag.get_text(strip=True)
        if not pid or pid in seen:
            continue
        seen.add(pid)

        title_tag = node.find("title", recursive=False)
        title = _SPAN.sub("", title_tag.get_text(strip=True)) if title_tag else ""
        comp_tag = node.find("companyName", recursive=False)
        closed_tag = node.find("closedAt", recursive=False)
        cat_tag = node.find("jobCategory", recursive=False)

        locs = _texts(node, "locations")
        stacks = _texts(node, "techStacks")
        snippet_parts = []
        if cat_tag and cat_tag.get_text(strip=True):
            snippet_parts.append(cat_tag.get_text(strip=True))
        if stacks:
            snippet_parts.append(", ".join(stacks))

        _dl = closed_tag.get_text(strip=True) if closed_tag else None
        _dd, _st = _derive_status(_dl, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=pid,
                url=f"{BASE}/position/{pid}",
                title=title,
                company=comp_tag.get_text(strip=True) if comp_tag else None,
                location=", ".join(locs) if locs else None,
                employment_type=None,       # not exposed by this endpoint
                posted_at=None,             # not exposed by this endpoint
                deadline=_dl,
                deadline_date=_dd,
                status=_st,
                salary=None,                # not exposed by this endpoint
                snippet="; ".join(snippet_parts) or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Jumpit.")
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

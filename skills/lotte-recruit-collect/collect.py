#!/usr/bin/env python3
"""job-searcher :: Lotte Recruit collector — self-contained, read-only.

Collects current public postings from Lotte Recruit (recruit.lotte.co.kr) and
prints a normalized JSON array (see docs/SCHEMA.md). The public announcement
list page (`/apply/announcement/list`) is server-rendered, so this is a plain
GET of that page — no login, save, or apply.

This is a company career portal, so it exposes one flat list of every open
announcement rather than a keyword search. `--query` therefore filters the
fetched list client-side by title/company substring (the site ignores a
server-side keyword param).

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --limit 20
    python3 collect.py --query "IT" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SOURCE = "lotte"
BASE = "https://recruit.lotte.co.kr"
LIST_URL = BASE + "/apply/announcement/list"
DETAIL_URL = BASE + "/apply/announcement/detail/{id}"

_ID = re.compile(r"/apply/announcement/detail/(\d+)")
# application period "2026.06.22 ~ 2026.07.07" -> capture the closing date
_CLOSE = re.compile(r"~\s*(\d{4})\.(\d{2})\.(\d{2})")


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
    return resp.text


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_fetch(LIST_URL, timeout), "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for card in soup.select("li:has(div.job-card-group)"):
        a = card.select_one(".card-tit a")
        if not a:
            continue
        m = _ID.search(a.get("href", ""))
        pid = m.group(1) if m else None
        if not pid or pid in seen:
            continue
        title = a.get_text(strip=True)
        corp_el = card.select_one(".cmp-name")
        company = corp_el.get_text(strip=True) if corp_el else None
        if needle and needle not in f"{title} {company or ''}".lower():
            continue
        seen.add(pid)

        date_el = card.select_one(".card-foot .date")
        date_txt = date_el.get_text(strip=True) if date_el else ""
        cm = _CLOSE.search(date_txt)
        deadline = f"{cm.group(1)}-{cm.group(2)}-{cm.group(3)}" if cm else (date_txt or None)

        # badge (신입/경력) + D-day text as the visible tags for this card
        tags = [b.get_text(strip=True) for b in card.select(".bage-group span") if b.get_text(strip=True)]
        dday_el = card.select_one(".card-foot .dday")
        if dday_el and dday_el.get_text(strip=True):
            tags.append(dday_el.get_text(strip=True))
        snippet = ", ".join(tags) or None

        out.append(
            JobPosting(
                source=SOURCE,
                external_id=pid,
                url=DETAIL_URL.format(id=pid),
                title=title,
                company=company,
                location=None,       # not shown on the list card
                employment_type=None,  # only 신입/경력 level shown (kept in snippet)
                posted_at=None,
                deadline=deadline,
                salary=None,
                snippet=snippet,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Lotte Recruit.")
    ap.add_argument("--query", "-q", default=None,
                    help="filter the list by title/company substring (client-side)")
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

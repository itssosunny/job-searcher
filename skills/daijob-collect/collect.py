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

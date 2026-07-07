#!/usr/bin/env python3
"""job-seeker :: Apple Jobs collector — self-contained, read-only.

Collects recent public postings from Apple's careers site (jobs.apple.com) and
prints a normalized JSON array (see docs/SCHEMA.md). Apple's search page is
server-rendered: the result set ships inside a `window.__staticRouterHydrationData`
JSON blob, so this is a plain GET of the public search page — no login, no save,
no apply. Defaults to Korea; `--location` maps to Apple's location filter slug.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "engineer" --limit 20
    python3 collect.py --location korea-republic-of-KOR
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

SOURCE = "apple-jobs"
BASE = "https://jobs.apple.com"
SEARCH_URL = BASE + "/en-us/search?{qs}"
PER_PAGE = 20  # Apple returns 20 results per search page

_HYDRATION = re.compile(
    r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);', re.S
)


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


def _search_page(query: str | None, location: str, page: int, timeout: int) -> dict:
    params = {"location": location, "page": page}
    if query:
        params["search"] = query
    html = _fetch(SEARCH_URL.format(qs=urlencode(params)), timeout)
    m = _HYDRATION.search(html)
    if not m:
        raise RuntimeError("Apple search page returned no hydration data (layout changed?)")
    # The captured group is a JS string literal wrapping escaped JSON.
    data = json.loads(json.loads('"' + m.group(1) + '"'))
    return data.get("loaderData", {}).get("search", {}) or {}


def _location(row: dict) -> str | None:
    parts = []
    for loc in row.get("locations", []) or []:
        city = (loc.get("city") or "").strip()
        name = (loc.get("name") or loc.get("countryName") or "").strip()
        parts.append(f"{city}, {name}" if city and name else (city or name))
    parts = [p for p in parts if p]
    return "; ".join(dict.fromkeys(parts)) or None


def _posted_at(row: dict) -> str | None:
    gmt = row.get("postDateInGMT")
    if gmt:
        try:
            return datetime.fromisoformat(gmt.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return row.get("postingDate")  # e.g. "Jul 07, 2026"


def collect(query: str | None, limit: int, location: str = "korea-republic-of-KOR",
            timeout: int = 25) -> list[JobPosting]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    page = 1
    while len(out) < limit:
        search = _search_page(query, location, page, timeout)
        results = search.get("searchResults") or []
        if not results:
            break
        for row in results:
            pid = str(row.get("positionId") or row.get("reqId") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            slug = row.get("transformedPostingTitle") or ""
            team_code = (row.get("team") or {}).get("teamCode")
            url = f"{BASE}/en-us/details/{pid}/{slug}"
            if team_code:
                url += f"?team={team_code}"
            summary = (row.get("jobSummary") or "").strip().replace("\n", " ")
            out.append(
                JobPosting(
                    source=SOURCE,
                    external_id=pid,
                    url=url,
                    title=(row.get("postingTitle") or "").strip(),
                    company="Apple",
                    location=_location(row),
                    employment_type=None,  # Apple search exposes no clean type field
                    posted_at=_posted_at(row),
                    deadline=None,
                    salary=None,
                    snippet=(summary[:200] or None),
                    collected_at=now,
                )
            )
            if len(out) >= limit:
                break
        total = search.get("totalRecords") or 0
        if page * PER_PAGE >= total:
            break
        page += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from Apple Jobs.")
    ap.add_argument("--query", "-q", default=None, help="search keyword (optional)")
    ap.add_argument("--location", "-l", default="korea-republic-of-KOR",
                    help="Apple location filter slug (default Korea)")
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
          + f" location={args.location!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

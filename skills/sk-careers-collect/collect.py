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
    salary: str | None
    snippet: str | None
    collected_at: str


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

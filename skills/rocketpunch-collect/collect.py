#!/usr/bin/env python3
"""job-seeker :: RocketPunch collector — self-contained, read-only (best-effort).

Tries to collect public postings from RocketPunch's (rocketpunch.com) /jobs
listing and print a normalized JSON array (see docs/SCHEMA.md). Plain GET only —
no login, no save, no apply.

STATUS: needs_browser. RocketPunch serves /jobs behind an AWS WAF JavaScript
challenge (HTTP 202 + awsWafCookieDomainList + challenge.js), so a plain fetch
receives the interstitial, not the listing. This collector detects that gate and
exits honestly rather than fabricating postings. If the WAF cookie is ever
already warm (no challenge), the parser below extracts server-rendered
`/jobs/<id>` cards; that path is intentionally generic (no single-company
hardcoding) but is not exercised in the gated case.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "개발자" --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "rocketpunch"
BASE = "https://www.rocketpunch.com"
LISTING_URL = BASE + "/jobs?keywords={q}"

_JOB = re.compile(r"/jobs/(\d+)")


class NeedsBrowser(RuntimeError):
    """Raised when the listing is served behind a JS bot challenge."""


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


def _fetch(url: str, timeout: int):
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.get(url, impersonate="safari", timeout=timeout)
    return resp


def _is_waf_challenge(resp) -> bool:
    body = resp.text
    return (
        resp.status_code == 202
        or "awsWafCookieDomainList" in body
        or "challenge.js" in body
        or "AwsWafIntegration" in body
    )


def collect(query: str, limit: int, timeout: int = 25) -> list[JobPosting]:
    from bs4 import BeautifulSoup

    resp = _fetch(LISTING_URL.format(q=quote(query)), timeout)
    if _is_waf_challenge(resp):
        raise NeedsBrowser(
            "RocketPunch /jobs is served behind an AWS WAF JavaScript challenge; "
            "the listing needs a browser to render. needs_browser."
        )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: list[JobPosting] = []
    seen: set[str] = set()

    # Generic server-rendered path: each posting links to /jobs/<numeric-id>.
    for a in soup.select('a[href*="/jobs/"]'):
        m = _JOB.search(a.get("href", ""))
        if not m:
            continue
        jid = m.group(1)
        if jid in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        seen.add(jid)
        # Walk up to a card container to harvest company / meta text.
        card = a
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent
        meta = card.get_text(" ", strip=True) if card else ""
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=jid,
                url=f"{BASE}/jobs/{jid}",
                title=title,
                company=None,
                location=None,
                employment_type=None,
                posted_at=None,
                deadline=None,
                salary=None,
                snippet=meta[:200] or None,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from RocketPunch (best-effort).")
    ap.add_argument("--query", "-q", default="개발자", help="search keyword")
    ap.add_argument("--limit", "-n", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        postings = collect(args.query, args.limit, args.timeout)
    except NeedsBrowser as exc:
        print(json.dumps({"source": SOURCE, "error": str(exc), "needs_browser": True, "postings": []}), file=sys.stderr)
        return 1
    except Exception as exc:  # network / parse failure — honest, no fabrication
        print(json.dumps({"source": SOURCE, "error": str(exc), "postings": []}), file=sys.stderr)
        return 1

    data = [asdict(p) for p in postings]
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"{SOURCE}: {len(data)} postings for query={args.query!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

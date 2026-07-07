#!/usr/bin/env python3
"""job-searcher :: NAVER Careers collector — self-contained, read-only.

Collects current public postings from NAVER Careers (recruit.navercorp.com) and
prints a normalized JSON array (see docs/SCHEMA.md). The public listing page
(`/rcrt/list.do`) renders its cards client-side from a JSON endpoint
(`/rcrt/loadJobList.do`); this collector calls that same public endpoint with a
plain GET — no login, save, or apply.

The endpoint's `sw` (search word) parameter is a real server-side filter, so
`--query` narrows results at the source.

Standalone usage:
    pip install curl_cffi beautifulsoup4 lxml
    python3 collect.py --query "AI" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

SOURCE = "naver"
BASE = "https://recruit.navercorp.com"
LIST_PAGE = BASE + "/rcrt/list.do"
# JSON endpoint the list page's drawJobList() consumes; `sw` = search word.
API_URL = BASE + "/rcrt/loadJobList.do?sw={q}&firstIndex={start}"
VIEW_URL = BASE + "/rcrt/view.do?annoId={anno}"


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


def _fetch_json(url: str, timeout: int) -> dict:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        sys.exit("Missing deps. Run: pip install curl_cffi beautifulsoup4 lxml")
    resp = creq.get(
        url,
        impersonate="safari",
        timeout=timeout,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": LIST_PAGE},
    )
    resp.raise_for_status()
    return resp.json()


def _iso_ymd(ymd: str | None) -> str | None:
    """`20260713` -> `2026-07-13`; anything else -> the raw value or None."""
    if not ymd:
        return None
    d = str(ymd).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return d or None


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sw = quote(query) if query else ""
    out: list[JobPosting] = []
    seen: set[str] = set()
    start = 0
    # The endpoint pages via firstIndex; loop until we have `limit`, the source
    # is exhausted, or a safety cap trips.
    for _ in range(50):
        data = _fetch_json(API_URL.format(q=sw, start=start), timeout)
        rows = data.get("list") or []
        if not rows:
            break
        total = data.get("totalSize")
        for r in rows:
            anno = r.get("annoId")
            if anno is None:
                continue
            anno = str(anno)
            if anno in seen:
                continue
            seen.add(anno)
            tags = [
                r.get("classCdNm"),
                r.get("subJobCdNm"),
                r.get("entTypeCdNm"),
                r.get("reqTypeCdNm"),
            ]
            snippet = ", ".join(t for t in tags if t) or None
            out.append(
                JobPosting(
                    source=SOURCE,
                    external_id=anno,
                    url=r.get("jobDetailLink") or VIEW_URL.format(anno=anno),
                    title=(r.get("annoSubject") or "").strip(),
                    company=r.get("sysCompanyCdNm") or None,
                    location=None,  # only a workAreaCd code is exposed, no label
                    employment_type=r.get("empTypeCdNm") or None,
                    posted_at=_iso_ymd(r.get("staYmd")),
                    deadline=_iso_ymd(r.get("endYmd")),
                    salary=None,
                    snippet=snippet,
                    collected_at=now,
                )
            )
            if len(out) >= limit:
                return out
        start += len(rows)
        if isinstance(total, int) and start >= total:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from NAVER Careers.")
    ap.add_argument("--query", "-q", default=None,
                    help="server-side search word (`sw`); default lists all open postings")
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

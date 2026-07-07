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
                deadline=closed_tag.get_text(strip=True) if closed_tag else None,
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

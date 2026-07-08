#!/usr/bin/env python3
"""job-searcher :: DevRunner collector — self-contained, read-only.

Collects recent public postings from DevRunner (devrunner.dev) and prints a
normalized JSON array (see docs/SCHEMA.md). The /jobs listing is a JS app, but
its server response embeds the full initial job list as data in the Next.js RSC
flight stream, so a plain GET of the public /jobs page is enough — no login, no
save, no apply, no browser. `--query` filters that embedded list client-side by
title/company/summary/tech substring.

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

SOURCE = "devrunner"
BASE = "https://devrunner.dev"
LISTING_URL = BASE + "/jobs"

# Next.js RSC flight chunks: self.__next_f.push([1,"...escaped json..."])
_PUSH = re.compile(r"self\.__next_f\.\x70ush\((\[.*?\])\)</script>", re.S)


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


def _extract_jobs(html: str) -> list[dict]:
    """Pull the embedded initialJobs.jobs[] array out of the RSC flight stream."""
    for block in _PUSH.findall(html):
        if "initialJobs" not in block:
            continue
        try:
            _chunk_id, flight = json.loads(block)
        except (ValueError, TypeError):
            continue
        idx = flight.find('"jobs":[')
        if idx < 0:
            continue
        start = flight.index("[", idx)
        depth = 0
        end = None
        for j in range(start, len(flight)):
            ch = flight[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end is None:
            continue
        try:
            return json.loads(flight[start:end])
        except ValueError:
            continue
    return []


def _iso(epoch_ms) -> str | None:
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _salary(job: dict) -> str | None:
    lo, hi = job.get("compensationMinBasePay"), job.get("compensationMaxBasePay")
    if not lo and not hi:
        return None
    cur = job.get("compensationCurrency") or ""
    unit = job.get("compensationUnit") or ""
    span = f"{lo or ''}~{hi or ''}".strip("~")
    return " ".join(p for p in (cur, span, unit) if p) or None


def collect(query: str | None, limit: int, timeout: int = 25) -> list[JobPosting]:
    jobs = _extract_jobs(_fetch(LISTING_URL, timeout))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    needle = query.lower() if query else None
    out: list[JobPosting] = []
    seen: set[str] = set()

    for job in jobs:
        jid = job.get("jobId")
        if jid is None or str(jid) in seen:
            continue
        title = (job.get("title") or "").strip()
        if not title:
            continue
        company = job.get("company") or job.get("organization")
        locations = job.get("locations") or []
        location = ", ".join(locations) or None
        summary = job.get("oneLineSummary") or ""
        tech = job.get("techCategories") or []
        snippet = " · ".join(filter(None, [summary, ", ".join(tech)]))[:200] or None

        haystack = " ".join(filter(None, [
            title, company, job.get("organization"), summary,
            job.get("positionCategory"), " ".join(tech), location,
        ])).lower()
        if needle and needle not in haystack:
            continue

        seen.add(str(jid))
        deadline = None if job.get("isOpenEnded") else _iso(job.get("endedAt"))
        _dd, _st = _derive_status(deadline, now)
        out.append(
            JobPosting(
                source=SOURCE,
                external_id=str(jid),
                url=f"{BASE}/jobs/{jid}",
                title=title,
                company=company,
                location=location,
                employment_type=job.get("employmentType"),
                posted_at=_iso(job.get("createdAt")),
                deadline=deadline,
                deadline_date=_dd,
                status=_st,
                salary=_salary(job),
                snippet=snippet,
                collected_at=now,
            )
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public postings from DevRunner.")
    ap.add_argument("--query", "-q", default=None, help="filter listing by title/company/tech substring")
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

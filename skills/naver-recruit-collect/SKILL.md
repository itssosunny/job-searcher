---
name: naver-recruit-collect
description: Collect current public job postings from NAVER Careers (recruit.navercorp.com). Use when the user wants to gather, scan, or monitor NAVER's open roles, optionally by keyword. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# NAVER Careers Collect

Collect current public postings from NAVER Careers and return normalized JSON
(`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its own
fetch + parse and depends only on `curl_cffi` (plus `beautifulsoup4`/`lxml`,
shared with the other collectors).

## Boundaries

- **Read-only.** GET of the public listing JSON endpoint only. Never log in,
  save a job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, and dates are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/naver-recruit-collect/collect.py --limit 20
python3 skills/naver-recruit-collect/collect.py --query "AI" --limit 20
```

- `--query, -q` — server-side search word. NAVER's listing endpoint takes an
  `sw` parameter that genuinely filters at the source, so this narrows results
  (empty default = all open postings).
- `--limit, -n` — max postings (default 20). The endpoint pages via
  `firstIndex`; the collector walks pages until it has `--limit` or the source
  is exhausted.
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr.

## Notes

- Source: `SRC-JOB-NAVER` — https://recruit.navercorp.com/ (re-verified
  2026-07-07). This is a company career portal: it typically lists only a
  handful of open postings at a time (all NAVER-group companies).
- Listing endpoint: `GET /rcrt/loadJobList.do?sw=<kw>&firstIndex=<n>` returns
  JSON `{list, totalSize}`. The `/rcrt/list.do` page renders those rows
  client-side via `drawJobList()`, so scraping the HTML would yield nothing —
  call the JSON endpoint (this skill does).
- `external_id` is `annoId`; the canonical posting URL is the item's
  `jobDetailLink` (`/rcrt/view.do?annoId=<id>`).
- `company` is `sysCompanyCdNm` (the specific NAVER-group entity). `location` is
  left `null` — the feed exposes only a `workAreaCd` code with no readable label.
  `snippet` carries the job class / sub-job / hire-type tags.
- If the endpoint returns 0 rows or its field names change, re-derive against a
  live fetch of `/rcrt/loadJobList.do` (do not hardcode a specific posting).

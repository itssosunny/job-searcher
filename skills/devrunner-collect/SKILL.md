---
name: devrunner-collect
description: Collect recent public developer job postings from DevRunner (devrunner.dev) by keyword. Use when the user wants to gather, scan, or monitor DevRunner listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# DevRunner Collect

Collect recent public postings from DevRunner's `/jobs` listing and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public `/jobs` listing only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, dates, and tags are copied verbatim from the page's own data.
- A collected posting reflects the page at run time; it is not proof the role is
  still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/devrunner-collect/collect.py --query "backend" --limit 20
```

- `--query, -q` — filter the listing by title/company/summary/tech substring
  (client-side; see Notes).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. DevRunner exposes
title, company, location, employment type, position category, tech categories,
a one-line summary, created date (→ `posted_at`), end date (→ `deadline`), and
compensation when present (→ `salary`).

## Notes

- Source: `SRC-JOB-DEVRUNNER` — https://devrunner.dev/ (collectible_open,
  verified 2026-07-07).
- The `/jobs` page is a JS (Next.js) app, but its server response embeds the
  full initial job list (~200 postings) as data in the RSC flight stream
  (`self.__next_f` → `initialJobs.jobs[]`). `collect.py` parses that embedded
  JSON directly, so no browser is required. `external_id` is the numeric
  `jobId`; canonical posting URL: `/jobs/<jobId>`.
- Because the whole initial list is embedded, `--query` filters it client-side.
  DevRunner's server-side filters/pagination are JS-driven; collecting results
  beyond the embedded initial list would need a browser.
- If DevRunner changes its RSC shape and 0 postings return, re-derive the
  `initialJobs`/`"jobs":[` extraction against a live fetch (do not hardcode a
  specific company).

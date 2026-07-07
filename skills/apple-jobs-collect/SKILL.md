---
name: apple-jobs-collect
description: Collect recent public job postings from Apple's careers site (jobs.apple.com), default Korea, by keyword and location. Use when the user wants to gather, scan, or monitor Apple job listings for a role or region. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Apple Jobs Collect

Collect recent public postings from Apple's careers search and return normalized
JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its
own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public search page only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  locations, and dates are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/apple-jobs-collect/collect.py --limit 20
python3 skills/apple-jobs-collect/collect.py --query "engineer" --limit 10
```

- `--query, -q` — search keyword (optional; omitted = all Korea postings).
- `--location, -l` — Apple location filter slug (default `korea-republic-of-KOR`).
- `--limit, -n` — max postings (default 20; the collector pages through 20-per-page
  results until the limit or `totalRecords` is reached).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Apple exposes title,
location, posting date, and a job-summary snippet; `company` is `Apple` (this is
Apple's own board). `employment_type`, `deadline`, and `salary` are `null` — the
Korea search results do not expose them.

## Notes

- Source: `SRC-JOB-APPLE` — https://jobs.apple.com/ (collectible_open,
  re-verified 2026-07-07). Korea search returned 23 total records at verification.
- The search page is server-rendered: results ship inside a
  `window.__staticRouterHydrationData` JSON blob (`loaderData.search.searchResults`),
  parsed directly — no separate JSON API call.
- `external_id` is the numeric `positionId`. Posting detail URL:
  `/en-us/details/<positionId>/<transformedPostingTitle>?team=<teamCode>`.
- If Apple changes the hydration key and 0 postings return, re-derive the
  `window.__staticRouterHydrationData` / `searchResults` path against a live fetch
  (do not hardcode a specific role or req id).

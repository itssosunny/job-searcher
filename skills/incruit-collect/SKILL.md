---
name: incruit-collect
description: Collect recent public job postings from Incruit (인크루트) by keyword. Use when the user wants to gather, scan, or monitor Incruit listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Incruit Collect

Collect recent public postings from Incruit's keyword search and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public search page only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and deadlines are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/incruit-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet,
collected_at`); a one-line count on stderr. Incruit's search exposes company,
region, employment type, and deadline; `posted_at` is not exposed (only relative
"N일전 등록" text, left in `snippet`).

## Notes

- Source: `SRC-JOB-INCRUIT` — https://www.incruit.com/ (collectible_open,
  re-verified 2026-07-07). Server-side keyword search lives on the search
  subdomain: `https://search.incruit.com/list/search.asp?col=job&kw=<q>`.
- Incruit serves **EUC-KR/CP949**, not UTF-8; `collect.py` decodes the raw
  bytes with `cp949` (do not rely on `resp.text`).
- Rows are `ul.c_row`; company is `a.cpname` and the title is the
  `jobdb_info/jobpost.asp?job=<id>` anchor. `external_id` is that numeric `job`
  id. Canonical detail URL: `https://job.incruit.com/jobdb_info/jobpost.asp?job=<id>`.
- If the layout changes and 0 postings return, re-derive the `ul.c_row` /
  `a.cpname` / jobpost-anchor selectors against a live fetch (do not hardcode a
  specific company).

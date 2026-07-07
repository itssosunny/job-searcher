---
name: jobkorea-collect
description: Collect recent public job postings from JobKorea (잡코리아) by keyword. Use when the user wants to gather, scan, or monitor JobKorea listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# JobKorea Collect

Collect recent public postings from JobKorea's keyword search and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public search page only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, salaries, and locations are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

```bash
# one-time deps (or: pip install -r requirements.txt)
pip install curl_cffi beautifulsoup4 lxml

python3 skills/jobkorea-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Each item has
`source, external_id, url, title, company, location, employment_type,
posted_at, deadline, salary, snippet, collected_at`.

## Notes

- Source: `SRC-JOB-JOBKOREA` — https://www.jobkorea.co.kr/ (collectible_open,
  re-verified 2026-07-07).
- Posting detail URLs use the `Recruit/GI_Read/<id>` pattern; `external_id` is
  that numeric id (stable for dedup).
- JobKorea's search markup is a Tailwind card layout (`div.shadow-list`); if the
  layout changes and 0 postings return, re-derive the card/anchor selectors
  against a live fetch (do not hardcode a specific company).

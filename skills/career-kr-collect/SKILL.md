---
name: career-kr-collect
description: Collect recent public job postings from Career.co.kr (커리어) by keyword. Use when the user wants to gather, scan, or monitor Career.co.kr listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Career.co.kr Collect

Collect recent public postings from Career.co.kr's public jobs listing and
return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public `/jobs/` listing only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and deadlines are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/career-kr-collect/collect.py --query "개발자" --limit 20
python3 skills/career-kr-collect/collect.py --limit 20      # whole listing
```

- `--query, -q` — filter the listing by title/company substring (**client-side**;
  see Notes). Omit to return the whole listing.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet,
collected_at`); a one-line count on stderr. Career.co.kr exposes company,
location, employment type, deadline, and sector hashtags (kept in `snippet`).

## Notes

- Source: `SRC-JOB-CAREER` — https://job.career.co.kr/ (collectible_open,
  re-verified 2026-07-07). The root auto-redirects to `/jobs/`.
- **Keyword filtering is client-side.** The public `/jobs/` listing ignores GET
  keyword params (`?keyword=`, `?searchWord=`, `?q=` all return the same
  featured list); the site's server-side search is a POST-only filter form,
  which is out of scope for a read-only GET collector. So `--query` filters the
  fetched listing by title/company substring, like the WeWorkRemotely feed
  collector. For unfiltered breadth, omit `--query`.
- Rows are `tbody tr` containing a `/recruit/view/<id>` anchor; `external_id` is
  that numeric id. Canonical detail URL: `/recruit/view/<id>`.
- If the layout changes and 0 postings return, re-derive the `tbody tr` /
  `a[href*='/recruit/view/']` selectors and the per-cell mapping against a live
  fetch (do not hardcode a specific company).

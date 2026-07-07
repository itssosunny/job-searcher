---
name: wanted-collect
description: Collect recent public job postings from Wanted (원티드) by keyword. Use when the user wants to gather, scan, or monitor Wanted listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Wanted Collect

Collect recent public postings from Wanted's own public jobs API and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`.

## Boundaries

- **Read-only.** GET of the public jobs JSON API only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the API does not expose are `null`; titles,
  companies, and locations are copied verbatim. The `reward` field is a
  referral bounty, not a salary, so `salary` stays `null`.
- A collected posting reflects the API at run time; it is not proof the role is
  still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi   # or: pip install -r requirements.txt

python3 skills/wanted-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Each item has
`source, external_id, url, title, company, location, employment_type,
posted_at, deadline, salary, snippet, collected_at`.

## Notes

- Source: `SRC-JOB-WANTED` — https://www.wanted.co.kr/ (collectible_open,
  re-verified 2026-07-07). The site's own JSON API is the stable interface —
  prefer it over scraping the JS-rendered HTML.
- Endpoint: `GET /api/v4/jobs?country=kr&job_sort=job.latest_order&years=-1&limit=<n>&keyword=<q>`;
  postings live under `data[]`. `external_id` is the numeric `id`; canonical
  detail URL is `/wd/<id>`.
- The list endpoint exposes company, region+district location, and `due_time`
  deadline; it does not expose employment type, posted date, or a role
  description, so those are `null`.
- If the API shape changes and 0 postings return, re-derive the `data[]` field
  names against a live fetch (do not hardcode a specific company).

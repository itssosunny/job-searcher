---
name: rallit-collect
description: Collect recent public job postings from Rallit (랠릿) by keyword. Use when the user wants to gather, scan, or monitor Rallit developer listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Rallit Collect

Collect recent public postings from Rallit's own public position API and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`.

## Boundaries

- **Read-only.** GET of the public position JSON API only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the API does not expose are `null`; titles,
  companies, regions, and skill tags are copied verbatim. The `joinReward`
  field is a referral bounty, not a salary, so `salary` stays `null`.
- A collected posting reflects the API at run time; it is not proof the role is
  still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi   # or: pip install -r requirements.txt

python3 skills/rallit-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Each item has
`source, external_id, url, title, company, location, employment_type,
posted_at, deadline, salary, snippet, collected_at`.

## Notes

- Source: `SRC-JOB-RALLIT` — https://www.rallit.com/ (collectible_open,
  re-verified 2026-07-07). The site's own JSON API is the stable interface —
  prefer it over scraping the JS-rendered HTML.
- Endpoint: `GET /api/v1/position?keyword=<q>&pageNumber=1&pageSize=<n>`;
  postings live under `data.items[]`. `external_id` is the numeric `id`;
  canonical detail URL is `/positions/<id>` (the API also returns `url`).
- Exposes region (`addressRegion`) and skill tags (folded into `snippet`).
  `startedAt`/`endedAt` map to `posted_at`/`deadline`, but the API's sentinel
  bounds (`1970-01-01`, `9999-12-31`) mean "always open" and are normalized to
  `null`. Employment type and salary are not exposed, so they are `null`.
- If the API shape changes and 0 postings return, re-derive the `data.items[]`
  field names against a live fetch (do not hardcode a specific company).

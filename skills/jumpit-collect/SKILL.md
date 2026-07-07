---
name: jumpit-collect
description: Collect recent public job postings from Jumpit (점핏) by keyword. Use when the user wants to gather, scan, or monitor Jumpit developer listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Jumpit Collect

Collect recent public postings from Jumpit's own public positions API and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public positions API only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the API does not expose are `null`; titles,
  companies, locations, deadlines, and tech-stack tags are copied verbatim.
- A collected posting reflects the API at run time; it is not proof the role is
  still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/jumpit-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Each item has
`source, external_id, url, title, company, location, employment_type,
posted_at, deadline, salary, snippet, collected_at`.

## Notes

- Source: `SRC-JOB-JUMPIT` — https://jumpit.saramin.co.kr/ (collectible_open,
  re-verified 2026-07-07). The site's own API is the stable interface — prefer
  it over scraping the JS-rendered HTML.
- Endpoint: `GET https://jumpit-api.saramin.co.kr/api/positions?sort=reg_dt&highlight=false&keyword=<q>`.
  It returns **XML** (parsed with BeautifulSoup's `xml` mode): each job is a
  `<positions>` node with a direct `<id>` child. `external_id` is that `id`;
  canonical detail URL is `/position/<id>`.
- Exposes location, `closedAt` deadline, job category, and tech-stack tags
  (folded into `snippet`); it does not expose employment type, posted date, or
  salary, so those are `null`. Keyword-matched titles may wrap the match in
  `<span>` markup — the collector strips it.
- If the API shape changes and 0 postings return, re-derive the `<positions>`
  node fields against a live fetch (do not hardcode a specific company).

---
name: daijob-collect
description: Collect recent public job postings from Daijob (daijob.com) — bilingual/English jobs in Japan. Use when the user wants to gather, scan, or monitor Daijob listings by keyword. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Daijob Collect

Collect recent public postings from Daijob's server-rendered English job search
and return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public search-result page only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and salaries are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/daijob-collect/collect.py --query "engineer" --limit 20
python3 skills/daijob-collect/collect.py --limit 20   # latest in-Japan roles
```

- `--query, -q` — free-word keyword (mapped to Daijob's `kw` search param).
- `--limit, -n` — max postings (default 20; the search page serves ~20/page).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Daijob exposes
company, location, salary, and a job-description snippet cleanly. Employment
type is not surfaced on the card, so it stays `null`.

## Notes

- Source: `SRC-JOB-DAIJOB` — https://www.daijob.com/en/ (collectible_open,
  verified 2026-07-07). The listing is at `/en/jobs/search?in_japan=true&pg=0`
  (redirects to `/en/jobs/search_result`); `/en/jobs` itself is a category hub,
  not a posting list.
- Cards are `article.job-card`; the title is `h2.job-card__title a` with an href
  of `/en/jobs/detail/<id>`. `external_id` is that numeric `<id>`. Location,
  salary, and description are read from the card's `dl`/`dt`/`dd` rows.
- If the layout changes and 0 postings return, re-derive the `article.job-card`
  child selectors against a live fetch (do not hardcode a specific company).

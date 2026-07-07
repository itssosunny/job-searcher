---
name: japandev-collect
description: Collect recent public job postings from Japan Dev (japan-dev.com) — IT jobs in Japan for English speakers. Use when the user wants to gather, scan, or monitor Japan Dev listings by role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Japan Dev Collect

Collect recent public postings from Japan Dev's server-rendered `/jobs` listing
and return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public `/jobs` listing only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and salaries are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/japandev-collect/collect.py --query "backend" --limit 20
python3 skills/japandev-collect/collect.py --limit 20   # all listed roles
```

- `--query, -q` — filter the listing by title/company substring (client-side).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Japan Dev exposes
company, location, salary band (`¥…`), and a remote/onsite arrangement cleanly;
residency/visa badges and technology tags land in `snippet`.

## Notes

- Source: `SRC-JOB-JAPANDEV` — https://japan-dev.com/ (collectible_open,
  verified 2026-07-07). The `/jobs` page is server-rendered and returns ~60 job
  cards in a single fetch.
- Cards are `li.job-item`; the title/link is `a.job-item__title` with an href of
  `/jobs/<company-slug>/<job-slug>`. `external_id` is the trailing `<job-slug>`
  (stable for dedup); company is read from the logo alt.
- `--query` filters the single fetched listing client-side (no server search
  param), so it narrows within the ~60 currently listed roles rather than
  querying the whole site.
- If the layout changes and 0 postings return, re-derive the `li.job-item`
  child selectors against a live fetch (do not hardcode a specific company).

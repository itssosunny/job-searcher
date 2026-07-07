---
name: dev-korea-collect
description: Collect recent public job postings from Dev Korea (dev-korea.com), English-friendly Korea tech jobs, by keyword. Use when the user wants to gather, scan, or monitor Dev Korea listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Dev Korea Collect

Collect recent public postings from Dev Korea's `/jobs` listing and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public `/jobs` listing only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and tags are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/dev-korea-collect/collect.py --query "data" --limit 20
```

- `--query, -q` — filter the listing by title/company/location/tag substring
  (client-side; see Notes).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet,
collected_at`); a one-line count on stderr. Dev Korea exposes title, company,
location, employment type, and a tech/language tag list cleanly; it does not
expose posting date, deadline, or salary in the listing (those stay `null`).

## Notes

- Source: `SRC-JOB-DEV-KOREA` — https://dev-korea.com/ (collectible_open,
  verified 2026-07-07).
- Cards are `li.dk-border`; the title anchor and `external_id` come from the
  `/jobs/<slug>` link, and company from the `/companies/<slug>` link. Canonical
  posting URL: `/jobs/<slug>`.
- The server renders a fixed first page (~10 cards); the site's own search box
  and pagination are JS-only, so query params (`?search=`, `?page=`) do not
  change the server response. `--query` therefore filters that first page
  client-side. Collecting beyond the first page needs a browser.
- If the layout changes and 0 postings return, re-derive the `li.dk-border`
  child selectors against a live fetch (do not hardcode a specific company).

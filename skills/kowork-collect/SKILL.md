---
name: kowork-collect
description: Collect recent public job postings from KOWORK (kowork.kr), an English jobs-for-foreigners board in Korea. Use when the user wants to gather, scan, or monitor KOWORK listings — foreigner-eligible roles with visa-sponsorship tags. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# KOWORK Collect

Collect recent public postings from KOWORK's English jobs-for-foreigners listing
and return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public `/en` listing only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the feed does not expose are `null`; titles,
  companies, locations, and visa/type tags are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/kowork-collect/collect.py --query "developer" --limit 20
python3 skills/kowork-collect/collect.py --limit 20      # whole first page
```

- `--query, -q` — filter the listing by title/company substring (**client-side**;
  see Notes). Omit to return the whole first page.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. KOWORK exposes
company (from the logo `alt`), location, employment type, and metadata pills
(visa eligibility like `E-7 Sponsors`, job category) — the full pill set is kept
in `snippet`, with a deadline `D-<n>` in `deadline` when shown.

## Notes

- Source: `SRC-JOB-KOWORK` — https://kowork.kr/en (collectible_open, re-verified
  2026-07-07). This is a board for foreigners in Korea, so postings carry visa
  tags (E-7, F-series, etc.).
- **First page only, best-effort.** KOWORK is a server-rendered Next.js app; the
  static HTML holds ~15 postings (the first page). More requires a real browser
  (infinite scroll), which is out of scope for a plain-fetch collector.
- **Keyword filtering is client-side.** The `?search=` param is ignored
  server-side, so `--query` filters the fetched page by title/company substring.
- Each card is an `a[href*='/en/post/<id>']`; `external_id` is that numeric id.
  Canonical detail URL: `/en/post/<id>`. Company comes from the logo image `alt`
  (`job-list-<company>-logo`); the metadata pills are duplicated across
  desktop/mobile blocks and are deduped on text.
- If the Tailwind markup changes and 0 postings return, re-derive the card
  anchor, `p.line-clamp-2` title, and pill selectors against a live fetch (do
  not hardcode a specific company).

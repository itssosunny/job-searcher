---
name: sap-jobs-collect
description: Collect public job postings from SAP's careers board (jobs.sap.com) for the Seoul listing by keyword. Use when the user wants to gather, scan, or monitor SAP Korea/Seoul job listings for a role. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# SAP Jobs Collect

Collect public postings from SAP's SuccessFactors careers board (the Seoul
listing) and return normalized JSON (`docs/SCHEMA.md`). Self-contained: this
skill's `collect.py` carries its own fetch + parse and depends only on
`curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public listing page only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the listing does not expose are `null`; titles and
  locations are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/sap-jobs-collect/collect.py --limit 20
python3 skills/sap-jobs-collect/collect.py --query "architect"
```

- `--query, -q` — filter the parsed rows by title/location substring (client-side;
  the listing URL itself is fixed to Seoul).
- `--limit, -n` — max postings (default 20; the Seoul listing is one page, ~19 rows).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. SAP's Seoul listing
exposes title, location (`Seoul, KR, <postcode>`), and req id. `company` is `SAP`
(this is SAP's own board). `employment_type`, `posted_at`, `deadline`, and
`salary` are `null` — the listing table does not expose them.

## Notes

- Source: `SRC-JOB-SAP` — https://jobs.sap.com/ (collectible_open, re-verified
  2026-07-07). The Seoul category page `/go/SAP-Jobs-in-Seoul/944001/` returned
  19 server-rendered rows at verification.
- Rows are `tr.data-row`; `external_id` is the trailing numeric req id in the
  `a.jobTitle-link` href. Canonical posting URL is `jobs.sap.com` + that href.
- If the layout changes and 0 postings return, re-derive the `tr.data-row` /
  `a.jobTitle-link` / `span.jobLocation` selectors against a live fetch (do not
  hardcode a specific role or req id).

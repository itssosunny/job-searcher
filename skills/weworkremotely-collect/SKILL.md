---
name: weworkremotely-collect
description: Collect recent public remote job postings from We Work Remotely. Use when the user wants to gather, scan, or monitor remote/global listings from WeWorkRemotely by keyword or category. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# We Work Remotely Collect

Collect recent public postings from We Work Remotely's published RSS feed and
return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of a published public RSS feed only. Never log in, save a
  job, message, or apply.
- **No fabrication.** Fields the feed does not expose are `null`; titles,
  companies, regions, and dates are copied verbatim.
- A collected posting reflects the feed at run time; it is not proof the role is
  still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/weworkremotely-collect/collect.py --query "engineer" --limit 20
python3 skills/weworkremotely-collect/collect.py --category remote-programming-jobs
```

- `--query, -q` — filter the feed by title/company substring (client-side).
- `--category, -c` — category feed slug, e.g. `remote-programming-jobs`,
  `remote-design-jobs`, `remote-devops-sysadmin-jobs`. Default: the all-jobs feed.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. The RSS feed exposes
company (split from `Company: Role` titles), region, employment type, and
publish date.

## Notes

- Source: `SRC-JOB-WEWORKREMOTELY` — https://weworkremotely.com/ (collectible_open,
  re-verified 2026-07-07). RSS (`/remote-jobs.rss`, `/categories/<slug>.rss`) is
  the stable interface — prefer it over scraping the HTML listing.
- `external_id` is the posting slug from the URL.

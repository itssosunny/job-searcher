---
name: coupang-collect
description: Collect current public job postings from Coupang (쿠팡) careers. Use when the user wants to gather, scan, or monitor Coupang listings by keyword or location. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Coupang Collect

Collect current public postings from Coupang's careers board and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the published careers JSON API only. Never log in, save
  a job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and dates are copied verbatim.
- A collected posting reflects the board at run time; it is not proof the role is
  still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/coupang-collect/collect.py --query "engineer" --limit 20
python3 skills/coupang-collect/collect.py --query "Seoul" --limit 20
```

- `--query, -q` — filter by title/location substring (client-side). Default: all.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr. The board exposes title, location, company, and the
first-published date (`posted_at`).

## Notes

- Source: `SRC-JOB-COUPANG` — https://www.coupang.jobs/ (verified 2026-07-07).
- Coupang runs a **Greenhouse**-backed board (token `coupang`); this skill reads
  the published jobs JSON at
  `https://boards-api.greenhouse.io/v1/boards/coupang/jobs`. `external_id` is the
  Greenhouse job id (== `gh_jid`); the canonical detail URL is
  `https://www.coupang.jobs/kr/jobs/<id>/?gh_jid=<id>`.
- The board is **global** (600+ roles across regions), not KR-only. Filter with
  `--query "Seoul"` / `--query "Korea"` for Korea-based roles.
- `employment_type`, `deadline`, and `salary` are not exposed on the board list,
  so they are `null`. If the board token changes and 0 postings return, re-probe
  `boards-api.greenhouse.io/v1/boards/<token>/jobs` (do not hardcode a role id).

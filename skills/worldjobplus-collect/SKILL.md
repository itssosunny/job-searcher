---
name: worldjobplus-collect
description: Collect public overseas-job postings from WorldJobPlus (월드잡플러스), Korea HRD's 해외취업 portal, by keyword and country. Use when the user wants to gather, scan, or monitor overseas (해외취업) job listings for a role or country. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# WorldJobPlus Collect

Collect public overseas-employment postings from WorldJobPlus (월드잡플러스), the
Korea HRD (한국산업인력공단) 해외취업 portal, and return normalized JSON
(`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its own
fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET/POST of the public listing endpoint only (the POST just
  sets page size / page index — it is not a login or an application). Never log
  in, save a job, message, or apply.
- **No fabrication.** Fields the listing does not expose are `null`; titles,
  employers, countries, salaries, and deadlines are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/worldjobplus-collect/collect.py --limit 20
python3 skills/worldjobplus-collect/collect.py --query "engineer" --location 일본
```

- `--query, -q` — filter the parsed rows by title/employer substring (client-side).
- `--location, -l` — filter by country substring, e.g. `일본`, `베트남`, `미국`
  (client-side; country is exposed per row).
- `--limit, -n` — max postings (default 20; the collector pages through the list
  50-per-page until the limit is reached).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout; a one-line count on stderr. Each row exposes
title, employer (`company`), country (`location`), salary (연봉/시급 as shown),
employment type (정규직/계약직/인턴 as shown), application deadline (`MM/DD(요일)`),
and a snippet (job field / experience / education / visa).

## Notes

- Source: `SRC-JOB-WORLDJOBPLUS` — https://www.worldjob.or.kr/ (collectible_open,
  re-verified 2026-07-07). The list endpoint `/advnc/cnttNewList.do` is
  server-rendered; posting ids look like `E20260707013`.
- Rows are `div.post-box`; `external_id` is the `E…` id from the row's
  `goView1('E…')` handler. The detail page is a JavaScript popup with no plain-GET
  URL, so `url` points at the public list endpoint and the stable id lives in
  `external_id` (no fabricated detail link).
- If the layout changes and 0 postings return, re-derive the `div.post-box` child
  selectors (`h5.mb4 a`, `p.mb8 a`, `.nation-box img`, `.day-box`,
  `.post-condition-box p`) against a live fetch (do not hardcode a specific role
  or posting id).

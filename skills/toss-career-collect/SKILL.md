---
name: toss-career-collect
description: Collect current public job postings from Toss Career (토스 채용, 비바리퍼블리카/자회사). Use when the user wants to gather, scan, or monitor Toss listings by keyword, team, or location. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Toss Career Collect

Collect current public postings from Toss's careers board and return normalized
JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its
own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public careers JSON API only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and dates are copied verbatim.
- A collected posting reflects the board at run time; it is not proof the role is
  still open.

## Run

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/toss-career-collect/collect.py --query "server" --limit 20
python3 skills/toss-career-collect/collect.py --query "부산" --limit 20
```

- `--query, -q` — filter by title/company/location substring (client-side).
  Default: all.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr. Toss exposes employment type (정규직/계약직 등, from
job metadata), location, first-published date (`posted_at`), and the job
category (as `snippet`).

## Notes

- Source: `SRC-JOB-TOSS-CAREER` — https://toss.im/career (verified 2026-07-07).
- The `toss.im/career` page renders its list **client-side** (JS; the portal
  shows "0개 포지션" before scripts run), but the same list is served by Toss's
  public careers JSON API, which this skill reads directly:
  `https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs`. No browser needed.
- The board is Greenhouse-backed: `external_id` is the `gh_jid` and the detail
  URL is `https://toss.im/career/job-detail?gh_jid=<id>`.
- `employment_type` and `snippet` come from each job's `metadata`
  (`Employment_Type`, `Job Category`). If the API path changes and 0 postings
  return, re-derive it by grepping the career page's JS bundles for
  `ipd-eggnog/career` (do not hardcode a specific job id).

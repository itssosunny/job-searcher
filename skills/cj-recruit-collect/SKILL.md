---
name: cj-recruit-collect
description: Collect current public job postings from CJ Careers (CJ 그룹 채용). Use when the user wants to gather, scan, or monitor CJ group listings (CJ ENM, TVING, CJ제일제당, CJ푸드빌 등). Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# CJ Careers Collect

Collect current public postings from CJ's recruit portal and return normalized
JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its
own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public recruit frame only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, and periods are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/cj-recruit-collect/collect.py --query "ENM" --limit 20
```

- `--query, -q` — filter by title/company substring (client-side). Default: all.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr. CJ exposes company (subsidiary), the recruit period
(as `deadline`), and rolling/experience tags (as `snippet`).

## Notes

- Source: `SRC-JOB-CJ-RECRUIT` — https://recruit.cj.net/ (verified 2026-07-07).
- CJ's root is a frameset; the server-rendered listing lives in the main frame
  `/recruit/ko/main/main/main.fo`, which this skill fetches directly. Cards are
  `a.btn-filter[href*='bestDetail']` with `p.tit`, `span.company`, `span.type`,
  `span.badge`, `p.period` children.
- `external_id` is the `zz_jo_num` (e.g. `J20251224037598`); the canonical
  detail URL is `bestDetail.fo?zz_jo_num=<id>`.
- **Scope / browser limit.** The main frame server-renders the current featured
  postings (the set this skill returns). The exhaustive keyword-search list at
  `/recruit/ko/recruit/recruit/list.fo` loads its rows via client-side AJAX and
  is **not** enumerable by a plain GET — collecting the full search result set
  needs a real browser. If 0 postings return, re-derive the card selectors
  against a live fetch of the main frame (do not hardcode a specific company).

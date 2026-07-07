---
name: saramin-collect
description: Collect recent public job postings from Saramin (사람인) by keyword. Use when the user wants to gather, scan, or monitor Saramin listings for a role, stack, or company. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Saramin Collect

Collect recent public postings from Saramin's keyword search and return
normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's `collect.py`
carries its own fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`,
`lxml`.

## Boundaries

- **Read-only.** GET of the public search page only. Never log in, save a job,
  message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, locations, and deadlines are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/saramin-collect/collect.py --query "데이터 엔지니어" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet,
collected_at`); a one-line count on stderr. Saramin exposes location,
employment type, deadline, and sector tags cleanly.

## Notes

- Source: `SRC-JOB-SARAMIN` — https://www.saramin.co.kr/ (collectible_open,
  re-verified 2026-07-07; the root auto-redirects same-host to `/zf_user/`).
- Cards are `div.item_recruit`; `external_id` is the `rec_idx`. Canonical
  posting URL: `/zf_user/jobs/relay/view?rec_idx=<id>`.
- If the layout changes and 0 postings return, re-derive the `.item_recruit`
  child selectors against a live fetch (do not hardcode a specific company).

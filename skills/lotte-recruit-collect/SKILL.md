---
name: lotte-recruit-collect
description: Collect current public job postings from Lotte Recruit (recruit.lotte.co.kr). Use when the user wants to gather, scan, or monitor Lotte-group open announcements, optionally filtered by keyword. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# Lotte Recruit Collect

Collect current public postings from Lotte Recruit's announcement list and
return normalized JSON (`docs/SCHEMA.md`). Self-contained: this skill's
`collect.py` carries its own fetch + parse and depends only on `curl_cffi`,
`beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public announcement-list page only. Never log in,
  save a job, message, or apply. Do not submit any form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, and application dates are copied verbatim.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/lotte-recruit-collect/collect.py --limit 20
python3 skills/lotte-recruit-collect/collect.py --query "IT" --limit 20
```

- `--query, -q` — filter by title/company substring. This is a **company career
  portal** that serves one flat list of every open announcement and ignores a
  server-side keyword param, so the filter is applied **client-side** to the
  fetched list (empty default = all open announcements).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr.

## Notes

- Source: `SRC-JOB-LOTTE` — https://recruit.lotte.co.kr/ (re-verified
  2026-07-07). The announcement list is **server-rendered**, so a plain GET of
  `/apply/announcement/list` returns every card — no browser needed.
- Cards are `li` wrapping `div.job-card-group`: `.cmp-name` is the Lotte-group
  entity, `.card-tit a` is the title + `/apply/announcement/detail/<id>` link,
  `.card-foot .date` is the application period and `.dday` the D-day tag.
- `external_id` is the numeric announcement id; the canonical posting URL is
  `/apply/announcement/detail/<id>`.
- `deadline` is parsed from the closing date of the application period
  (`… ~ 2026.07.07` → `2026-07-07`). `location` and `employment_type` are `null`
  (the list card shows neither); the 신입/경력 badge and D-day are kept in
  `snippet`.
- If the layout changes and 0 postings return, re-derive the `.job-card-group`
  child selectors against a live fetch (do not hardcode a specific company).

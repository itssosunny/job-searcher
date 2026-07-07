---
name: michael-page-collect
description: Attempt to collect public job postings from Michael Page (michaelpage.com). Use when the user wants Michael Page listings — but note the result list is JS-rendered, so plain fetch cannot enumerate it and the collector reports needs_browser. Read-only — no login, save, or apply.
---

# Michael Page Collect

Best-effort collector for Michael Page's public job search, returning normalized
JSON (`docs/SCHEMA.md`) when postings are server-rendered. Self-contained: this
skill's `collect.py` carries its own fetch + parse and depends only on
`curl_cffi`, `beautifulsoup4`, `lxml`.

## Listing needs a browser

Michael Page renders its result list **client-side** (Salesforce/thunderhead
lightning): a plain fetch of `/job-search` returns an empty search shell
(`body.search-empty-result`) with **no server-rendered postings**, and the
origin is slow/flaky (a single request can take 60–120s or time out). There is
no public jobs RSS or sitemap of postings.

So a no-login fetch **cannot enumerate this listing**. Rather than fabricate,
the collector reports `needs_browser`: it prints an empty JSON array on stdout
and a `{"source": "michaelpage", "needs_browser": true, ...}` note on stderr,
and exits `1`. To actually collect Michael Page postings, drive the search in a
real browser (e.g. the claude-in-chrome / Playwright tools) and read the
rendered `/job-detail/<slug>/ref/<id>` cards.

## Boundaries

- **Read-only.** Best-effort GET of the public search page only. Never log in,
  save a job, message, or apply. Do not submit any form.
- **No fabrication.** When nothing is server-rendered, the collector says
  `needs_browser` instead of inventing postings.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/michael-page-collect/collect.py --query "engineering" --limit 20
```

- `--query, -q` — search keyword (a Korea location filter is applied when set).
- `--limit, -n` — max postings (default 20).
- `--timeout` — per-request timeout in seconds (default 90; the origin is slow).
- `--pretty` — indent the JSON.

The parser handles the `/job-detail/<slug>/ref/<id>` pattern, so if Michael Page
ever serves postings server-side this collector upgrades to `works` with no code
change. Until then, expect a `needs_browser` result.

## Notes

- Source: `SRC-JOB-MICHAELPAGE` — https://www.michaelpage.com/ (probed
  2026-07-07: reachable but JS-only listing + slow origin → `needs_browser`).
- Detail URL pattern: `/job-detail/<slug>/ref/<id>`; `external_id` is the `<id>`.
- Do not hardcode a specific company; the URL pattern is the only platform
  assumption.

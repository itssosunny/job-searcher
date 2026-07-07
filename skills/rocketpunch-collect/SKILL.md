---
name: rocketpunch-collect
description: Collect recent public job postings from RocketPunch (rocketpunch.com) by keyword. Use when the user wants to gather, scan, or monitor RocketPunch listings for a role, stack, or company. Read-only — no login, save, or apply. The listing needs a browser (AWS WAF challenge); collect.py detects the gate and reports needs_browser honestly.
---

# RocketPunch Collect

Best-effort collector for RocketPunch's `/jobs` listing, normalized to
`docs/SCHEMA.md`. Self-contained: this skill's `collect.py` carries its own
fetch + parse and depends only on `curl_cffi`, `beautifulsoup4`, `lxml`.

## Boundaries

- **Read-only.** GET of the public `/jobs` listing only. Never log in, save a
  job, message, or apply. Do not submit any form.
- **No fabrication.** When the listing is not reachable by fetch, `collect.py`
  reports the reason and returns no postings — it never invents rows.
- A collected posting reflects the public page at run time; it is not proof the
  role is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/rocketpunch-collect/collect.py --query "개발자" --limit 20
```

- `--query, -q` — search keyword (default `개발자`).
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

## Status: the listing needs a browser (needs_browser)

RocketPunch serves `/jobs` behind an **AWS WAF JavaScript challenge** (HTTP
`202` with `awsWafCookieDomainList`, `challenge.js`, and `AwsWafIntegration`),
so a plain read-only GET receives the challenge interstitial, not the job list.
Solving it requires executing the challenge script in a real browser, which is
out of scope for a fetch-only, read-only collector.

`collect.py` detects the challenge and exits `1` with a JSON error carrying
`"needs_browser": true` on stderr — it does not fabricate postings. To actually
collect RocketPunch, drive the listing in a browser (e.g. claude-in-chrome /
Playwright) so the WAF cookie is issued, then hand the rendered HTML to the
generic `/jobs/<id>` card parser already in `collect.py`.

## Notes

- Source: `SRC-JOB-ROCKETPUNCH` — https://www.rocketpunch.com/jobs
  (needs_browser, verified 2026-07-07).
- Detail URLs use the `/jobs/<id>` pattern; `external_id` is that numeric id.
- The parser is intentionally generic (any `/jobs/<id>` card, no single-company
  hardcoding). If RocketPunch ever drops the WAF gate for server-rendered HTML,
  the same `collect.py` will return postings without changes.

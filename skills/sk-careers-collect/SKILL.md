---
name: sk-careers-collect
description: Collect current public job postings from SK Careers (skcareers.com). Use when the user wants to gather, scan, or monitor SK-group open roles, optionally by keyword. Read-only — no login, save, or apply. Prints a normalized JSON array of postings.
---

# SK Careers Collect

Collect current public postings from SK Careers and return normalized JSON
(`docs/SCHEMA.md`). Self-contained: this skill's `collect.py` carries its own
fetch + parse and depends only on `curl_cffi` (plus `beautifulsoup4`/`lxml`,
shared with the other collectors).

## Boundaries

- **Read-only.** GET of the public recruit page + a call to its public listing
  JSON endpoint with empty filters. Never log in, save a job, message, or apply.
  Do not submit any application form.
- **No fabrication.** Fields the source does not expose are `null`; titles,
  companies, and locations are copied verbatim. If the endpoint is throttling,
  the collector reports an error rather than inventing postings.
- A collected posting reflects the source at run time; it is not proof the role
  is still open.

## Run

If `collect.py` fails with `ModuleNotFoundError`, install the deps yourself
(`pip install curl_cffi beautifulsoup4 lxml`) and retry — do not ask the user
to install anything.

```bash
pip install curl_cffi beautifulsoup4 lxml   # or: pip install -r requirements.txt

python3 skills/sk-careers-collect/collect.py --limit 20
python3 skills/sk-careers-collect/collect.py --query "반도체" --limit 20
```

- `--query, -q` — server-side search word. SK's listing endpoint takes a
  `searchText` field that filters at the source (the value is percent-encoded to
  mirror the site's own `encodeURIComponent`); empty default = all open postings.
- `--limit, -n` — max postings (default 20).
- `--pretty` — indent the JSON.

Output: a JSON array on stdout (`source, external_id, url, title, company,
location, employment_type, posted_at, deadline, salary, snippet, collected_at`);
a one-line count on stderr.

## Notes

- Source: `SRC-JOB-SK` — https://www.skcareers.com/ (re-verified 2026-07-07).
  Covers all SK-group companies (SK hynix, SK telecom, SK innovation, …).
- Listing endpoint: `POST /Recruit/GetRecruitList` with the seven filter fields
  empty returns JSON `{success, totalCount, list}`. The `/Recruit` page renders
  those rows client-side, so scraping the HTML yields nothing — call the JSON
  endpoint (this skill does, with the `X-Requested-With`/`Referer`/`Origin`
  headers the site's own script sends).
- `external_id` is `noticeID` (e.g. `R261397`); the canonical posting URL is
  `/Recruit/Detail/<noticeID>`. `company` = `corpName`, `location` =
  `workingArea`, `employment_type` = `workingType`, `deadline` = `D-<remainDay>`,
  and `snippet` carries the job-role / recruit-type tags.
- **Rate-sensitive endpoint.** `GetRecruitList` intermittently returns an HTML
  404 error page (instead of JSON) when the source is throttling by IP —
  especially under rapid repeated calls. The collector already retries a few
  times with backoff; if it still fails it exits non-zero with an honest
  `error`. Re-run after a short pause and space out calls. (The public
  `/Recruit` page and the `GetAutocomplete` endpoint stay reachable during a
  throttle, so a 404 here is throttling, not a dead route.)

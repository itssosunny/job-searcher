# Normalized `JobPosting` schema

Every `collect.py` prints a JSON array of `JobPosting` objects to stdout. The
schema is intentionally small and platform-agnostic so postings from any source
merge cleanly.

| field | type | notes |
| --- | --- | --- |
| `source` | string | platform id, e.g. `jobkorea`, `saramin`, `weworkremotely` |
| `external_id` | string \| null | the platform's own posting id (for dedup) |
| `url` | string | canonical public posting URL |
| `title` | string | role title |
| `company` | string \| null | hiring company / employer |
| `location` | string \| null | as shown on the source |
| `employment_type` | string \| null | 정규직/계약직/인턴/full-time/remote… as shown |
| `posted_at` | string \| null | ISO-8601 date if the source exposes one |
| `deadline` | string \| null | ISO-8601 or source text (e.g. `~07.20`, `D-5`) |
| `deadline_date` | string \| null | ISO-8601 date derived from `deadline` when it parses to a real date; else `null`. Never invented. |
| `status` | string | `open` / `closing_soon` / `closed` / `rolling` / `unknown` — derived from `deadline` + `collected_at`. |
| `salary` | string \| null | as shown; never inferred |
| `snippet` | string \| null | short description / tags, trimmed |
| `collected_at` | string | ISO-8601 UTC timestamp of this collection run |

## Rules

- **Read-only.** Collectors only GET public listing/search/detail pages. Never
  log in, save, message, or apply. Never submit forms.
- **No fabrication.** A field is `null` when the source does not expose it.
  Numbers, dates, and company names are copied verbatim from the source.
- **Best-effort freshness.** Listings reflect what the public page shows at run
  time; a collected posting is not proof the role is still open.
- **Derived status.** `deadline_date` and `status` are computed from the
  posting's own `deadline` text plus `collected_at` — never from a guess or an
  external clock. `deadline` stays the verbatim ground truth. Rules: a parseable
  future date → `open` (≥4 days) or `closing_soon` (today..+3); a past date →
  `closed`; 상시/수시/open-until-filled with no date → `rolling`; nothing
  parseable → `unknown`. Sources that expose no deadline are always `unknown`.
- **Self-contained.** Each skill's `collect.py` carries its own fetch + parse +
  this schema inline. You can copy one skill directory out and it runs
  standalone with `pip install curl_cffi beautifulsoup4 lxml`. The
  `_derive_status` helper is duplicated byte-identically across skills by design.

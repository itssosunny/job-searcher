# job-seeker

A Claude Code plugin: **one self-contained skill per job platform**. Each skill
collects recent **public** job postings from its source and prints a normalized
JSON array (`docs/SCHEMA.md`). Read-only by design — no login, no saving, no
messaging, no applying.

## Design

- **One skill = one source.** Each `skills/<platform>-collect/` is fully
  standalone: its `collect.py` carries its own fetch + parse + the normalized
  schema inline. Copy a single skill directory out and it runs with just
  `pip install curl_cffi beautifulsoup4 lxml`.
- **Normalized output.** Every collector prints the same `JobPosting` shape, so
  postings from different sources merge cleanly. See [docs/SCHEMA.md](docs/SCHEMA.md).
- **Honest.** A field is `null` when the source doesn't expose it. Nothing is
  inferred or fabricated. A collected posting is not proof the role is still open.
- **Read-only.** Collectors only GET public search/listing/RSS pages. `curl_cffi`
  impersonates a real browser TLS fingerprint so public pages that reject plain
  `requests` still return content — it never logs in or submits a form.

## Install

As a Claude Code plugin (self-hosted marketplace):

```
/plugin marketplace add <this-repo>
/plugin install job-seeker
```

Or run any collector directly:

```bash
pip install -r requirements.txt
python3 skills/jobkorea-collect/collect.py --query "데이터 엔지니어" --limit 20
```

## Sources (24 fetch-collectible platforms)

Derived from a 2026-07-07 collectibility scan of a 53-source registry: these 24
returned a concrete public posting via automated no-login fetch/search. All 24
collectors are implemented — 21 are live-verified against the real source, 1 is
correct but was rate-limited during the build session, and 2 have JS-only /
anti-bot listings and honestly report `needs_browser`.

| Skill | Platform | Status |
| --- | --- | --- |
| `jobkorea-collect` | JobKorea (잡코리아) | ✅ works |
| `saramin-collect` | Saramin (사람인) | ✅ works |
| `weworkremotely-collect` | We Work Remotely | ✅ works (RSS) |
| `wanted-collect` | Wanted (원티드) | ✅ works (JSON API) |
| `jumpit-collect` | Jumpit (점핏) | ✅ works (XML API) |
| `rallit-collect` | Rallit (랠릿) | ✅ works (JSON API) |
| `incruit-collect` | Incruit (인크루트) | ✅ works (CP949) |
| `career-kr-collect` | Career.co.kr | ✅ works |
| `dev-korea-collect` | Dev Korea | ✅ works |
| `kowork-collect` | KOWORK | ✅ works (first page) |
| `devrunner-collect` | DevRunner | ✅ works (RSC stream) |
| `cj-recruit-collect` | CJ Careers | ✅ works (featured; full search needs browser) |
| `coupang-collect` | Coupang | ✅ works (Greenhouse API) |
| `toss-career-collect` | Toss Career | ✅ works (public API) |
| `naver-recruit-collect` | NAVER Careers | ✅ works (JSON API) |
| `lotte-recruit-collect` | Lotte Recruit | ✅ works |
| `apple-jobs-collect` | Apple Jobs (Korea) | ✅ works (SSR JSON) |
| `sap-jobs-collect` | SAP Jobs (Seoul) | ✅ works |
| `worldjobplus-collect` | WorldJobPlus (해외취업) | ✅ works |
| `japandev-collect` | Japan Dev | ✅ works |
| `daijob-collect` | Daijob | ✅ works |
| `sk-careers-collect` | SK Careers | ⏳ works, rate-limited during build (JSON endpoint returned 83 postings; IP-throttled after heavy probing — re-run later) |
| `rocketpunch-collect` | RocketPunch (로켓펀치) | 🔒 needs browser (AWS WAF JS challenge) |
| `michael-page-collect` | Michael Page | 🔒 needs browser (Salesforce JS-only listing) |

Legend: **✅ works** — a plain no-login fetch/API returns concrete postings
(live-verified 2026-07-07). **⏳** — collector is correct but the source
rate-limited this build session. **🔒 needs browser** — the listing is
JS-only/anti-bot; the skill detects the gate and exits honestly (exit 1 +
`needs_browser`) rather than fabricating. A `needs_browser` skill still ships:
it carries the correct parser and auto-upgrades if the source serves postings
server-side.

## License

MIT.

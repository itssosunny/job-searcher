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
returned a concrete public posting via automated no-login fetch/search. `✅` =
reference collector implemented + live-verified; the rest are planned with the
same standalone pattern.

| Skill | Platform | Status |
| --- | --- | --- |
| `jobkorea-collect` | JobKorea (잡코리아) | ✅ |
| `saramin-collect` | Saramin (사람인) | ✅ |
| `weworkremotely-collect` | We Work Remotely | ✅ |
| `wanted-collect` | Wanted (원티드) | planned |
| `jumpit-collect` | Jumpit (점핏) | planned |
| `rallit-collect` | Rallit (랠릿) | planned |
| `rocketpunch-collect` | RocketPunch (로켓펀치) | planned |
| `incruit-collect` | Incruit (인크루트) | planned |
| `career-kr-collect` | Career.co.kr | planned |
| `dev-korea-collect` | Dev Korea | planned |
| `kowork-collect` | KOWORK | planned |
| `devrunner-collect` | DevRunner | planned |
| `sk-careers-collect` | SK Careers | planned |
| `lotte-recruit-collect` | Lotte Recruit | planned |
| `naver-recruit-collect` | NAVER Careers | planned |
| `cj-recruit-collect` | CJ Careers | planned |
| `coupang-collect` | Coupang | planned |
| `toss-career-collect` | Toss Career | planned |
| `apple-jobs-collect` | Apple Jobs (Korea) | planned |
| `sap-jobs-collect` | SAP Jobs (Seoul) | planned |
| `worldjobplus-collect` | WorldJobPlus (해외취업) | planned |
| `michael-page-collect` | Michael Page | planned |
| `japandev-collect` | Japan Dev | planned |
| `daijob-collect` | Daijob | planned |

Sources needing a real browser (JS-only / anti-bot 403) are intentionally out of
scope for v1's plain-fetch collectors.

## License

MIT.

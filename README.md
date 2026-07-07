# 잡써쳐 (job-searcher)

> **구직할 때, 여러 플랫폼을 찾아다니지 마세요. 자동으로 수집하세요.**
> Don't hop between job boards — let your agent collect them.

24개 채용 플랫폼(잡코리아·사람인·원티드·점핏 + 글로벌) → **하나의 정규화 JSON**.
Claude Code 스킬 팩. **읽기 전용** — 로그인 안 함, 저장 안 함, 지원(apply) 안 함. MIT.

<!-- TODO: assets/demo.gif — 30초 데모 (설치 → "공고 모아줘" → 표 출력) -->

## 사용방법

### Claude Code 플러그인으로 (권장)

```
/plugin marketplace add itssosunny/job-searcher
/plugin install job-searcher
```

설치가 끝나면 자연어로 시키면 됩니다:

- "잡코리아에서 마케터 공고 20개 모아줘"
- "원티드랑 점핏에서 데이터 엔지니어 공고 모아서 표로 정리해줘"
- "쿠팡·토스·네이버 채용 페이지에서 백엔드 공고 모아줘"

필요한 Python 패키지(`curl_cffi`, `beautifulsoup4`, `lxml`)가 없으면 에이전트가 알아서 설치합니다.

### 스크립트로 직접 실행

```bash
pip install -r requirements.txt
python3 skills/jobkorea-collect/collect.py --query "데이터 엔지니어" --limit 20
```

모든 수집기는 같은 `JobPosting` JSON 배열을 출력하므로 소스가 달라도 결과가 깔끔하게 합쳐집니다.
스키마는 [docs/SCHEMA.md](docs/SCHEMA.md).

## 수집하는 플랫폼 (24개)

24개 모두 구현되어 있습니다. 21개는 실제 소스에 대해 라이브 검증했고(2026-07-07),
1개는 검증 세션 중 rate-limit에 걸렸으며(수집기 자체는 정상), 2개는 JS 전용/anti-bot
페이지라 가짜 데이터 대신 `needs_browser`로 정직하게 종료합니다.

| 스킬 | 플랫폼 | 상태 |
| --- | --- | --- |
| `jobkorea-collect` | 잡코리아 (JobKorea) | ✅ 동작 |
| `saramin-collect` | 사람인 (Saramin) | ✅ 동작 |
| `wanted-collect` | 원티드 (Wanted) | ✅ 동작 (JSON API) |
| `jumpit-collect` | 점핏 (Jumpit) | ✅ 동작 (XML API) |
| `rallit-collect` | 랠릿 (Rallit) | ✅ 동작 (JSON API) |
| `incruit-collect` | 인크루트 (Incruit) | ✅ 동작 (CP949) |
| `career-kr-collect` | Career.co.kr | ✅ 동작 |
| `dev-korea-collect` | Dev Korea | ✅ 동작 |
| `kowork-collect` | KOWORK | ✅ 동작 (첫 페이지) |
| `devrunner-collect` | DevRunner | ✅ 동작 (RSC 스트림) |
| `toss-career-collect` | 토스 채용 | ✅ 동작 (공개 API) |
| `naver-recruit-collect` | 네이버 채용 | ✅ 동작 (JSON API) |
| `coupang-collect` | 쿠팡 | ✅ 동작 (Greenhouse API) |
| `cj-recruit-collect` | CJ 채용 | ✅ 동작 (추천 공고; 전체 검색은 브라우저 필요) |
| `lotte-recruit-collect` | 롯데 채용 | ✅ 동작 |
| `apple-jobs-collect` | Apple Jobs (한국) | ✅ 동작 (SSR JSON) |
| `sap-jobs-collect` | SAP Jobs (서울) | ✅ 동작 |
| `weworkremotely-collect` | We Work Remotely | ✅ 동작 (RSS) |
| `worldjobplus-collect` | 월드잡플러스 (해외취업) | ✅ 동작 |
| `japandev-collect` | Japan Dev | ✅ 동작 |
| `daijob-collect` | Daijob | ✅ 동작 |
| `sk-careers-collect` | SK Careers | ⏳ 정상 동작 확인, 검증 세션 중 rate-limit — 재실행하면 됨 |
| `rocketpunch-collect` | 로켓펀치 (RocketPunch) | 🔒 브라우저 필요 (AWS WAF JS 챌린지) |
| `michael-page-collect` | Michael Page | 🔒 브라우저 필요 (Salesforce JS 전용 리스팅) |

범례 — **✅ 동작**: 로그인 없는 일반 fetch/API로 실제 공고가 확인됨 (2026-07-07 라이브 검증).
**⏳**: 수집기는 정상이나 해당 세션에서 소스가 rate-limit. **🔒 브라우저 필요**: JS 전용/anti-bot
페이지 — 스킬이 게이트를 감지하면 데이터를 지어내지 않고 `needs_browser`로 종료합니다
(파서는 내장되어 있어 소스가 서버사이드로 공고를 주기 시작하면 자동으로 살아납니다).

## 설계 원칙

- **하나의 스킬 = 하나의 플랫폼.** 각 `skills/<platform>-collect/`는 완전 자립형 —
  `collect.py` 하나에 fetch + parse + 스키마가 다 들어 있습니다. 디렉토리 하나만 복사해 가도
  `pip install curl_cffi beautifulsoup4 lxml`만 하면 그대로 돌아갑니다.
- **정규화 출력.** 모든 수집기가 같은 `JobPosting` 형태를 출력합니다 ([docs/SCHEMA.md](docs/SCHEMA.md)).
- **정직함.** 소스가 노출하지 않는 필드는 `null`입니다. 아무것도 추론하거나 지어내지 않습니다.
  수집된 공고가 "아직 열려 있다"는 보장은 아닙니다.
- **읽기 전용.** 공개 검색/목록/RSS 페이지를 GET만 합니다. `curl_cffi`가 실제 브라우저의 TLS
  지문을 흉내 내 일반 `requests`를 거부하는 공개 페이지도 읽을 수 있게 하지만 — 로그인하거나
  폼을 제출하는 일은 절대 없습니다.

## 유지보수에 대하여

수집기는 각 사이트의 공개 페이지 구조에 의존합니다. 사이트가 개편되면 일부 수집기가 멈출 수
있어요. 발견하면 이슈로 알려주세요 — 스킬 하나가 파일 하나라 고치기 쉽습니다.

## License

MIT

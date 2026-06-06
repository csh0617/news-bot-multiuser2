# 정치인 뉴스 크롤링·분류 봇

특정 정치인에 대한 뉴스를 주기적으로 수집하고, **외부 API를 거의 쓰지 않고** 로컬에서
세 가지로 분류해 Supabase(`news_articles`)에 저장한다.

1. **동명이인 구분** — 같은 이름의 다른 정치인 기사가 아닌지
2. **관련성** — 단순 이름 언급인지, 그 정치인이 주체인 기사인지
3. **감성** — 긍정 / 중립 / 부정

## 깔때기(funnel) 구조

```
수집 → 1.동명이인(로컬) → 2.관련성(로컬) → 3.감성(로컬 감성사전) → Supabase 저장
100건     party/직책 앵커      제목/리드/조사 규칙     긍/부정 어휘 + 부정어 처리
```

- 1·2단계가 무료 로컬 필터로 대부분을 걸러내므로, 비싼 단계(감성)는 소수만 본다.
- `url_hash` 중복 제거로 **같은 기사는 절대 두 번 처리하지 않는다.**
- 감성분류까지 전부 로컬 → **외부 분류 API 호출 0회.**

## 동명이인 구분 원리

정치인 마스터(`politicians`, 4227행)의 `party / region / district / position / career`를
**positive 앵커**로, 같은 이름을 가진 *다른* 정치인의 고유 식별자를 **negative 앵커**로 쓴다.

> 예: `이재명`(더불어민주당·대통령)과 `이재명`(국민의힘·충북 진천군의원)이 동시에 존재.
> 전자를 대상으로 하면 기사에 "국민의힘", "진천"이 나올 때 감점되어 동명이인으로 걸러진다.

`politicians.positive_keywords` / `negative_keywords` 배열로 인물별 수동 보정도 가능.

## 설정 (환경변수)

`.env.example` 참고. 핵심:

| 변수 | 설명 |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase 접속(필수) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 검색 API(선택, 없으면 HTML 스크래핑 폴백) |
| `SAVE_MENTIONS` | 단순 언급 기사도 저장할지(기본 false) |
| 각종 `*_THRESHOLD` | 분류 임계값 튜닝 |

> 비밀값은 절대 코드/리포에 넣지 말 것. (구버전 `users.json`의 텔레그램 토큰은 노출되었으니 **재발급** 권장.)

## 실행

```bash
pip install -r requirements.txt

# 특정 인물 1회 크롤링·분류
python -m newsbot.worker --once --names 이재명

# auto_crawl_enabled=true 인 정치인 전체 1회
python -m newsbot.worker --once

# 주기 루프 (LOOP_INTERVAL_SECONDS)
python -m newsbot.worker
```

크롤링 대상 지정 (SQL):

```sql
update politicians set auto_crawl_enabled = true, crawl_interval_hours = 6
where name = '이재명' and party = '더불어민주당';
```

`start.sh`는 워커(`app.py`)를 백그라운드로, 상태 대시보드(`web.py`)를 포그라운드로 실행한다
(Render 포트 감지용). 대시보드 `/` 에서 분류 현황을, `/health` 로 헬스체크를 제공.

## 스케줄링 대안 — Supabase pg_cron

워커 루프 대신 DB 내부 크론으로도 가능:

```sql
select cron.schedule('crawl-news', '0 */6 * * *', $$
  select net.http_post(
    url := 'https://<your-worker-host>/crawl',
    headers := '{"X-Trigger-Token":"<CRAWL_TRIGGER_TOKEN>"}'::jsonb);
$$);
```

## ⚠️ 보안: RLS

이 프로젝트는 `politicians`, `news_articles` 등 다수 테이블의 **RLS(행 수준 보안)가 꺼져 있어**
anon 키만으로 누구나 읽기/쓰기가 가능하다. 공개 사이트라면 읽기는 허용하되 쓰기는 막는 정책을
추가해야 한다. (정책 없이 RLS만 켜면 모든 접근이 차단되므로 정책과 함께 적용할 것.)

## 분류 정확도 높이기

규칙 기반은 가볍고 무료지만 한계가 있다. 더 높이려면:
- `positive_keywords` / `negative_keywords`로 인물별 앵커 보강
- `newsbot/nlp/lexicon_ko.py` 감성 어휘 보강
- 정확도가 더 필요하면 1·2단계 통과분(소수)에만 **배치 LLM(Haiku)** 을 끼워 넣는 방식으로
  확장 가능 (호출 수는 깔때기로 이미 최소화됨).
```

"""환경변수 기반 설정. 비밀값은 절대 코드/리포에 하드코딩하지 않는다."""
import os


def _get(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _flag(name, default="false"):
    return _get(name, default).lower() in ("1", "true", "yes", "on")


# --- Supabase ---
SUPABASE_URL = _get("SUPABASE_URL")
# 서버 워커는 service_role 키 사용(RLS 우회). 없으면 anon 키로 폴백.
SUPABASE_KEY = (
    _get("SUPABASE_SERVICE_ROLE_KEY")
    or _get("SUPABASE_KEY")
    or _get("SUPABASE_ANON_KEY")
)
SUPABASE_PROJECT_ID = _get("SUPABASE_PROJECT_ID", "rqusufmignjipgdsjhxn")

# --- 뉴스 소스 (네이버 검색 OpenAPI, 없으면 HTML 스크래핑 폴백) ---
NAVER_CLIENT_ID = _get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get("NAVER_CLIENT_SECRET")

# --- 스케줄/수집량 ---
LOOP_INTERVAL_SECONDS = int(_get("LOOP_INTERVAL_SECONDS", "1800"))   # 워커 루프 주기(30분)
ARTICLES_PER_POLITICIAN = int(_get("ARTICLES_PER_POLITICIAN", "20"))  # 1회당 정치인별 검색 건수
DEFAULT_CRAWL_INTERVAL_HOURS = int(_get("DEFAULT_CRAWL_INTERVAL_HOURS", "6"))
FETCH_FULL_CONTENT = _flag("FETCH_FULL_CONTENT")  # 본문 페이지까지 받아올지(느림). 기본은 검색 요약만.
MAX_POLITICIANS_PER_RUN = int(_get("MAX_POLITICIANS_PER_RUN", "50"))

# --- 분류 임계값 (튜닝 가능) ---
DISAMBIG_THRESHOLD = float(_get("DISAMBIG_THRESHOLD", "1.0"))          # 동명이인 통과 최소 점수
RELEVANCE_SUBJECT_THRESHOLD = float(_get("RELEVANCE_SUBJECT_THRESHOLD", "0.45"))
RELEVANCE_MENTION_THRESHOLD = float(_get("RELEVANCE_MENTION_THRESHOLD", "0.15"))
SENTIMENT_NEUTRAL_BAND = float(_get("SENTIMENT_NEUTRAL_BAND", "0.12"))  # 중립 데드밴드

# 'subject'(주체 기사)만 저장할지, 'mention'(단순 언급)도 저장할지
SAVE_MENTIONS = _flag("SAVE_MENTIONS")

# --- 선택: 텔레그램 알림 (기본 비활성, 주체 기사만 발송) ---
TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")
TELEGRAM_NOTIFY = _flag("TELEGRAM_NOTIFY")

CLASSIFIER_VERSION = "rule_v1"

"""Supabase 접근 계층. 비밀값은 환경변수에서만 읽는다."""
import hashlib
from datetime import datetime, timezone, timedelta

from supabase import create_client

from . import config

_client = None


def client():
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY 환경변수가 필요합니다.")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def url_hash(url):
    return hashlib.sha1((url or "").strip().encode("utf-8")).hexdigest()


def get_target_politicians(names=None, limit=None):
    """크롤링 대상 정치인 조회.

    names 가 주어지면 그 이름들만, 아니면 auto_crawl_enabled=true 인 정치인 중
    crawl_interval_hours 가 지난(또는 한 번도 안 한) 대상을 가져온다.
    """
    limit = limit or config.MAX_POLITICIANS_PER_RUN
    q = client().table("politicians").select("*")
    if names:
        q = q.in_("name", names)
        res = q.execute()
        return res.data or []

    res = q.eq("auto_crawl_enabled", True).limit(500).execute()
    rows = res.data or []
    now = datetime.now(timezone.utc)
    due = []
    for p in rows:
        hours = p.get("crawl_interval_hours") or config.DEFAULT_CRAWL_INTERVAL_HOURS
        last = p.get("last_crawled_at")
        if not last:
            due.append(p)
            continue
        last_dt = _parse_ts(last)
        if last_dt is None or now - last_dt >= timedelta(hours=hours):
            due.append(p)
    return due[:limit]


def get_same_name_politicians(name, exclude_id):
    res = client().table("politicians").select(
        "id,name,party,district,position,region,category,career"
    ).eq("name", name).execute()
    return [r for r in (res.data or []) if r.get("id") != exclude_id]


def article_exists(politician_id, uhash):
    res = (client().table("news_articles").select("id")
           .eq("politician_id", politician_id).eq("url_hash", uhash)
           .limit(1).execute())
    return bool(res.data)


def insert_article(record):
    return client().table("news_articles").insert(record).execute()


def update_last_crawled(politician_id):
    client().table("politicians").update(
        {"last_crawled_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", politician_id).execute()


def log_crawl(source, found, saved, status="success", error=None):
    try:
        client().table("crawling_logs").insert({
            "source": source, "articles_found": found,
            "articles_saved": saved, "status": status,
            "error_message": error,
        }).execute()
    except Exception as e:  # 로깅 실패가 파이프라인을 막지 않게
        print(f"[warn] crawling_logs 기록 실패: {e}")


def _parse_ts(value):
    if not value:
        return None
    try:
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

"""한 정치인에 대한 깔때기 파이프라인.

수집 → (중복제거) → 1.동명이인 → 2.관련성 → 3.감성 → 저장
비싼 단계가 적은 기사만 보도록 앞단에서 최대한 걸러낸다.
"""
from datetime import datetime, timezone

from . import config, db, crawler
from .nlp import disambiguation, relevance, sentiment

# politicians.category → news_articles.category (CHECK 제약 값이 다름)
_CATEGORY_MAP = {
    "metro_governor": "metropolitan_governor",
    "metropolitan_governor": "metropolitan_governor",
    "local_mayor": "mayor",
    "mayor": "mayor",
    "education": "superintendent",
    "superintendent": "superintendent",
    "congressman": "congressman",
    "president": "president",
    "cabinet": "cabinet",
    "metropolitan_council": "metropolitan_council",
    "local_council": "local_council",
}
_SENT_KO = {"positive": "긍정", "neutral": "중립", "negative": "부정"}


def _news_category(politician):
    return _CATEGORY_MAP.get(politician.get("category") or "", "congressman")


def _search_query(politician):
    """검색 단계에서부터 정당을 붙여 소스 레벨 1차 필터."""
    name = politician.get("name") or ""
    party = (politician.get("party") or "").strip()
    return f"{name} {party}".strip() if party else name


def process_politician(politician):
    pid = politician.get("id")
    name = politician.get("name") or ""
    aliases = politician.get("aliases") or []

    others = db.get_same_name_politicians(name, pid)
    profile = disambiguation.build_profile(politician, others)

    stats = {"found": 0, "saved": 0, "dup": 0, "unrelated": 0,
             "mention": 0, "subject": 0, "homonym_collisions": len(others)}

    articles = crawler.search(_search_query(politician))
    stats["found"] = len(articles)

    for art in articles:
        url = art.get("url")
        if not url:
            continue
        uhash = db.url_hash(url)
        if db.article_exists(pid, uhash):
            stats["dup"] += 1
            continue

        title = art.get("title") or ""
        content = art.get("content") or ""
        if config.FETCH_FULL_CONTENT and len(content) < 80:
            content = crawler.fetch_full_content(url) or content

        # 1단계: 동명이인
        dis = disambiguation.score(title, content, profile,
                                   config.DISAMBIG_THRESHOLD)
        # 2단계: 관련성 (동명이인 통과 여부 반영)
        rel = relevance.classify(
            title, content, name, aliases,
            disambiguation_passed=dis["passed"],
            subject_threshold=config.RELEVANCE_SUBJECT_THRESHOLD,
            mention_threshold=config.RELEVANCE_MENTION_THRESHOLD)

        if rel["label"] == "unrelated":
            stats["unrelated"] += 1
            continue
        if rel["label"] == "mention":
            stats["mention"] += 1
            if not config.SAVE_MENTIONS:
                continue
        else:
            stats["subject"] += 1

        # 3단계: 감성 (앞단을 통과한 소수에만)
        sent_label, sent_score = sentiment.analyze(
            title, content, config.SENTIMENT_NEUTRAL_BAND)

        record = _build_record(politician, art, uhash, dis, rel,
                               sent_label, sent_score)
        try:
            db.insert_article(record)
            stats["saved"] += 1
            if (config.TELEGRAM_NOTIFY and rel["label"] == "subject"):
                _notify(politician, title, url, sent_label)
        except Exception as e:
            msg = str(e)
            if "duplicate" in msg.lower() or "23505" in msg:
                stats["dup"] += 1
            else:
                print(f"[warn] 저장 실패: {e}")

    db.update_last_crawled(pid)
    return stats


def _build_record(politician, art, uhash, dis, rel, sent_label, sent_score):
    published = art.get("published_at") or datetime.now(timezone.utc).isoformat()
    content = art.get("content") or ""
    return {
        "title": art.get("title") or "",
        "summary": content[:300] if content else None,
        "content": content or None,
        "politician_id": politician.get("id"),
        "politician_name": politician.get("name"),
        "politician_position": politician.get("position") or politician.get("party") or "정치인",
        "region": politician.get("region") or "대한민국",
        "category": _news_category(politician),
        "source": art.get("source") or "naver",
        "source_url": art.get("url"),
        "published_at": published,
        # 감성
        "sentiment": sent_label,
        "sentiment_label": _SENT_KO.get(sent_label, "중립"),
        "sentiment_score": sent_score,
        # 깔때기 메타
        "url_hash": uhash,
        "mention_count": rel["mention_count"],
        "disambiguation_score": dis["score"],
        "disambiguation_passed": dis["passed"],
        "relevance_score": rel["score"],
        "relevance_label": rel["label"],
        "is_relevant": rel["is_relevant"],
        "classified_by": config.CLASSIFIER_VERSION,
    }


def _notify(politician, title, url, sent_label):
    import requests
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    emoji = {"positive": "🟢", "neutral": "⚪", "negative": "🔴"}.get(sent_label, "⚪")
    text = f"{emoji} [{politician.get('name')}] {title}\n🔗 {url}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"[warn] 텔레그램 알림 실패: {e}")

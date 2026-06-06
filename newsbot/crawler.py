"""뉴스 수집기.

우선순위:
    1) 네이버 검색 OpenAPI (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 있을 때) — 안정적
    2) 네이버 뉴스 검색 HTML 스크래핑 폴백 — 키 없이 동작하지만 깨지기 쉬움

각 기사: {title, content(=요약/본문), url, source, published_at}
content 는 관련성·감성 분석의 입력이 된다. FETCH_FULL_CONTENT=true 면 본문 페이지까지 받아온다.
"""
import datetime as dt

import requests
from bs4 import BeautifulSoup

from . import config
from .nlp.text import normalize

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
_TIMEOUT = 10


def search(query, display=None):
    display = display or config.ARTICLES_PER_POLITICIAN
    if config.NAVER_CLIENT_ID and config.NAVER_CLIENT_SECRET:
        try:
            return _search_naver_api(query, display)
        except Exception as e:
            print(f"[warn] 네이버 API 검색 실패, 스크래핑으로 폴백: {e}")
    return _search_naver_scrape(query, display)


def _search_naver_api(query, display):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": min(display, 100), "sort": "date"}
    r = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    items = r.json().get("items", [])
    out = []
    for it in items:
        out.append({
            "title": normalize(it.get("title")),
            "content": normalize(it.get("description")),
            "url": it.get("originallink") or it.get("link"),
            "source": _domain(it.get("originallink") or it.get("link")),
            "published_at": _parse_rfc822(it.get("pubDate")),
        })
    return out


def _search_naver_scrape(query, display):
    url = "https://search.naver.com/search.naver"
    r = requests.get(url, headers=_HEADERS,
                     params={"where": "news", "query": query}, timeout=_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select(".news_tit")[:display]:
        out.append({
            "title": normalize(a.get("title") or a.get_text()),
            "content": "",
            "url": a.get("href"),
            "source": _domain(a.get("href")),
            "published_at": None,
        })
    return out


def fetch_full_content(url):
    """본문 페이지에서 텍스트 best-effort 추출 (실패해도 빈 문자열)."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for sel in ("article", "#dic_area", "#articleBodyContents",
                    ".article_body", "#newsct_article"):
            node = soup.select_one(sel)
            if node:
                return normalize(node.get_text(" "))
        ps = soup.find_all("p")
        return normalize(" ".join(p.get_text(" ") for p in ps[:40]))
    except Exception as e:
        print(f"[warn] 본문 수집 실패 ({url}): {e}")
        return ""


def _domain(url):
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        return (urlparse(url).netloc or "").replace("www.", "")
    except Exception:
        return ""


def _parse_rfc822(value):
    if not value:
        return None
    try:
        return dt.datetime.strptime(
            value, "%a, %d %b %Y %H:%M:%S %z").isoformat()
    except Exception:
        return None

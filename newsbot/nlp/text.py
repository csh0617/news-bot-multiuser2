"""한국어 텍스트 처리 공용 헬퍼 (형태소 분석기 없이 가볍게)."""
import re

_WORD_RE = re.compile(r"[가-힣]+|[A-Za-z]+|[0-9]+")
_SPACE_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")

# 이름 뒤에 붙는 주격/주제 조사 → '문장의 주어'일 가능성 신호
SUBJECT_PARTICLES = ("은", "는", "이", "가", "께서", "께선")
# 호칭(직책)이 이름 뒤에 오면 주체 신호 강화
TITLE_SUFFIXES = (
    "대통령", "의원", "장관", "지사", "시장", "군수", "구청장", "위원장",
    "대표", "총리", "차관", "청장", "교육감", "후보", "당선인", "원내대표",
    "최고위원", "의장", "부의장", "비서실장", "수석",
)


def strip_html(text):
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    # 네이버 API가 돌려주는 엔티티 정리
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&nbsp;", " "), ("&#39;", "'")):
        text = text.replace(a, b)
    return text


def normalize(text):
    if not text:
        return ""
    return _SPACE_RE.sub(" ", strip_html(text)).strip()


def tokens(text):
    return _WORD_RE.findall(text or "")


def token_set(text):
    return set(tokens(text))


def split_sentences(text):
    if not text:
        return []
    # 줄바꿈 + 한국어 종결(다/요/음/함 + 구두점) + 일반 구두점 기준
    parts = re.split(r"(?<=[다요음함죠])[.!?]?\s+|[.!?\n]+", text)
    return [p.strip() for p in parts if p and p.strip()]


def find_name_spans(text, name, aliases=None):
    """본문에서 이름/별칭이 등장하는 (start, end) 위치 목록."""
    if not text or not name:
        return []
    needles = [name] + list(aliases or [])
    spans = []
    for n in needles:
        if not n:
            continue
        start = 0
        while True:
            idx = text.find(n, start)
            if idx == -1:
                break
            spans.append((idx, idx + len(n)))
            start = idx + len(n)
    return sorted(set(spans))


def is_subject_mention(text, end_idx):
    """이름 직후 문자열을 보고 '주어/직책'으로 쓰였는지 판단."""
    tail = text[end_idx:end_idx + 8]
    if tail[:1] in (" ", ""):  # '이재명 대통령' 처럼 공백 후 직책
        nxt = tail.strip()
        if nxt.startswith(TITLE_SUFFIXES):
            return True
    if tail.startswith(SUBJECT_PARTICLES):
        return True
    for suf in TITLE_SUFFIXES:
        if tail.startswith(suf):
            return True
    return False

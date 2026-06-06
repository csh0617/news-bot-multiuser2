"""동명이인 구분 — 정치인 프로필 앵커 매칭 (로컬, 외부 API 0회).

아이디어:
    - 대상 정치인의 소속/지역/직책/경력에서 '앵커 키워드'를 뽑는다 (positive).
    - 같은 이름을 가진 *다른* 정치인들의 고유 앵커는 'negative'로 쓴다.
      → 기사에 상대편 앵커가 나오면 동명이인일 확률이 높다고 보고 감점.
    - 점수가 임계값 이상이면 '이 기사는 대상 정치인의 것'으로 통과.
"""
from .text import tokens, normalize

STRONG_W = 1.5   # 정당, 직책(지사/시장/대통령 등) 등 강한 식별자
WEAK_W = 0.5     # 지역, 선거구, 위원회, 경력 토큰 등
NEG_W = 1.2      # 동명이인 고유 앵커
TITLE_MULT = 1.5  # 제목에 등장하면 가중

CATEGORY_WORDS = {
    "president": ["대통령"],
    "congressman": ["국회의원"],
    "cabinet": ["장관"],
    "mayor": ["시장"],
    "local_mayor": ["시장", "군수", "구청장"],
    "metro_governor": ["도지사", "지사"],
    "metropolitan_governor": ["도지사", "지사"],
    "metropolitan_council": ["광역의원", "도의원", "시의원"],
    "local_council": ["기초의원", "구의원", "시의원", "군의원"],
    "education": ["교육감"],
    "superintendent": ["교육감"],
}

DUTY_SUFFIXES = ("지사", "시장", "군수", "구청장", "장관", "차관", "청장",
                 "교육감", "의원", "대표", "총리", "위원장", "의장", "대통령")

_STOP = {"대한민국", "현재", "전국", "선거구", "의회의원", "의회"}


def _duty_tokens(text):
    """자유 텍스트(경력 등)에서 직책성 토큰만 추출."""
    out = []
    for tok in tokens(text or ""):
        if len(tok) >= 3 and tok.endswith(DUTY_SUFFIXES) and tok not in _STOP:
            out.append(tok)
    return out


def _field_tokens(text, min_len=2):
    return [t for t in tokens(text or "") if len(t) >= min_len and t not in _STOP]


def build_profile(politician, same_name_others=None):
    """politician(dict) + 동명이인 목록으로 앵커 프로필 생성."""
    name = politician.get("name") or ""
    strong, weak, negative = set(), set(), set()

    party = (politician.get("party") or "").strip()
    if party:
        strong.add(party)

    for w in CATEGORY_WORDS.get(politician.get("category") or "", []):
        strong.add(w)
    for w in _field_tokens(politician.get("position")):
        (strong if w.endswith(DUTY_SUFFIXES) else weak).add(w)
    for w in _duty_tokens(politician.get("career")):
        strong.add(w)

    # 지역/선거구/위원회/경력 일반 토큰 → 약한 앵커
    region_main = (politician.get("region") or "").replace("특별자치도", "") \
        .replace("특별시", "").replace("광역시", "").replace("도", "").strip()
    if len(region_main) >= 2:
        weak.add(region_main)
    for f in ("district", "committees"):
        for w in _field_tokens(politician.get(f)):
            weak.add(w)
    for w in (politician.get("aliases") or []):
        if w:
            weak.add(w)
    for w in (politician.get("positive_keywords") or []):
        if w:
            strong.add(w)
    for w in (politician.get("negative_keywords") or []):
        if w:
            negative.add(w)

    # 동명이인의 고유 식별자를 negative 로
    for other in (same_name_others or []):
        cands = set()
        if other.get("party"):
            cands.add(other["party"].strip())
        for w in CATEGORY_WORDS.get(other.get("category") or "", []):
            cands.add(w)
        cands.update(_field_tokens(other.get("district")))
        cands.update(_field_tokens(other.get("position")))
        for c in cands:
            if c and c not in strong and c not in weak and c != name:
                negative.add(c)

    # 이름 자체나 빈 값은 앵커에서 제외
    for s in (strong, weak, negative):
        s.discard(name)
        s.discard("")
    return {"name": name, "strong": strong, "weak": weak, "negative": negative}


def score(title, body, profile, threshold=1.0):
    title_n = normalize(title)
    body_n = normalize(body)

    matched_pos, matched_neg = [], []
    total = 0.0

    def hit(anchor, weight):
        nonlocal total
        in_t = anchor in title_n
        in_b = anchor in body_n
        if in_t or in_b:
            total += weight * (TITLE_MULT if in_t else 1.0)
            matched_pos.append(anchor)

    for a in profile["strong"]:
        hit(a, STRONG_W)
    for a in profile["weak"]:
        hit(a, WEAK_W)

    for a in profile["negative"]:
        if a in title_n or a in body_n:
            total -= NEG_W
            matched_neg.append(a)

    passed = total >= threshold
    return {
        "score": round(total, 3),
        "passed": passed,
        "matched_positive": matched_pos,
        "matched_negative": matched_neg,
    }

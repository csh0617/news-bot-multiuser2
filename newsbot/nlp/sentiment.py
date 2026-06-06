"""감성 분류 (긍정/중립/부정) — 로컬 감성사전 기반, 외부 API 0회.

방식:
    1) 제목/본문을 토큰화하고, 각 토큰이 감성사전 표제어로 시작하는지(부분일치) 검사.
    2) 바로 앞 토큰이 부정어면 극성을 반전(예: '지지 안 한다' → 부정).
    3) 제목 가중치를 본문보다 높게 둔다(제목이 논조를 압축).
    4) 정규화 점수가 중립 데드밴드 안이면 'neutral'.

반환: (label, score)  score ∈ [-1, 1]  (음수=부정, 양수=긍정)
"""
from . import lexicon_ko as lex
from .text import tokens, normalize

TITLE_WEIGHT = 2.0
BODY_WEIGHT = 1.0


def _lemma_polarity(tok):
    """토큰이 긍/부정 표제어로 시작하면 +1/-1, 아니면 0."""
    if len(tok) < lex.MIN_LEMMA_LEN:
        return 0
    for lemma in lex.POSITIVE:
        if tok.startswith(lemma):
            return 1
    for lemma in lex.NEGATIVE:
        if tok.startswith(lemma):
            return -1
    return 0


def _score_tokens(toks):
    pos = neg = 0
    for i, tok in enumerate(toks):
        pol = _lemma_polarity(tok)
        if pol == 0:
            continue
        # 직전 토큰이 부정어면 극성 반전
        prev = toks[i - 1] if i > 0 else ""
        if prev.startswith(lex.NEGATORS) and len(prev) <= 3:
            pol = -pol
        if pol > 0:
            pos += 1
        else:
            neg += 1
    return pos, neg


def analyze(title, body, neutral_band=0.12):
    title_toks = tokens(normalize(title))
    body_toks = tokens(normalize(body))

    tp, tn = _score_tokens(title_toks)
    bp, bn = _score_tokens(body_toks)

    pos = tp * TITLE_WEIGHT + bp * BODY_WEIGHT
    neg = tn * TITLE_WEIGHT + bn * BODY_WEIGHT
    total = pos + neg

    if total == 0:
        return "neutral", 0.0

    score = (pos - neg) / total  # [-1, 1]
    if abs(score) < neutral_band:
        return "neutral", round(score, 3)
    return ("positive" if score > 0 else "negative"), round(score, 3)

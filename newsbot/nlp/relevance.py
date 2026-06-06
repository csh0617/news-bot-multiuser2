"""관련성 분류 — '주체 기사' vs '단순 언급' vs '무관' (로컬, 외부 API 0회).

신호:
    - 제목에 이름 등장        → 주체일 확률 매우 높음 (가장 강함)
    - 첫 문단(리드)에 등장     → 주체 신호
    - 이름이 주어/직책으로 쓰임 → 주체 신호 (조사 은/는/이/가, 'OO 대통령')
    - 언급 빈도(문장 수 대비)   → 높을수록 주체
    - 나열형 기사(여러 인물 ··· 단순 거론) → 감점
"""
from .text import find_name_spans, split_sentences, is_subject_mention, normalize

LIST_MARKERS = ("·", "ㆍ", "…", "▲", "△", "○", "ㅇ")


def classify(title, body, name, aliases=None,
             disambiguation_passed=True,
             subject_threshold=0.45, mention_threshold=0.15):
    title_n = normalize(title)
    body_n = normalize(body)
    aliases = aliases or []

    title_spans = find_name_spans(title_n, name, aliases)
    body_spans = find_name_spans(body_n, name, aliases)
    mention_count = len(title_spans) + len(body_spans)

    sentences = split_sentences(body_n)
    lead = " ".join(sentences[:2])

    title_hit = len(title_spans) > 0
    lead_hit = bool(find_name_spans(lead, name, aliases))
    subject_hit = any(is_subject_mention(title_n, e) for _, e in title_spans) \
        or any(is_subject_mention(body_n, e) for _, e in body_spans)

    density = mention_count / max(1, len(sentences))

    # 나열형 기사 감점: 본문에 리스트 마커가 많고 언급은 1회뿐이면 단순 거론일 확률↑
    list_markers = sum(body_n.count(m) for m in LIST_MARKERS)
    roundup_penalty = 0.2 if (list_markers >= 5 and mention_count <= 1) else 0.0

    score = 0.0
    if title_hit:
        score += 0.5
    if subject_hit:
        score += 0.25
    if lead_hit:
        score += 0.15
    score += min(0.2, density * 0.1)
    score = max(0.0, min(1.0, score - roundup_penalty))

    if not disambiguation_passed:
        label = "unrelated"
    elif title_hit or score >= subject_threshold or (subject_hit and lead_hit):
        label = "subject"
    elif mention_count > 0 and score >= mention_threshold:
        label = "mention"
    elif mention_count > 0:
        label = "mention"
    else:
        label = "unrelated"

    return {
        "score": round(score, 3),
        "label": label,
        "mention_count": mention_count,
        "is_relevant": label == "subject",
        "title_hit": title_hit,
        "subject_hit": subject_hit,
        "lead_hit": lead_hit,
    }

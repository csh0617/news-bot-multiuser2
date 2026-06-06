"""국회의원(현직 300명) 공식 데이터 적재 스크립트.

검증된 방식 (2단계 공식 출처 결합):
  1) 현직 명단·인적사항: 열린국회정보 'nwvrqwxyaytdsfvhu' (국회의원 인적사항) → 정확히 현직 300명.
     정당(POLY_NM)·선거구(ORIG_NM)·약력(MEM_TITLE)·생년월일·연락처 제공.
  2) 프로필 사진: 'ALLNAMEMBER'(인적정보 통합)의 NAAS_PIC 를 의원코드(MONA_CD==NAAS_CD)로 매칭.
     (현직 사진 URL은 /openassm/new/{해시}.jpg 형태라 코드로 URL 추측이 불가 → 반드시 NAAS_PIC 사용.)

인터넷이 되는 곳(Render 셸/PC)에서 실행하세요. 정부 사이트 차단 환경에서는 동작하지 않습니다.

필요 환경변수:
    NATIONAL_ASSEMBLY_API_KEY   open.assembly.go.kr 인증키 (필수)
    SUPABASE_URL                (필수)
    SUPABASE_SERVICE_ROLE_KEY   (권장; 없으면 SUPABASE_ANON_KEY)

사용:
    python -m scripts.import_assembly_members --inspect   # 응답 필드 확인
    python -m scripts.import_assembly_members --dry-run    # 매핑 미리보기 (DB 미반영)
    python -m scripts.import_assembly_members --load       # 실제 upsert (assembly_code 기준 멱등)
"""
import argparse
import json
import os
import re
import sys

import requests

BASE = "https://open.assembly.go.kr/portal/openapi"
ROSTER_SVC = "nwvrqwxyaytdsfvhu"   # 현직 국회의원 인적사항 (300명)
ALLMEMBER_SVC = "ALLNAMEMBER"      # 인적정보 통합 (사진 NAAS_PIC 보유)

SIDO = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도",
}


def api_key():
    k = os.environ.get("NATIONAL_ASSEMBLY_API_KEY")
    if not k:
        sys.exit("[!] NATIONAL_ASSEMBLY_API_KEY 가 필요합니다. open.assembly.go.kr 인증키 발급.")
    return k


def fetch(service, p_index=1, p_size=300, **extra):
    params = {"KEY": api_key(), "Type": "json", "pIndex": p_index, "pSize": p_size}
    params.update(extra)
    r = requests.get(f"{BASE}/{service}", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    body = data.get(service)
    if not body:
        raise RuntimeError(f"예상치 못한 응답: {json.dumps(data, ensure_ascii=False)[:400]}")
    rows = []
    for part in body:
        if isinstance(part, dict) and "row" in part:
            rows = part["row"]
    return rows


def fetch_all(service, p_size=1000, max_pages=20):
    rows, page = [], 1
    while page <= max_pages:
        page_rows = fetch(service, page, p_size)
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < p_size:
            break
        page += 1
    return rows


def photo_map():
    """ALLNAMEMBER 전체에서 의원코드 → 사진 URL 매핑."""
    m = {}
    for r in fetch_all(ALLMEMBER_SVC):
        pic = (r.get("NAAS_PIC") or "").strip()
        if r.get("NAAS_CD") and pic:
            m[r["NAAS_CD"]] = pic
    return m


def _region(district, is_pr):
    if is_pr or not district:
        return "대한민국"
    return SIDO.get(district.split()[0], "대한민국")


def _birth(v):
    v = (v or "").strip()
    return v if re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None


def _election_count(reele):
    reele = (reele or "").strip()
    if reele == "초선":
        return 1
    if reele == "재선":
        return 2
    digits = re.sub(r"[^0-9]", "", reele)
    return int(digits) if digits else None


def map_member(m, photos):
    div = (m.get("ELECT_GBN_NM") or "").strip()
    district = (m.get("ORIG_NM") or "").strip()
    is_pr = ("비례" in div) or not district
    pic = photos.get(m.get("MONA_CD"))
    return {
        "assembly_code": m.get("MONA_CD"),
        "name": (m.get("HG_NM") or "").strip(),
        "hanja": (m.get("HJ_NM") or "").strip() or None,
        "party": (m.get("POLY_NM") or "").strip() or None,
        "district": district or "비례대표",
        "region": _region(district, is_pr),
        "position": "제22대 국회의원",
        "category": "congressman",
        "committees": (m.get("CMITS") or m.get("CMIT_NM") or "").strip() or None,
        "career": (m.get("MEM_TITLE") or "").strip() or None,
        "birth_date": _birth(m.get("BTH_DATE")),
        "election_count": _election_count(m.get("REELE_GBN_NM")),
        "contact_email": (m.get("E_MAIL") or "").strip() or None,
        "contact_phone": (m.get("TEL_NO") or "").strip() or None,
        "office_address": (m.get("ASSEM_ADDR") or "").strip() or None,
        "profile_image_url": pic,
        "profile_image": pic,
    }


def supabase():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY"))
    if not (url and key):
        sys.exit("[!] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 가 필요합니다.")
    return create_client(url, key)


def upsert(records):
    sb = supabase()
    res = sb.table("politicians").select("assembly_code").not_.is_(
        "assembly_code", "null").execute()
    existing = {row["assembly_code"] for row in (res.data or [])}
    to_insert = [r for r in records if r["assembly_code"] not in existing]
    to_update = [r for r in records if r["assembly_code"] in existing]
    for i in range(0, len(to_insert), 100):
        sb.table("politicians").insert(to_insert[i:i + 100]).execute()
    for r in to_update:
        sb.table("politicians").update(r).eq("assembly_code", r["assembly_code"]).execute()
    return len(to_insert), len(to_update)


def main():
    ap = argparse.ArgumentParser(description="국회의원 현직 300명 공식 데이터 적재")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--load", action="store_true")
    args = ap.parse_args()

    roster = fetch(ROSTER_SVC, 1, 300)
    print(f"[i] 현직 의원 {len(roster)}명 수신")

    if args.inspect:
        print("\n=== 현직 서비스 필드 ===")
        print(list(roster[0].keys()))
        print(json.dumps(roster[0], ensure_ascii=False, indent=2))
        return

    photos = photo_map()
    print(f"[i] 사진 매핑 {len(photos)}건 확보")
    mapped = [map_member(m, photos) for m in roster
              if m.get("MONA_CD") and m.get("HG_NM")]
    with_pic = sum(1 for r in mapped if r["profile_image_url"])
    print(f"[i] 매핑 {len(mapped)}명 / 사진 {with_pic}명")

    if args.dry_run or not args.load:
        print(json.dumps(mapped[:3], ensure_ascii=False, indent=2))
        if not args.load:
            print("\n(미반영) 실제 적재는 --load")
        return

    ins, upd = upsert(mapped)
    print(f"[✓] 적재 완료: 신규 {ins}명, 갱신 {upd}명 (총 {len(mapped)})")


if __name__ == "__main__":
    main()

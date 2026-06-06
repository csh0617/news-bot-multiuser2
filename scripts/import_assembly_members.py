"""국회의원(현직 300명) 공식 데이터 적재 스크립트.

출처: 열린국회정보 OpenAPI 'ALLNAMEMBER' (국회의원 인적정보 통합)
      https://open.assembly.go.kr/portal/openapi/main.do
      → 이름/정당/선거구/위원회/약력/생년월일/연락처 + 사진(NAAS_PIC) 공식 제공.

이 스크립트는 인터넷이 되는 곳(Render 셸 또는 PC)에서 실행하세요.
(작업 샌드박스에서는 정부 사이트 접속이 차단됩니다.)

필요 환경변수:
    NATIONAL_ASSEMBLY_API_KEY   open.assembly.go.kr 인증키 (필수)
    SUPABASE_URL                (필수)
    SUPABASE_SERVICE_ROLE_KEY   (권장) 없으면 SUPABASE_ANON_KEY 도 가능(RLS 꺼진 상태에서)

사용:
    python -m scripts.import_assembly_members --inspect    # 응답 필드 실제 확인 (먼저 이걸로 검증!)
    python -m scripts.import_assembly_members --dry-run     # 매핑 결과 미리보기 (DB 미반영)
    python -m scripts.import_assembly_members --load        # 실제 upsert (assembly_code 기준 멱등)
"""
import argparse
import json
import os
import sys

import requests

API_URL = "https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER"
DEFAULT_ERA = "제22대"

# 시·도 약칭 → 정식 명칭 (region 컬럼용)
SIDO = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
    "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
    "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
    "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
    "경남": "경상남도", "제주": "제주특별자치도",
}

# ALLNAMEMBER 필드명 (open.assembly.go.kr 공식). --inspect 로 실제 확인 가능.
F = {
    "code": "NAAS_CD", "name": "NAAS_NM", "hanja": "NAAS_CH_NM",
    "party": "PLPT_NM", "district": "ELECD_NM", "district_div": "ELECD_DIV_NM",
    "committee": "BLNG_CMIT_NM", "eras": "GTELT_ERACO", "reelect": "RLCT_DIV_NM",
    "birth": "BIRDY_DT", "career": "BRF_HST", "tel": "NAAS_TEL_NO",
    "email": "NAAS_EMAIL_ADDR", "office": "OFFM_RNUM_NO", "pic": "NAAS_PIC",
}


def api_key():
    k = os.environ.get("NATIONAL_ASSEMBLY_API_KEY")
    if not k:
        sys.exit("[!] NATIONAL_ASSEMBLY_API_KEY 환경변수가 필요합니다. "
                 "open.assembly.go.kr 에서 인증키를 발급받으세요.")
    return k


def fetch_all(page_size=300):
    """ALLNAMEMBER 전체 행을 페이지네이션으로 수집."""
    key, rows, page = api_key(), [], 1
    while True:
        params = {"KEY": key, "Type": "json", "pIndex": page, "pSize": page_size}
        r = requests.get(API_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        body = data.get("ALLNAMEMBER")
        if not body:
            # 인증 실패 등은 RESULT 메시지로 옴
            raise RuntimeError(f"예상치 못한 응답: {json.dumps(data, ensure_ascii=False)[:400]}")
        page_rows = []
        for part in body:
            if isinstance(part, dict) and "row" in part:
                page_rows = part["row"]
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
        page += 1
    return rows


def _last_segment(value):
    if not value:
        return None
    for sep in ("/", ",", "|"):
        if sep in value:
            value = value.split(sep)[-1]
    return value.strip() or None


def _region(district):
    if not district:
        return "대한민국"
    head = district.split()[0]
    for k, v in SIDO.items():
        if head.startswith(k):
            return v
    return "대한민국"


def _birth(value):
    if not value:
        return None
    d = value.replace(".", "-").replace("/", "-").strip()
    if len(d) == 8 and d.isdigit():
        d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d if len(d) == 10 and d[4] == "-" else None


def map_member(m, era):
    div = (m.get(F["district_div"]) or "").strip()
    district = (m.get(F["district"]) or "").strip()
    is_pr = ("비례" in div) or not district
    eras = m.get(F["eras"]) or ""
    return {
        "assembly_code": m.get(F["code"]),
        "name": (m.get(F["name"]) or "").strip(),
        "hanja": (m.get(F["hanja"]) or "").strip() or None,
        "party": _last_segment(m.get(F["party"])),
        "district": "비례대표" if is_pr else district,
        "region": "대한민국" if is_pr else _region(district),
        "position": f"{era} 국회의원",
        "category": "congressman",
        "committees": (m.get(F["committee"]) or "").strip() or None,
        "career": (m.get(F["career"]) or "").strip() or None,
        "birth_date": _birth(m.get(F["birth"])),
        "election_count": len([e for e in eras.split(",") if e.strip()]) or None,
        "contact_email": (m.get(F["email"]) or "").strip() or None,
        "contact_phone": (m.get(F["tel"]) or "").strip() or None,
        "office_address": (m.get(F["office"]) or "").strip() or None,
        "profile_image_url": (m.get(F["pic"]) or "").strip() or None,
        "profile_image": (m.get(F["pic"]) or "").strip() or None,
    }


def supabase():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY"))
    if not (url and key):
        sys.exit("[!] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.")
    return create_client(url, key)


def upsert(records):
    """assembly_code 기준으로 신규는 insert, 기존은 update (멱등)."""
    sb = supabase()
    existing = set()
    res = sb.table("politicians").select("assembly_code").not_.is_(
        "assembly_code", "null").execute()
    for row in (res.data or []):
        existing.add(row["assembly_code"])

    to_insert = [r for r in records if r["assembly_code"] not in existing]
    to_update = [r for r in records if r["assembly_code"] in existing]

    for i in range(0, len(to_insert), 100):
        sb.table("politicians").insert(to_insert[i:i + 100]).execute()
    for r in to_update:
        sb.table("politicians").update(r).eq(
            "assembly_code", r["assembly_code"]).execute()
    return len(to_insert), len(to_update)


def main():
    ap = argparse.ArgumentParser(description="국회의원 공식 데이터 적재")
    ap.add_argument("--inspect", action="store_true", help="응답 원본 필드 확인")
    ap.add_argument("--dry-run", action="store_true", help="매핑만 미리보기 (DB 미반영)")
    ap.add_argument("--load", action="store_true", help="실제 upsert")
    ap.add_argument("--era", default=DEFAULT_ERA, help="대상 대수 (기본 제22대)")
    args = ap.parse_args()

    rows = fetch_all()
    print(f"[i] ALLNAMEMBER 전체 {len(rows)}건 수신")

    if args.inspect:
        print("\n=== 첫 레코드 필드명 ===")
        print(list(rows[0].keys()))
        print("\n=== 샘플 2건 ===")
        print(json.dumps(rows[:2], ensure_ascii=False, indent=2))
        return

    current = [m for m in rows if args.era in (m.get(F["eras"]) or "")]
    mapped = [map_member(m, args.era) for m in current]
    mapped = [r for r in mapped if r["assembly_code"] and r["name"]]
    with_pic = sum(1 for r in mapped if r["profile_image_url"])

    print(f"[i] {args.era} 대상 {len(mapped)}명 / 사진 보유 {with_pic}명")
    if not mapped:
        sys.exit("[!] 대상 0명. --inspect 로 필드명(GTELT_ERACO 등)을 먼저 확인하세요.")

    if args.dry_run or not args.load:
        print("\n=== 매핑 미리보기 (앞 3명) ===")
        print(json.dumps(mapped[:3], ensure_ascii=False, indent=2))
        if not args.load:
            print("\n(미반영) 실제 적재는 --load")
        return

    ins, upd = upsert(mapped)
    print(f"[✓] 적재 완료: 신규 {ins}명, 갱신 {upd}명 (총 {len(mapped)})")


if __name__ == "__main__":
    main()

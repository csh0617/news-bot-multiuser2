"""백그라운드 워커 / CLI 진입점.

사용 예:
    python -m newsbot.worker --once --names 이재명          # 1회 실행, 특정 인물
    python -m newsbot.worker --once                         # 1회, auto_crawl 대상 전체
    python -m newsbot.worker                                # 루프(LOOP_INTERVAL_SECONDS 주기)
"""
import argparse
import time
import traceback

from . import config, db, pipeline


def run_once(names=None):
    politicians = db.get_target_politicians(names=names)
    if not politicians:
        print("[i] 크롤링 대상 정치인이 없습니다. "
              "(politicians.auto_crawl_enabled=true 로 지정하거나 --names 사용)")
        return

    totals = {"found": 0, "saved": 0, "dup": 0, "unrelated": 0,
              "mention": 0, "subject": 0}
    for p in politicians:
        try:
            s = pipeline.process_politician(p)
            for k in totals:
                totals[k] += s.get(k, 0)
            print(f"  [{p.get('name')}] 수집 {s['found']} → 저장 {s['saved']} "
                  f"(주체 {s['subject']}, 언급 {s['mention']}, "
                  f"무관 {s['unrelated']}, 중복 {s['dup']}, "
                  f"동명이인 {s['homonym_collisions']})")
        except Exception as e:
            print(f"  [에러] {p.get('name')}: {e}")
            traceback.print_exc()

    db.log_crawl("naver", totals["found"], totals["saved"])
    print(f"[✓] 합계: 수집 {totals['found']} / 저장 {totals['saved']} "
          f"(주체 {totals['subject']}, 언급 {totals['mention']}, 무관 {totals['unrelated']})")


def main():
    ap = argparse.ArgumentParser(description="정치인 뉴스 크롤링·분류 워커")
    ap.add_argument("--once", action="store_true", help="1회만 실행하고 종료")
    ap.add_argument("--names", nargs="*", help="대상 정치인 이름(공백 구분)")
    args = ap.parse_args()

    print("[*] 정치인 뉴스 크롤링·분류 워커 시작")
    if args.once:
        run_once(args.names)
        return

    while True:
        print("\n[🔁] 루프 시작 " + "=" * 30)
        try:
            run_once(args.names)
        except Exception as e:
            print(f"[에러] 루프 실패: {e}")
            traceback.print_exc()
        print(f"[💤] {config.LOOP_INTERVAL_SECONDS}초 대기")
        time.sleep(config.LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

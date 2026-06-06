"""백그라운드 워커 진입점 (start.sh 에서 실행).

기존 users.json 기반 단순 전송 로직을 대체한다.
실제 파이프라인은 newsbot 패키지에 있다.
"""
from newsbot.worker import main

if __name__ == "__main__":
    main()

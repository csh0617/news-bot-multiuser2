#!/bin/bash
# 뉴스 전송용 백그라운드 워커 실행
nohup python app.py > worker.log 2>&1 &

# 웹 서버 실행 (포그라운드로 실행돼야 Render가 감지함)
python web.py


#!/bin/bash
# 웹 서버 + 뉴스봇 동시에 실행
python3 web.py &  # 웹 서비스 백그라운드 실행
python3 app.py    # 뉴스봇 실행

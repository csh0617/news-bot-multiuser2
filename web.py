"""상태 대시보드 + 헬스체크 + 수동 크롤 트리거 (Render 가 감지하는 웹 포트).

기존 users.json 등록 폼은 Supabase 기반으로 전환되며 제거되었다.
실제 크롤링/분류는 newsbot 워커(app.py)가 담당한다.
"""
import os
import threading

from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
CRAWL_TRIGGER_TOKEN = os.environ.get("CRAWL_TRIGGER_TOKEN")


@app.route("/health")
def health():
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    stats = _dashboard_stats()
    return render_template("index.html", **stats)


@app.route("/crawl", methods=["POST"])
def crawl():
    """수동 트리거. CRAWL_TRIGGER_TOKEN 이 설정된 경우에만 허용."""
    if not CRAWL_TRIGGER_TOKEN:
        return jsonify({"result": "disabled",
                        "message": "CRAWL_TRIGGER_TOKEN 미설정"}), 403
    token = request.headers.get("X-Trigger-Token") or request.form.get("token")
    if token != CRAWL_TRIGGER_TOKEN:
        return jsonify({"result": "forbidden"}), 403

    names = request.form.getlist("names") or None
    from newsbot.worker import run_once
    threading.Thread(target=run_once, kwargs={"names": names},
                     daemon=True).start()
    return jsonify({"result": "started", "names": names})


def _dashboard_stats():
    try:
        from newsbot import db
        c = db.client()
        total = c.table("news_articles").select("id", count="exact").execute().count or 0
        by = {}
        for s in ("positive", "neutral", "negative"):
            by[s] = c.table("news_articles").select(
                "id", count="exact").eq("sentiment", s).execute().count or 0
        last = c.table("crawling_logs").select("*").order(
            "crawled_at", desc=True).limit(1).execute().data
        recent = c.table("news_articles").select(
            "title,politician_name,sentiment,source_url,published_at"
        ).eq("relevance_label", "subject").order(
            "created_at", desc=True).limit(15).execute().data or []
        return {"total": total, "by": by,
                "last_log": last[0] if last else None, "recent": recent,
                "error": None}
    except Exception as e:
        return {"total": 0, "by": {}, "last_log": None, "recent": [],
                "error": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

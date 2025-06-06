from flask import Flask, request, render_template, jsonify
import json
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    try:
        name = request.form["name"]
        chat_id = request.form["chat_id"]
        token = request.form["telegram_token"]
        keywords = request.form["keywords"].split(",")

        if not os.path.exists(USERS_FILE):
            users = []
        else:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)

        for user in users:
            if user["chat_id"] == chat_id:
                user["name"] = name
                user["telegram_token"] = token
                user["keywords"] = keywords
                break
        else:
            users.append({
                "name": name,
                "chat_id": chat_id,
                "telegram_token": token,
                "keywords": keywords
            })

        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

        return jsonify({"result": "success"})
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

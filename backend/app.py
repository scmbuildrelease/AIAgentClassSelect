from flask import Flask, jsonify
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

DATA_FILE = os.getenv("COURSES_FILE", "/data/courses.json")

@app.route("/courses")
def get_courses():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                courses = json.load(f).get("courses", {}).values()
            # keep the `title`/`link` keys the frontend already uses
            return jsonify([{**c, "title": c.get("name"), "link": c.get("detail_url") or c.get("source_url")}
                            for c in sorted(courses, key=lambda c: (c.get("provider") or "", c.get("name") or ""))])
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

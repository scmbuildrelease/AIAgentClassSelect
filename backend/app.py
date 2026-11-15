from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json

from activity_tracker.i18n import display
from activity_tracker.search import Glossary, search

app = Flask(__name__)
app.json.ensure_ascii = False  # send Chinese as UTF-8 text, not \uXXXX escapes
app.json.mimetype = "application/json; charset=utf-8"
CORS(app)

DATA_FILE = os.getenv("COURSES_FILE", "/data/courses.json")
SETTINGS_FILE = os.getenv("SETTINGS_FILE", "/app/config/settings.json")


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.route("/courses")
def get_courses():
    """?q= bilingual search (机器人 = robotics ...), ?lang=en|zh picks display titles.

    Every item keeps its original `name`/`description`; `display` is what to show for `lang`.
    Cross-language duplicates are returned once (the twin's text is in `translations`).
    """
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            courses = [c for c in json.load(f).get("courses", {}).values() if not c.get("duplicate_of")]
        settings = load_settings()
        query = request.args.get("q", "").strip()
        if query:
            labels = {k: " ".join([v.get("label", ""), v.get("short", "")])
                      for k, v in settings.get("categories", {}).items()}
            courses = search(courses, query, Glossary(settings.get("glossary", [])), labels)
        else:
            courses.sort(key=lambda c: (c.get("provider") or "", c.get("name") or ""))
        lang = request.args.get("lang", "en")
        # keep the `title`/`link` keys the frontend already uses
        return jsonify([{**c, "display": display(c, lang), "title": c.get("name"),
                         "link": c.get("detail_url") or c.get("source_url")} for c in courses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

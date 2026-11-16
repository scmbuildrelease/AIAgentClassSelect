from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
from datetime import date

from activity_tracker.agent import handle_chat
from activity_tracker.i18n import display
from activity_tracker.recommend import ADULT, PAST, audience, lifecycle, local_today
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


def load_courses(settings, include_all=False):
    """Tracked activities with lifecycle/audience; past and adult ones only with include_all."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        courses = [c for c in json.load(f).get("courses", {}).values() if not c.get("duplicate_of")]
    today = (date.fromisoformat(os.environ["TODAY"]) if os.getenv("TODAY")  # TODAY: pinned date for tests
             else local_today(tz=settings.get("timezone")))
    courses = [{**c, "lifecycle": lifecycle(c, today), "audience": audience(c)} for c in courses]
    if not include_all:
        courses = [c for c in courses if c["lifecycle"] != PAST and c["audience"] != ADULT]
    return courses, today


def course_item(c, lang):
    # keep the `title`/`link` keys the frontend already uses
    return {**c, "display": display(c, lang), "title": c.get("name"),
            "link": c.get("detail_url") or c.get("source_url")}


@app.route("/courses")
def get_courses():
    """?q= bilingual search (机器人 = robotics ...), ?lang=en|zh picks display titles.

    Every item keeps its original `name`/`description`; `display` is what to show for `lang`.
    Cross-language duplicates are returned once (the twin's text is in `translations`).
    Past activities and adult courses are left out unless ?all=1 (they stay in the data file).
    """
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    try:
        settings = load_settings()
        courses, _ = load_courses(settings, request.args.get("all") == "1")
        query = request.args.get("q", "").strip()
        if query:
            labels = {k: " ".join([v.get("label", ""), v.get("short", "")])
                      for k, v in settings.get("categories", {}).items()}
            courses = search(courses, query, Glossary(settings.get("glossary", [])), labels)
        else:
            courses.sort(key=lambda c: (c.get("provider") or "", c.get("name") or ""))
        lang = request.args.get("lang", "en")
        return jsonify([course_item(c, lang) for c in courses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/agent/chat", methods=["POST"])
def agent_chat():
    """Kids Activity AI Agent: {"message": "...", "lang": "en"} -> answer, activities, tools_used,
    agent_status, model, error. Uses the local Ollama model (AI_* environment variables); read-only."""
    body = request.get_json(silent=True) or {}
    try:
        settings = load_settings()
        courses, today = load_courses(settings) if os.path.exists(DATA_FILE) else ([], local_today())
        result, status = handle_chat(body.get("message"), courses, settings, today)
    except Exception as e:
        return jsonify({"answer": None, "activities": [], "tools_used": [], "agent_status": "error",
                        "model": os.getenv("AI_MODEL"), "error": str(e)}), 500
    lang = body.get("lang") if isinstance(body.get("lang"), str) else "en"
    return jsonify({**result, "activities": [course_item(c, lang) for c in result["activities"]]}), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

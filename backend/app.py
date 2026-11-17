from flask import Flask, jsonify, request
import os
import json
from datetime import date

from activity_tracker.agent import (AgentSettings, OllamaClient, OllamaError, age_matches, dates_overlap, handle_chat,
                                    location_matcher)
from activity_tracker.config import Config
from activity_tracker.i18n import display
from activity_tracker.recommend import ADULT, PAST, audience, lifecycle, local_today
from activity_tracker.search import Glossary, search

app = Flask(__name__)
app.json.ensure_ascii = False  # send Chinese as UTF-8 text, not \uXXXX escapes
app.json.mimetype = "application/json; charset=utf-8"
# No CORS headers: browsers reach this API only through the frontend server's same-origin proxy
# (frontend/package.json "proxy"). CORS is not an access control; see docs/INSTALL_MAC.md for the network setup.

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


def filter_courses(courses, args, settings):
    """Optional filters for GET /courses: age, city, category, from/to (YYYY-MM-DD). Raises ValueError.

    Uses the AI agent's filters: published ages (or an aggregator's age group) must include the age,
    the city must match, and published dates must overlap the range. Unpublished values do not match.
    """
    if args.get("age"):
        if not args["age"].isdigit() or not 0 <= int(args["age"]) <= 18:
            raise ValueError("age must be a whole number from 0 to 18")
        courses = [c for c in courses if age_matches(c, int(args["age"]), int(args["age"]))]
    if args.get("city"):
        here = location_matcher(args["city"], Config(settings, [], []).cities)
        courses = [c for c in courses if here(c)] if here else courses
    if args.get("category"):
        if args["category"] not in settings.get("categories", {}):
            raise ValueError(f"unknown category {args['category']!r}")
        courses = [c for c in courses if args["category"] in (c.get("categories") or [])]
    if args.get("from") or args.get("to"):
        start = date.fromisoformat(args.get("from") or args["to"])  # ValueError: not YYYY-MM-DD
        end = date.fromisoformat(args.get("to") or args["from"])
        if end < start:
            raise ValueError("'to' is before 'from'")
        courses = [c for c in courses if dates_overlap(c, start, end)]
    return courses


@app.route("/courses")
def get_courses():
    """?q= bilingual search (机器人 = robotics ...), ?lang=en|zh picks display titles.

    Every item keeps its original `name`/`description`; `display` is what to show for `lang`.
    Cross-language duplicates are returned once (the twin's text is in `translations`).
    Past activities and adult courses are left out unless ?all=1 (they stay in the data file).
    Optional filters: ?age=8&city=San Jose&category=stem&from=2026-12-01&to=2026-12-31.
    """
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    try:
        settings = load_settings()
        courses, _ = load_courses(settings, request.args.get("all") == "1")
        try:
            courses = filter_courses(courses, request.args, settings)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
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


@app.route("/options")
def get_options():
    """Filter choices for the UI: category keys/labels and the cities present in the current activities."""
    settings = load_settings()
    courses = load_courses(settings)[0] if os.path.exists(DATA_FILE) else []
    cities = {}
    for c in courses:
        if c.get("city"):
            cities[c["city"]] = cities.get(c["city"], 0) + 1
    return jsonify({"categories": {k: {"label": v.get("label"), "short": v.get("short")}
                                   for k, v in settings.get("categories", {}).items()},
                    "cities": [{"name": n, "count": k}
                               for n, k in sorted(cities.items(), key=lambda x: (-x[1], x[0]))]})


@app.route("/health")
def health():
    """Read-only status for the Settings screen and install checks: backend, data file, AI/Ollama."""
    data = {"available": os.path.exists(DATA_FILE), "activities": 0, "last_checked": None}
    if data["available"]:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                records = json.load(f).get("courses", {}).values()
            data["last_checked"] = max((c.get("last_checked") or "" for c in records), default=None) or None
            data["activities"] = len(load_courses(load_settings())[0])
        except (OSError, ValueError) as e:
            data.update(available=False, error=f"data file unreadable: {e}")
    cfg = AgentSettings.from_env()
    ai = {"enabled": cfg.enabled, "provider": cfg.provider, "model": cfg.model, "ollama": "not_checked", "error": None}
    if cfg.enabled and cfg.error:
        ai["error"] = f"invalid AI configuration: {cfg.error}"  # Ollama is not checked; the assistant won't run
    elif cfg.enabled:
        try:
            OllamaClient(cfg.base_url, cfg.model, timeout=3).check_model()  # lists models; runs no model
            ai["ollama"] = "ok"
        except OllamaError as e:
            ai.update(ollama="unavailable", error=str(e))
    return jsonify({"backend": "ok", "data": data, "ai": ai})


@app.route("/agent/chat", methods=["POST"])
def agent_chat():
    """Kids Activity AI Agent: {"message": "...", "lang": "en"} -> answer, activities, tools_used,
    agent_status, model, error. Uses the local Ollama model (AI_* environment variables); read-only."""
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") if isinstance(body.get("lang"), str) else "en"
    try:
        settings = load_settings()
        courses, today = load_courses(settings) if os.path.exists(DATA_FILE) else ([], local_today())
        result, status = handle_chat(body.get("message"), courses, settings, today, lang=lang)
    except Exception as e:
        return jsonify({"answer": None, "activities": [], "tools_used": [], "agent_status": "error",
                        "model": os.getenv("AI_MODEL"), "error": str(e)}), 500
    return jsonify({**result, "activities": [course_item(c, lang) for c in result["activities"]]}), status


if __name__ == "__main__":
    # 0.0.0.0 inside the container so the frontend container can reach backend:8000 over the Docker network.
    # docker-compose.yml publishes the port on the Mac's loopback only (127.0.0.1:8000), not to the LAN.
    app.run(host="0.0.0.0", port=8000)

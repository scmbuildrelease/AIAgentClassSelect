"""GET /courses filters, GET /options and GET /health (used by the mobile UI). Read-only, no network."""
import hashlib
import importlib
import json
import sys

import pytest

from conftest import ROOT

COURSES = {
    "robo": {"id": "robo", "name": "LEGO Robotics Camp", "categories": ["stem"], "city": "San Jose", "age_min": 7,
             "age_max": 9, "start_date": "2026-12-21", "end_date": "2026-12-23",
             "last_checked": "2026-11-16T04:00:00Z"},
    "swim": {"id": "swim", "name": "Swim Lessons", "categories": ["sports"], "city": "Fremont", "age_min": 4,
             "age_max": 6, "sessions": ["2026-11-21 10:00"]},
    "zhong": {"id": "zhong", "name": "中文学校周六班", "categories": ["language"], "location": "圣何塞 San Jose"},
    "past": {"id": "past", "name": "Summer Camp", "city": "San Jose", "start_date": "2026-06-15",
             "end_date": "2026-07-17"},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("flask")
    data = tmp_path / "courses.json"
    data.write_text(json.dumps({"courses": COURSES}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("COURSES_FILE", str(data))
    monkeypatch.setenv("SETTINGS_FILE", str(ROOT / "config" / "settings.json"))
    monkeypatch.setenv("TODAY", "2026-11-16")
    for var in ("AI_ENABLED", "AI_BASE_URL", "AI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    sys.path.insert(0, str(ROOT / "backend"))
    app = importlib.reload(importlib.import_module("app")).app
    c = app.test_client()
    c.data_file = data
    return c


def ids(client, query=""):
    r = client.get(f"/courses?{query}")
    assert r.status_code == 200, r.get_json()
    return sorted(c["id"] for c in r.get_json())


def test_courses_without_filters_is_unchanged(client):
    assert ids(client) == ["robo", "swim", "zhong"]  # past hidden by default, as before
    assert ids(client, "all=1") == ["past", "robo", "swim", "zhong"]
    assert ids(client, "q=机器人") == ["robo"]


@pytest.mark.parametrize("query, expected", [
    ("age=8", ["robo"]),                                     # zhong publishes no ages: not a match
    ("age=5", ["swim"]),
    ("city=San Jose", ["robo", "zhong"]),
    ("city=圣何塞", ["robo", "zhong"]),                        # Chinese city alias
    ("city=San Francisco Bay Area", ["robo", "swim", "zhong"]),  # the region is not a city filter
    ("category=stem", ["robo"]),
    ("from=2026-11-20&to=2026-11-22", ["swim"]),
    ("from=2026-12-22", ["robo"]),
    ("age=8&city=San Jose&category=stem&q=robotics", ["robo"]),
    ("age=8&city=Fremont", []),
])
def test_courses_filters(client, query, expected):
    assert ids(client, query) == expected


@pytest.mark.parametrize("query, error", [
    ("age=eight", "age must be a whole number"),
    ("age=40", "age must be a whole number"),
    ("from=next-friday", "Invalid isoformat"),
    ("from=2026-12-31&to=2026-12-01", "'to' is before 'from'"),
    ("category=robots", "unknown category 'robots'"),
])
def test_courses_filter_errors(client, query, error):
    r = client.get(f"/courses?{query}")
    assert r.status_code == 400 and error in r.get_json()["error"]


def test_options_lists_categories_and_cities_from_current_data(client):
    o = client.get("/options").get_json()
    assert o["categories"]["stem"] == {"label": "Math, Science, STEM & Coding", "short": "STEM"}
    assert o["cities"] == [{"name": "Fremont", "count": 1}, {"name": "San Jose", "count": 1}]  # past not counted


def test_health_without_ai(client):
    h = client.get("/health").get_json()
    assert h["backend"] == "ok"
    assert h["data"] == {"available": True, "activities": 3, "last_checked": "2026-11-16T04:00:00Z"}
    assert h["ai"]["enabled"] is False and h["ai"]["ollama"] == "not_checked"


def test_health_reports_unreachable_ollama(client, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_BASE_URL", "http://127.0.0.1:9")  # nothing listens on port 9
    ai = client.get("/health").get_json()["ai"]
    assert ai["enabled"] and ai["ollama"] == "unavailable" and "no Ollama server is reachable" in ai["error"]


def test_health_reports_invalid_ai_settings_without_failing(client, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_TIMEOUT", "abc")
    r = client.get("/health")
    ai = r.get_json()["ai"]
    assert r.status_code == 200 and r.get_json()["backend"] == "ok"
    assert ai["ollama"] == "not_checked" and "invalid AI configuration: AI_TIMEOUT must be" in ai["error"]


def test_empty_results_are_an_empty_list(client):
    assert ids(client, "q=underwater basket weaving") == []
    assert ids(client, "city=Gilroy") == []


def test_health_without_data_file(client, monkeypatch, tmp_path):
    import app
    monkeypatch.setattr(app, "DATA_FILE", str(tmp_path / "missing.json"))
    data = client.get("/health").get_json()["data"]
    assert data["available"] is False and data["activities"] == 0


def test_new_endpoints_never_write_the_data_file(client):
    before = hashlib.sha256(client.data_file.read_bytes()).hexdigest()
    for url in ("/courses?age=8&city=San Jose", "/options", "/health", "/courses?all=1"):
        client.get(url)
    assert hashlib.sha256(client.data_file.read_bytes()).hexdigest() == before


def test_no_cors_headers_browsers_use_the_same_origin_proxy(client):
    for r in (client.get("/courses", headers={"Origin": "http://evil.example"}),
              client.options("/agent/chat", headers={"Origin": "http://evil.example",
                                                     "Access-Control-Request-Method": "POST"})):
        assert "Access-Control-Allow-Origin" not in r.headers

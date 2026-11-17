"""Kids Activity AI Agent: tool calling loop, validation, limits, errors and the /agent/chat endpoint.

Most tests script Ollama's replies with a fake HTTP session (no model needed, as in CI). The `live` tests
call the real local Ollama server and are skipped when it or the model is not available.
"""
import copy
import hashlib
import importlib
import json
import sys
from datetime import date

import pytest
import requests

from activity_tracker import agent
from activity_tracker.agent import (ActivityTools, OllamaClient, OllamaError, clean_answer, handle_chat,
                                    run_agent)
from conftest import ROOT

TODAY = date(2026, 11, 16)
SETTINGS = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
ENV = {"AI_ENABLED": "true", "AI_PROVIDER": "ollama", "AI_MODEL": "qwen2.5:1.5b",
       "AI_BASE_URL": "http://ollama.test:11434"}
COURSES = [
    {"id": "robo", "name": "LEGO Robotics Camp", "provider": "Bot Lab", "categories": ["stem"], "city": "San Jose",
     "age_text": "Ages 7-9", "age_min": 7, "age_max": 9, "start_date": "2026-12-21", "end_date": "2026-12-23",
     "price": "$450", "detail_url": "https://botlab.example.org/camps/robotics", "source_url": "https://botlab.example.org/"},
    {"id": "swim", "name": "Swim Lessons", "provider": "Aqua Kids", "categories": ["sports"], "city": "Fremont",
     "age_text": "Ages 4-6", "age_min": 4, "age_max": 6, "sessions": ["2026-11-21 10:00–11:00"],
     "detail_url": "https://aqua.example.org/swim"},
    {"id": "zhong", "name": "中文学校周六班", "provider": "谷雨中文学校", "categories": ["language"],
     "city": "San Jose", "source_url": "https://school.example.org/"},
]


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


class FakeOllama:
    """Scripted Ollama: each POST /api/chat returns the next reply; records every request."""

    def __init__(self, replies, models=("qwen2.5:1.5b",)):
        self.replies, self.models, self.requests = list(replies), models, []

    def get(self, url, timeout):
        return Resp(200, {"models": [{"name": m} for m in self.models]})

    def post(self, url, json, timeout):
        self.requests.append(copy.deepcopy(json))  # a snapshot: later turns mutate the message list
        return Resp(200, {"message": self.replies.pop(0)})


def call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


def tool_reply(*calls):
    return {"role": "assistant", "content": "", "tool_calls": list(calls)}


def answer(text):
    return {"role": "assistant", "content": text}


def chat(replies, message="Find robotics classes", **kw):
    fake = FakeOllama(replies, **kw)
    body, status = handle_chat(message, COURSES, SETTINGS, TODAY, env=ENV, session=fake)
    return body, status, fake


def test_model_selected_tool_is_executed_and_result_sent_back():
    body, status, fake = chat([tool_reply(call("search_activities", keyword="robotics")),
                               answer("LEGO Robotics Camp by Bot Lab, Ages 7-9, $450.")])
    assert status == 200 and body["agent_status"] == "ok" and body["error"] is None
    assert body["model"] == "qwen2.5:1.5b" and body["answer"].startswith("LEGO Robotics Camp")
    assert body["tools_used"] == [{"tool": "search_activities", "arguments": {"keyword": "robotics"}, "ok": True,
                                   "result_count": 1}]
    assert [a["id"] for a in body["activities"]] == ["robo"]
    first, second = fake.requests
    assert [t["function"]["name"] for t in first["tools"]] == ["search_activities", "filter_by_age",
                                                              "filter_by_date", "get_activity_details"]
    assert first["options"] == {"temperature": 0} and first["stream"] is False
    tool_msg = second["messages"][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["activities"][0]["id"] == "robo"


def test_multiple_tool_calls_narrow_the_results():
    body, _, fake = chat([tool_reply(call("search_activities", location="圣何塞")),       # San Jose: robo, zhong
                          tool_reply(call("filter_by_age", age=8)),                      # robo only (zhong: no ages)
                          tool_reply(call("filter_by_date", start_date="2026-12-20", end_date="2026-12-31")),
                          answer("One match: LEGO Robotics Camp.")],
                         message="8岁 圣何塞 寒假")
    assert [(t["tool"], t["result_count"]) for t in body["tools_used"]] == [
        ("search_activities", 2), ("filter_by_age", 1), ("filter_by_date", 1)]
    assert [a["id"] for a in body["activities"]] == ["robo"] and len(fake.requests) == 4
    age_result = json.loads(fake.requests[2]["messages"][-1]["content"])
    assert age_result["left_out_without_published_age"] == 1
    assert age_result["activities"][0]["age_fit"] == "published range includes age 8"
    # older list results are collapsed so the model only reads the newest one in full
    assert "superseded" in fake.requests[3]["messages"][-3]["content"]


def test_several_calls_in_one_step_and_details():
    body, _, _ = chat([tool_reply(call("search_activities", keyword="swim"), call("get_activity_details",
                                                                               activity_id="swim")),
                       answer("Swim Lessons on 2026-11-21.")])
    assert [t["tool"] for t in body["tools_used"]] == ["search_activities", "get_activity_details"]
    assert all(t["ok"] for t in body["tools_used"]) and [a["id"] for a in body["activities"]] == ["swim"]


@pytest.mark.parametrize("bad_call, error", [
    (call("run_shell", command="rm -rf /"), "unknown tool 'run_shell'"),
    (call("__init__"), "unknown tool '__init__'"),
    (call("filter_by_age", age="eight"), "age must be a whole number"),
    (call("filter_by_age", age=40), "age must be between 0 and 18"),
    (call("filter_by_age"), "missing required argument(s): age"),
    (call("filter_by_date", start_date="next friday"), "dates must be YYYY-MM-DD"),
    (call("filter_by_date", start_date="2026-12-31", end_date="2026-12-01"), "end_date is before start_date"),
    (call("search_activities", category="quidditch"), "unknown category 'quidditch'"),
    (call("get_activity_details", activity_id="nope"), "No activity has id 'nope'"),
    ({"function": {"name": "search_activities", "arguments": "not json"}}, "arguments must be a JSON object"),
])
def test_invalid_and_unknown_tool_calls_are_rejected_not_executed(bad_call, error):
    body, status, fake = chat([tool_reply(bad_call), answer("Sorry, I could not search.")])
    entry = body["tools_used"][0]
    assert status == 200 and entry["ok"] is False and error in entry["error"]
    assert "error" in json.loads(fake.requests[1]["messages"][-1]["content"])  # the model is told why
    assert body["activities"] == []


def test_unknown_arguments_are_ignored_and_reported():
    body, _, _ = chat([tool_reply(call("search_activities", keyword="robotics", age=8)), answer("ok")])
    assert body["tools_used"][0]["ignored_arguments"] == ["age"] and body["tools_used"][0]["ok"]


def test_too_many_calls_in_one_step_are_skipped():
    body, _, _ = chat([tool_reply(*[call("search_activities")] * 6), answer("ok")])
    assert [t["tool"] for t in body["tools_used"]] == ["search_activities"] * 4 + ["(skipped)"]
    assert "2 more tool call(s)" in body["tools_used"][-1]["error"]


def test_maximum_iterations_stops_the_loop():
    fake = FakeOllama([tool_reply(call("search_activities", keyword="robotics"))] * 10)
    body, status = handle_chat("robotics", COURSES, SETTINGS, TODAY, env={**ENV, "AI_MAX_ITERATIONS": "3"},
                               session=fake)
    assert status == 200 and body["agent_status"] == "max_iterations" and len(fake.requests) == 3
    assert len(body["tools_used"]) == 3 and "stopped after 3 model calls" in body["answer"]
    assert [a["id"] for a in body["activities"]] == ["robo"]  # tool results so far, never model text


def test_answer_without_tools_is_nudged_once_then_flagged():
    body, _, fake = chat([answer("Try Robo Academy!"), answer("Try Robo Academy!")])
    assert body["agent_status"] == "no_tools_used" and body["activities"] == [] and len(fake.requests) == 2
    assert "Use the tools" in fake.requests[1]["messages"][-1]["content"]


def test_no_matching_activities():
    body, _, fake = chat([tool_reply(call("search_activities", keyword="fencing", location="Fremont")),
                          answer("No fencing classes were found in Fremont.")])
    result = json.loads(fake.requests[1]["messages"][-1]["content"])
    assert result["count"] == 0 and "search again with fewer arguments" in result["note"]
    assert body["agent_status"] == "ok" and body["activities"] == []


def test_bay_area_is_not_a_city_filter():
    tools = ActivityTools(COURSES, SETTINGS, TODAY)
    assert tools.search_activities(keyword="robotics classes", location="San Francisco Bay Area")["count"] == 1
    assert tools.search_activities(keyword="中文学校课程", location="湾区")["count"] == 1


def test_source_urls_are_preserved_and_invented_links_removed():
    body, _, fake = chat([tool_reply(call("get_activity_details", activity_id="robo")),
                          answer("See https://botlab.example.org/camps/robotics. Or https://made-up.example.com/x")])
    details = json.loads(fake.requests[1]["messages"][-1]["content"])["activity"]
    assert details["detail_url"] == "https://botlab.example.org/camps/robotics"
    assert details["source_url"] == "https://botlab.example.org/" and details["price"] == "$450"
    assert "https://botlab.example.org/camps/robotics" in body["answer"]
    assert "made-up.example.com" not in body["answer"] and "[link removed" in body["answer"]
    assert body["activities"][0]["detail_url"] == "https://botlab.example.org/camps/robotics"


def test_private_reasoning_is_never_returned():
    assert clean_answer("<think>secret plan</think>Here you go.", set()) == "Here you go."


def test_ollama_unreachable_gives_a_clear_error():
    body, status = handle_chat("robotics", COURSES, SETTINGS, TODAY,
                               env={**ENV, "AI_BASE_URL": "http://127.0.0.1:9"})  # nothing listens on port 9
    assert status == 503 and body["agent_status"] == "unavailable" and body["activities"] == []
    assert "no Ollama server is reachable at http://127.0.0.1:9" in body["error"]


def test_missing_model_gives_a_clear_error():
    body, status, fake = chat([], models=("llama3.2:latest",))
    assert status == 503 and body["agent_status"] == "unavailable" and fake.requests == []
    assert "model 'qwen2.5:1.5b' is not installed" in body["error"] and "llama3.2:latest" in body["error"]


@pytest.mark.parametrize("env, status, error", [
    ({}, "disabled", "set AI_ENABLED=true"),
    ({**ENV, "AI_PROVIDER": "openai"}, "disabled", "only the local 'ollama' provider"),
    ({**ENV, "AI_BASE_URL": "file:///etc/passwd"}, "unavailable", "must be an http:// or https:// URL"),
])
def test_disabled_or_unsupported_configuration(env, status, error):
    body, code = handle_chat("robotics", COURSES, SETTINGS, TODAY, env=env, session=FakeOllama([]))
    assert code == 503 and body["agent_status"] == status and error in body["error"]


def test_endpoint_returns_cards_and_leaves_the_data_unchanged(tmp_path, monkeypatch):
    pytest.importorskip("flask")
    data = tmp_path / "courses.json"
    data.write_text(json.dumps({"courses": {c["id"]: c for c in COURSES}}, ensure_ascii=False), encoding="utf-8")
    before = hashlib.sha256(data.read_bytes()).hexdigest()
    for k, v in {**ENV, "COURSES_FILE": str(data), "SETTINGS_FILE": str(ROOT / "config" / "settings.json"),
                 "TODAY": "2026-11-16"}.items():
        monkeypatch.setenv(k, v)
    fake = FakeOllama([tool_reply(call("search_activities", keyword="机器人")), answer("LEGO Robotics Camp")])
    monkeypatch.setattr(agent.requests, "Session", lambda: fake)
    sys.path.insert(0, str(ROOT / "backend"))
    client = importlib.reload(importlib.import_module("app")).app.test_client()
    courses_before = client.get("/courses").get_json()
    r = client.post("/agent/chat", json={"message": "机器人课程", "lang": "zh-Hans"})
    body = r.get_json()
    assert r.status_code == 200 and set(body) == {"answer", "activities", "tools_used", "agent_status", "model",
                                                  "error"}
    card = body["activities"][0]
    assert card["link"] == "https://botlab.example.org/camps/robotics" and card["display"]["name"]
    assert client.post("/agent/chat", json={}).status_code == 400
    assert client.get("/courses").get_json() == courses_before          # existing API unchanged
    assert hashlib.sha256(data.read_bytes()).hexdigest() == before       # data file never written


# ---- real local Ollama (skipped when it is not running or the model is not installed) ----

def _live_settings():
    cfg = agent.AgentSettings.from_env({**ENV, "AI_BASE_URL": "http://localhost:11434"})
    try:
        OllamaClient(cfg.base_url, cfg.model, timeout=5).check_model()
    except OllamaError as e:
        pytest.skip(f"local Ollama not available: {e}")
    return cfg


def test_live_ollama_selects_a_tool_and_answers():
    cfg = _live_settings()
    tools = ActivityTools(COURSES, SETTINGS, TODAY)
    result = run_agent("Find robotics classes", tools, OllamaClient(cfg.base_url, cfg.model, timeout=120))
    used = [t["tool"] for t in result["tools_used"]]
    assert result["agent_status"] == "ok" and "search_activities" in used and result["answer"]
    assert {a["id"] for a in result["activities"]} <= {c["id"] for c in COURSES}
    print("\nLIVE tools:", json.dumps(result["tools_used"], ensure_ascii=False), "\nLIVE answer:", result["answer"])


def test_live_ollama_chains_search_and_date_filter():
    cfg = _live_settings()
    tools = ActivityTools(COURSES, SETTINGS, TODAY)
    result = run_agent("Any activities in Fremont between 2026-11-20 and 2026-11-22?", tools,
                       OllamaClient(cfg.base_url, cfg.model, timeout=120))
    used = [t["tool"] for t in result["tools_used"]]
    print("\nLIVE tools:", json.dumps(result["tools_used"], ensure_ascii=False), "\nLIVE answer:", result["answer"])
    assert "search_activities" in used and "filter_by_date" in used
    assert [a["id"] for a in result["activities"]] == ["swim"]


def test_requests_is_the_only_http_client():
    assert agent.requests is requests  # no AI SDKs: plain HTTP to the local Ollama API

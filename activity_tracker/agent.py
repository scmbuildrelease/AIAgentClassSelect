"""Kids Activity AI Agent: a local Ollama model chooses which activity tools to call.

User message -> model (with tool definitions) -> tool calls -> Python tools over the tracked activities ->
tool results -> model -> ... -> final answer. The tools reuse the existing search and filter code and only
read data. Activity facts shown to the user (cards, links) come from tool results, never from model text.

Configuration is environment-only (no API keys, no cloud providers, no fallback to one):
  AI_ENABLED=true  AI_PROVIDER=ollama  AI_MODEL=qwen2.5:1.5b  AI_BASE_URL=http://localhost:11434
  In Docker: AI_BASE_URL=http://host.docker.internal:11434 (the Ollama app on the Mac host).
"""
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from datetime import date
from urllib.parse import urlsplit

import requests

from .config import Config
from .extract import detect_cities
from .i18n import search_key
from .recommend import AGE_GROUP_MATCH, AGE_MATCH_CONFIRMED, age_fit, age_fit_note, date_span
from .search import Glossary, search

DEFAULT_MODEL = "qwen2.5:1.5b"  # small tool-calling model (~1 GB) that runs on an 8 GB Mac; pull it with Ollama
DEFAULT_BASE_URL = "http://localhost:11434"
MAX_ITERATIONS = 5             # model calls per request
MAX_TOOL_CALLS_PER_STEP = 4
MAX_MESSAGE_CHARS = 500
RESULT_LIMIT = 8               # activities sent back to the model per tool result
CARD_LIMIT = 20                # activities returned to the frontend
OK, NO_TOOLS_USED, MAX_ITERATIONS_REACHED = "ok", "no_tools_used", "max_iterations"
DISABLED, UNAVAILABLE, ERROR = "disabled", "unavailable", "error"

# Words that describe the request, not the activity ("robotics classes for kids" -> "robotics").
# search() requires every leftover word to appear, so these would otherwise hide every match.
GENERIC_WORDS = {"class", "classes", "course", "courses", "activity", "activities", "program", "programs",
                 "lesson", "lessons", "kid", "kids", "child", "children", "for", "my", "a", "an", "the", "and",
                 "in", "near", "year", "years", "old", "yo", "age", "aged", "ages", "some", "any", "find", "me"}
GENERIC_ZH = ("课程", "課程", "课堂", "課堂", "活动", "活動", "儿童", "兒童", "孩子", "小孩", "小朋友", "适合", "適合")
# The whole region is not a location filter ("San Francisco Bay Area" must not mean San Francisco only).
REGION_RE = re.compile(r"(?:the\s+)?(?:san francisco\s+|sf\s+)?bay\s*area|南湾|南灣|东湾|東灣|湾区|灣區", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"')\]，。]+")
THINK_RE = re.compile(r"<think>.*?</think>", re.S)  # never show a model's private reasoning

SYSTEM_PROMPT = """You help a parent find kids' activities in the San Francisco Bay Area. Today is {today}.
Rules:
- Always call a tool to find activities before answering. Never invent activities, ages, dates, prices or links.
- search_activities finds activities by keyword, category and location. Only pass a category or location the
  user asked for.
- If the user gives the child's age, call filter_by_age with it after searching.
- If the user mentions a date, a date range or "this weekend", you MUST call filter_by_date with those dates
  after searching, and only list activities from its results.
- filter_by_age and filter_by_date narrow the results of the most recent search.
- get_activity_details returns everything known about one activity, by its id.
- Dates are YYYY-MM-DD. Valid categories: {categories}.
- If no activities are found, say so plainly.
- Final answer: list up to 5 activities by name with provider, ages, dates and price exactly as the tool results
  give them ("not published" when missing). Answer in the same language as the user. Be brief."""
NUDGE = "Use the tools to look up activities before answering. Do not answer from memory."


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required}}}


TOOL_DEFINITIONS = [
    _tool("search_activities", "Search tracked kids' activities. All arguments are optional.",
          {"keyword": {"type": "string", "description": "Topic, e.g. robotics, swimming, 机器人, 夏令营"},
           "category": {"type": "string", "description": "One category key; only if the user names that kind"},
           "location": {"type": "string", "description": "City, e.g. San Jose, Fremont, 圣何塞"}}, []),
    _tool("filter_by_age", "Keep only activities whose published ages include the child's age.",
          {"age": {"type": "integer", "description": "Child's age in years"}}, ["age"]),
    _tool("filter_by_date", "Keep only activities with published dates between start_date and end_date.",
          {"start_date": {"type": "string", "description": "YYYY-MM-DD"},
           "end_date": {"type": "string", "description": "YYYY-MM-DD; defaults to start_date"}}, ["start_date"]),
    _tool("get_activity_details", "Full details and official source link of one activity.",
          {"activity_id": {"type": "string", "description": "The id from a search result"}}, ["activity_id"]),
]
ARGUMENT_TYPES = {name: {p: spec["type"] for p, spec in t["function"]["parameters"]["properties"].items()}
                  for t in TOOL_DEFINITIONS for name in [t["function"]["name"]]}
REQUIRED = {t["function"]["name"]: set(t["function"]["parameters"]["required"]) for t in TOOL_DEFINITIONS}


class OllamaError(RuntimeError):
    """The local model could not be used; the message says why."""


class ToolError(ValueError):
    """Invalid tool call; the message is sent back to the model."""


@dataclass
class AgentSettings:
    enabled: bool
    provider: str
    model: str
    base_url: str
    timeout: float
    max_iterations: int

    @classmethod
    def from_env(cls, env=None) -> "AgentSettings":
        env = os.environ if env is None else env
        return cls(enabled=(env.get("AI_ENABLED") or "").strip().lower() in ("1", "true", "yes"),
                   provider=(env.get("AI_PROVIDER") or "ollama").strip().lower(),
                   model=env.get("AI_MODEL") or DEFAULT_MODEL,
                   base_url=(env.get("AI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
                   timeout=float(env.get("AI_TIMEOUT") or 120),
                   max_iterations=int(env.get("AI_MAX_ITERATIONS") or MAX_ITERATIONS))


class OllamaClient:
    """Minimal client for a local Ollama server's chat API with native tool calling."""

    def __init__(self, base_url: str, model: str, timeout: float = 120, session: requests.Session | None = None):
        if urlsplit(base_url).scheme not in ("http", "https"):
            raise OllamaError(f"AI_BASE_URL must be an http:// or https:// URL, not {base_url!r}")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout
        self.session = session or requests.Session()

    def _unreachable(self) -> OllamaError:
        return OllamaError(f"no Ollama server is reachable at {self.base_url} "
                           "(start the Ollama app or `ollama serve`; in Docker, check AI_BASE_URL)")

    def check_model(self) -> None:
        """Fail early, with a clear reason, if the server is down or the model is not installed."""
        try:
            r = self.session.get(f"{self.base_url}/api/tags", timeout=10)
        except requests.RequestException:
            raise self._unreachable() from None
        if r.status_code != 200:
            raise OllamaError(f"Ollama at {self.base_url} answered HTTP {r.status_code}")
        try:
            names = {m.get("name") for m in r.json().get("models", [])}
        except (ValueError, AttributeError):
            raise OllamaError(f"{self.base_url} did not answer like an Ollama server") from None
        if self.model not in names and f"{self.model}:latest" not in names:
            raise OllamaError(f"model {self.model!r} is not installed on the Ollama server at {self.base_url} "
                              f"(installed: {', '.join(sorted(n for n in names if n)) or 'none'}); "
                              f"set AI_MODEL to one of them or run `ollama pull {self.model}`")

    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False) -> dict:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False,
                                   "options": {"temperature": 0}}
        if tools:
            payload["tools"] = tools
        if json_mode:
            payload["format"] = "json"
        return self._post_message(payload)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embedding vectors from the server (POST /api/embed); OllamaError says why when unsupported."""
        try:
            r = self.session.post(f"{self.base_url}/api/embed", json={"model": model, "input": texts},
                                  timeout=self.timeout)
        except requests.Timeout:
            raise OllamaError(f"embedding model {model!r} did not answer within {self.timeout:.0f}s") from None
        except requests.RequestException:
            raise self._unreachable() from None
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code != 200 or not isinstance(body, dict):
            error = body.get("error") if isinstance(body, dict) else None
            raise OllamaError(f"embeddings unavailable: {error or f'HTTP {r.status_code}'}")
        vectors = body.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise OllamaError("Ollama returned no embeddings")
        return vectors

    def _post_message(self, payload: dict) -> dict:
        try:
            r = self.session.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except requests.Timeout:
            raise OllamaError(f"model {self.model!r} did not answer within {self.timeout:.0f}s") from None
        except requests.RequestException:
            raise self._unreachable() from None
        if r.status_code != 200:
            raise OllamaError(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")
        try:
            message = r.json().get("message")
        except (ValueError, AttributeError):
            message = None
        if not isinstance(message, dict):
            raise OllamaError("Ollama returned a response without a message")
        return message


def _keyword(text: str) -> str:
    for word in GENERIC_ZH:
        text = text.replace(word, " ")
    text = re.sub(r"(?<=\S)[课課班](?=\s|$)", " ", text)  # "编程课" -> "编程"; "课后" is kept
    return " ".join(w for w in text.split() if w.lower() not in GENERIC_WORDS and not w.isdigit())


def _when(rec: dict) -> str:
    if rec.get("sessions"):
        more = len(rec["sessions"]) - 2
        return "; ".join(rec["sessions"][:2]) + (f" (+{more} more)" if more > 0 else "")
    start, end = rec.get("start_date"), rec.get("end_date")
    if start and end and end != start:
        return f"{start} to {end}"
    return start or end or "not published"


def summary(rec: dict) -> dict:
    """What the model sees of an activity: published values only."""
    return {"id": rec["id"], "name": rec.get("name"), "provider": rec.get("provider"),
            "city": rec.get("city") or rec.get("location") or "not published",
            "ages": rec.get("age_text") or "not published", "dates": _when(rec),
            "price": rec.get("price") or "not published", "url": rec.get("detail_url") or rec.get("source_url")}


DETAIL_FIELDS = ("id", "name", "provider", "organizer", "city", "location", "categories", "age_text", "schedule",
                 "sessions", "start_date", "end_date", "price", "enrollment_status", "description", "detail_url",
                 "registration_url", "source_url", "original_event_url", "lifecycle")


def location_matcher(location: str | None, cities) -> Callable[[dict], bool] | None:
    """Predicate for records in the given place, or None when it names no place ("Bay Area" is not one)."""
    location = REGION_RE.sub(" ", location or "").strip(" ,")
    if not location:
        return None
    wanted = set(detect_cities(location, cities))  # "圣何塞" -> San Jose
    place = search_key(location)

    def here(r: dict) -> bool:
        text = " ".join(filter(None, (r.get("city"), r.get("location"))))
        return bool(wanted & set(detect_cities(text, cities))) if wanted else place in search_key(text)
    return here


def age_matches(rec: dict, min_age: int, max_age: int) -> bool:
    """Published ages (or the aggregator's broad age group) include the wanted ages."""
    return age_fit(rec, min_age, max_age) in (AGE_MATCH_CONFIRMED, AGE_GROUP_MATCH)


def has_published_age(rec: dict) -> bool:
    return not (rec.get("age_min") is None and rec.get("age_max") is None and rec.get("age_group_min") is None)


def dates_overlap(rec: dict, start: date, end: date) -> bool | None:
    """Whether published dates overlap start..end; None when the record publishes no dates."""
    span = date_span(rec)
    if span is None:
        return None
    return span[0] <= end and (span[1] is None or span[1] >= start)


class ActivityTools:
    """The four tools, over the current (non-past, non-adult) activities. Read-only."""

    def __init__(self, courses: list[dict], settings: dict, today: date):
        self.catalog = courses
        self.by_id = {c["id"]: c for c in courses}
        self.today = today
        self.glossary = Glossary(settings.get("glossary", []))
        self.categories = settings.get("categories", {})
        self.labels = {k: " ".join([v.get("label", ""), v.get("short", "")]) for k, v in self.categories.items()}
        self.cities = Config(settings, [], []).cities
        self.current: list[dict] | None = None  # result set of the latest search/filter
        self.detailed: list[dict] = []
        # explicit dispatch table: a tool name from the model is only ever looked up here
        self.handlers: dict[str, Callable[..., dict]] = {
            "search_activities": self.search_activities, "filter_by_age": self.filter_by_age,
            "filter_by_date": self.filter_by_date, "get_activity_details": self.get_activity_details}

    def _result(self, recs: list[dict], empty_hint: str = "", **notes) -> dict:
        self.current = recs
        out = {"count": len(recs), "activities": [summary(r) for r in recs[:RESULT_LIMIT]], **notes}
        if not recs:
            out["note"] = (empty_hint or "No activities match.") + " Do not suggest activities that are not in results."
        elif len(recs) > RESULT_LIMIT:
            out["note"] = f"Showing the first {RESULT_LIMIT} of {len(recs)}."
        return out

    def search_activities(self, keyword: str | None = None, category: str | None = None,
                          location: str | None = None) -> dict:
        recs = self.catalog
        if category:
            recs = [r for r in recs if category in (r.get("categories") or [])]
        here = location_matcher(location, self.cities)
        if here:
            recs = [r for r in recs if here(r)]
        location = REGION_RE.sub(" ", location or "").strip(" ,")
        terms = _keyword(keyword or "")
        if terms:
            recs = search(recs, terms, self.glossary, self.labels)
        used = [f"{k}={v!r}" for k, v in (("keyword", terms), ("category", category), ("location", location)) if v]
        hint = (f"No activities match {', '.join(used)}. If the user did not ask for all of these, search again "
                "with fewer arguments; otherwise say none were found.") if len(used) > 1 else ""
        return self._result(recs, hint)

    def filter_by_age(self, age: int) -> dict:
        base = self.catalog if self.current is None else self.current
        fits = {r["id"]: age_fit(r, age, age) for r in base}
        kept = [r for r in base if fits[r["id"]] == AGE_MATCH_CONFIRMED] + \
               [r for r in base if fits[r["id"]] == AGE_GROUP_MATCH]
        unknown = sum(1 for r in base if not has_published_age(r))
        out = self._result(kept, left_out_without_published_age=unknown)
        for item, rec in zip(out["activities"], kept):
            item["age_fit"] = age_fit_note(rec, age, age)
        return out

    def filter_by_date(self, start_date: date, end_date: date | None = None) -> dict:
        end_date = end_date or start_date
        base = self.catalog if self.current is None else self.current
        overlaps = {r["id"]: dates_overlap(r, start_date, end_date) for r in base}
        kept = [r for r in base if overlaps[r["id"]]]
        undated = sum(1 for r in base if overlaps[r["id"]] is None)
        return self._result(kept, left_out_without_published_dates=undated)

    def get_activity_details(self, activity_id: str) -> dict:
        rec = self.by_id.get(activity_id)
        if rec is None:
            return {"error": f"No activity has id {activity_id!r}. Use an id from a search result."}
        if rec not in self.detailed:
            self.detailed.append(rec)
        return {"count": 1, "activity": {k: rec.get(k) for k in DETAIL_FIELDS if rec.get(k) not in (None, [], "")}}

    def validate(self, name: str, raw) -> tuple[dict, list[str]]:
        """Checked, typed arguments plus the names of ignored unknown ones. Raises ToolError."""
        if isinstance(raw, str):
            try:
                raw = json.loads(raw or "{}")
            except ValueError:
                raise ToolError("arguments must be a JSON object") from None
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ToolError("arguments must be a JSON object")
        types = ARGUMENT_TYPES[name]
        ignored = sorted(k for k in raw if k not in types)
        args: dict[str, Any] = {}
        for key, kind in types.items():
            value = raw.get(key)
            if value is None or value == "":
                continue
            if kind == "integer":
                if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, float) and
                                                   value.is_integer()) or (isinstance(value, str) and value.isdigit())):
                    raise ToolError(f"{key} must be a whole number")
                value = int(value)
                if not 0 <= value <= 18:
                    raise ToolError(f"{key} must be between 0 and 18")
            else:
                if not isinstance(value, str):
                    raise ToolError(f"{key} must be a string")
                value = value.strip()[:100]
            args[key] = value
        missing = REQUIRED[name] - set(args)
        if missing:
            raise ToolError(f"missing required argument(s): {', '.join(sorted(missing))}")
        if name == "search_activities" and args.get("category"):
            wanted = args["category"].lower()
            key = next((k for k, v in self.categories.items()
                        if wanted in (k.lower(), v.get("short", "").lower(), v.get("label", "").lower())), None)
            if key is None:
                raise ToolError(f"unknown category {args['category']!r}; valid: {', '.join(self.categories)}")
            args["category"] = key
        if name == "filter_by_date":
            try:
                args = {k: date.fromisoformat(v) for k, v in args.items()}
            except ValueError:
                raise ToolError("dates must be YYYY-MM-DD") from None
            if args.get("end_date") and args["end_date"] < args["start_date"]:
                raise ToolError("end_date is before start_date")
        return args, ignored

    def execute(self, call: dict) -> tuple[dict, dict]:
        """Run one model-requested tool call: (trace entry, result for the model). Never raises on bad input."""
        fn = call.get("function") if isinstance(call, dict) else None
        name = fn.get("name") if isinstance(fn, dict) else None
        raw = fn.get("arguments") if isinstance(fn, dict) else None
        entry: dict[str, Any] = {"tool": str(name)[:60], "ok": False,
                                 "arguments": raw if isinstance(raw, dict) else str(raw)[:200]}
        if name not in self.handlers:
            entry["error"] = f"unknown tool {str(name)[:60]!r}"
            return entry, {"error": f"Unknown tool {str(name)[:60]!r}. Available: {', '.join(self.handlers)}"}
        try:
            args, ignored = self.validate(name, raw)
        except ToolError as e:
            entry["error"] = str(e)
            return entry, {"error": f"Invalid arguments for {name}: {e}"}
        result = self.handlers[name](**args)
        entry["arguments"] = {k: v.isoformat() if isinstance(v, date) else v for k, v in args.items()}
        if ignored:
            entry["ignored_arguments"] = ignored
        entry["ok"] = "error" not in result
        entry["result_count"] = result.get("count", 0)
        if "error" in result:
            entry["error"] = result["error"]
        return entry, result

    def shown(self) -> list[dict]:
        recs = list(self.current or [])
        return (recs + [r for r in self.detailed if r not in recs])[:CARD_LIMIT]

    def known_urls(self) -> set[str]:
        return {u for r in self.catalog for u in (r.get("detail_url"), r.get("source_url"),
                                                  r.get("registration_url"), r.get("original_event_url")) if u}


def clean_answer(text: str | None, known_urls: set[str]) -> str:
    """The model's final text without hidden reasoning, and without links that are not in the activity data."""
    text = THINK_RE.sub("", text or "").strip()
    return URL_RE.sub(lambda m: m.group(0) if m.group(0).rstrip(".,;:!?") in known_urls
                      else "[link removed: not in the activity data]", text)


def run_agent(message: str, tools: ActivityTools, client: OllamaClient, max_iterations: int = MAX_ITERATIONS) -> dict:
    """The tool-calling loop. The model decides which tools to call and when to answer."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT.format(today=tools.today.isoformat(),
                                                                    categories=", ".join(tools.categories))},
                {"role": "user", "content": message}]
    trace: list[dict] = []
    nudged = False
    latest_list: dict | None = None  # the model sees only the newest search/filter result in full
    for _ in range(max_iterations):
        reply = client.chat(messages, TOOL_DEFINITIONS)
        calls = reply.get("tool_calls") or []
        if not calls:
            if not trace and not nudged:  # answered from memory: ask once to use the tools instead
                nudged = True
                messages += [{"role": "assistant", "content": reply.get("content") or ""},
                             {"role": "user", "content": NUDGE}]
                continue
            return {"answer": clean_answer(reply.get("content"), tools.known_urls()), "activities": tools.shown(),
                    "tools_used": trace, "agent_status": OK if trace else NO_TOOLS_USED}
        messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": calls})
        for call in calls[:MAX_TOOL_CALLS_PER_STEP]:
            entry, result = tools.execute(call)
            trace.append(entry)
            tool_message = {"role": "tool", "tool_name": entry["tool"],
                            "content": json.dumps(result, ensure_ascii=False, default=str)}
            if entry["ok"] and entry["tool"] != "get_activity_details":
                if latest_list is not None:
                    latest_list["content"] = json.dumps({"note": "superseded by a later search or filter"})
                latest_list = tool_message
            messages.append(tool_message)
        if len(calls) > MAX_TOOL_CALLS_PER_STEP:
            skipped = len(calls) - MAX_TOOL_CALLS_PER_STEP
            error = f"{skipped} more tool call(s) in one step were not run (limit {MAX_TOOL_CALLS_PER_STEP})"
            trace.append({"tool": "(skipped)", "ok": False, "error": error})
            messages.append({"role": "tool", "tool_name": "(skipped)", "content": json.dumps({"error": error})})
    return {"answer": f"The assistant stopped after {max_iterations} model calls without a final answer. "
                      "The activities below are the tool results so far.",
            "activities": tools.shown(), "tools_used": trace, "agent_status": MAX_ITERATIONS_REACHED}


def handle_chat(message, courses: list[dict], settings: dict, today: date, env=None,
                session: requests.Session | None = None) -> tuple[dict, int]:
    """POST /agent/chat: (response body without display formatting, HTTP status)."""
    cfg = AgentSettings.from_env(env)
    base: dict[str, Any] = {"answer": None, "activities": [], "tools_used": [], "agent_status": None,
                            "model": cfg.model, "error": None}
    if not isinstance(message, str) or not message.strip():
        return {**base, "agent_status": ERROR, "error": "message is required"}, 400
    if len(message) > MAX_MESSAGE_CHARS:
        return {**base, "agent_status": ERROR, "error": f"message is longer than {MAX_MESSAGE_CHARS} characters"}, 400
    if not cfg.enabled:
        return {**base, "agent_status": DISABLED, "error": "The AI assistant is turned off (set AI_ENABLED=true)."}, 503
    if cfg.provider != "ollama":
        return {**base, "agent_status": DISABLED,
                "error": f"AI_PROVIDER={cfg.provider!r} is not supported; only the local 'ollama' provider is."}, 503
    try:
        client = OllamaClient(cfg.base_url, cfg.model, cfg.timeout, session)
        client.check_model()
        result = run_agent(message.strip(), ActivityTools(courses, settings, today), client, cfg.max_iterations)
    except OllamaError as e:
        return {**base, "agent_status": UNAVAILABLE, "error": f"Local AI model unavailable: {e}"}, 503
    return {**base, **result}, 200

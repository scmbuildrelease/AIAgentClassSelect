# Kids Activity AI Agent — MVP

A small tool-calling agent on top of the existing activity tracker. A **local** Qwen model, served by the
Ollama app already installed on the Mac (the same one CIRCA uses), reads a parent's question, **chooses which
Python tools to call**, reads their results, and writes a short answer. Everything runs on the machine:
there are no API keys, no cloud model and no cloud fallback.

## Architecture

```
React "AI Assistant" panel (frontend/src/Assistant.js)
   │  POST /agent/chat {"message", "lang"}
   ▼
Flask backend/app.py ── load_courses() (same list as GET /courses: no past or adult activities)
   │
   ▼
activity_tracker/agent.py
   handle_chat ── checks AI_* settings and that Ollama has the model (GET /api/tags)
   run_agent   ── loop, at most AI_MAX_ITERATIONS (5) model calls:
                    Ollama /api/chat (messages + 4 tool definitions, temperature 0)
                      ├─ tool_calls → validate → run tool (fixed dispatch table) → result back to the model
                      └─ text       → final answer
   ActivityTools ── search_activities, filter_by_age, filter_by_date, get_activity_details
                    reusing search.search + Glossary, extract.detect_cities, recommend.age_fit/age_fit_note,
                    recommend.date_span
```

The model only *decides*. The tools do the work, using the existing search and filter code, and only read
the data. `data/courses.json` is never written.

### What the user can trust

- **Activity cards and links come from tool results**, never from the model's text. Each card is a real record
  with its official `detail_url` or `source_url`.
- **The answer text is written by a 1.5B-parameter model** and can be imprecise: it may summarize badly or mention
  an item from an earlier step. Two guards apply:
  - Any URL in the answer that is not in the activity data is replaced with `[link removed: not in the activity data]`.
  - `<think>` blocks are removed. No private reasoning is returned.
- **The tool trace is the real list of calls** the model made, with validated arguments and result counts.

## Configuration

Environment variables only. These match CIRCA's approach: env-configured Ollama URL and model, `http(s)` URLs
only, and temperature 0.

| Variable | Default | Notes |
|---|---|---|
| `AI_ENABLED` | off | `true` turns the assistant on. When off, `/agent/chat` returns `agent_status: "disabled"`. |
| `AI_PROVIDER` | `ollama` | The only accepted value. Anything else is refused; there is no cloud provider. |
| `AI_MODEL` | `qwen2.5:1.5b` | The Qwen model already installed for CIRCA on the original Mac. A new Mac pulls it with `ollama pull qwen2.5:1.5b` (or a larger model; see [INSTALL_MAC.md](INSTALL_MAC.md)). |
| `AI_BASE_URL` | `http://localhost:11434` | In Docker: `http://host.docker.internal:11434` (set by `docker-compose.yml`) |
| `AI_TIMEOUT` | `120` | Seconds per model call |
| `AI_MAX_ITERATIONS` | `5` | Model calls per request |

Verified locally on 2026-11-16:
- Ollama **0.40.11**.
- Model **`qwen2.5:1.5b`** (Q4_K_M, 32K context). `GET /api/show` lists the capabilities `completion` and `tools`.

## Tools

| Tool | Arguments | Reuses | Behavior |
|---|---|---|---|
| `search_activities` | `keyword`, `category`, `location`, all optional | `search.search` + `Glossary` (bilingual: 机器人 = robotics), `extract.detect_cities` (圣何塞 → San Jose) | Starts a new result set. "Bay Area" or "湾区" is not a city filter. Words like "classes", "kids", 课程 and 课 are dropped from the keyword. |
| `filter_by_age` | `age` (0–18, required) | `recommend.age_fit`, `age_fit_note` | Narrows the latest results to published age ranges that include the age, then broad aggregator age groups. Counts records with no published age as left out. |
| `filter_by_date` | `start_date` (required), `end_date`, both `YYYY-MM-DD` | `recommend.date_span` (same date parsing as the lifecycle rule) | Keeps activities whose published sessions or dates overlap the range. Counts undated records as left out. |
| `get_activity_details` | `activity_id` (required) | — | All published fields of one activity, including `detail_url`, `registration_url`, `source_url` and the organizer's original URL |

### Safety rules in the loop

- **Fixed dispatch table.** Unknown tool names (`run_shell`, `__init__`, …) are rejected and the model is told
  which tools exist. Nothing is looked up with `getattr`, and no Python, shell or SQL is ever executed.
- **Argument validation:**
  - Types, ranges, required fields, ISO dates (with end ≥ start) and known categories are checked.
  - Unknown extra arguments are ignored and listed in the trace (`ignored_arguments`).
  - Strings are cut to 100 characters, and the message itself is limited to 500.
- **Limits.**
  - At most 4 tool calls run per model step; the rest are skipped and reported.
  - At most `AI_MAX_ITERATIONS` model calls run per request. Hitting the limit returns `agent_status: "max_iterations"`
    with the tool results so far.
- **No answer from memory.** If the model answers without any tool, it is asked once to use the tools. If it
  still doesn't, the reply is returned with `agent_status: "no_tools_used"` and no activity cards, and the UI
  says the answer is not based on the activity data.
- **Small context for a small model.** When a newer search or filter result arrives, older list results in the
  conversation are replaced by a short "superseded" note, so the model reads only the current result set.

## API

`POST /agent/chat` with body `{"message": "Robotics for an 8 year old in San Jose", "lang": "en"}` returns:

```json
{
  "answer": "Here are some robotics camps for an 8-year-old in San Jose: …",
  "activities": [{"id": "…", "name": "Junior Robot Engineer", "link": "https://siliconvalley.clubscikidz.com/…", "display": {…}, …}],
  "tools_used": [{"tool": "search_activities", "arguments": {"keyword": "robotics", "category": "stem", "location": "San Jose"},
                  "ok": true, "result_count": 3}],
  "agent_status": "ok",
  "model": "qwen2.5:1.5b",
  "error": null
}
```

| `agent_status` | HTTP | Meaning |
|---|---|---|
| `ok` | 200 | At least one tool ran and the model answered |
| `no_tools_used` | 200 | The model answered without tools, even after being asked once (e.g. "hi") |
| `max_iterations` | 200 | Step limit reached; `activities` holds the tool results so far |
| `disabled` | 503 | `AI_ENABLED` is not true, or `AI_PROVIDER` is not `ollama` |
| `unavailable` | 503 | Ollama is unreachable, the model isn't installed, a call timed out, or `AI_BASE_URL` is invalid. `error` says which. |
| `error` | 400 / 500 | Missing or over-long message, or an unexpected server error |

`activities` items have the same shape as `GET /courses` items. `GET /courses` is unchanged.

## Run it

### Local (no Docker)

```bash
ollama list                         # qwen2.5:1.5b must be listed; the Ollama app must be running
. .venv/bin/activate
AI_ENABLED=true COURSES_FILE=data/courses.json SETTINGS_FILE=config/settings.json python backend/app.py
# in another shell:
curl -s -X POST localhost:8000/agent/chat -H 'Content-Type: application/json' \
     -d '{"message":"Robotics for an 8 year old in San Jose","lang":"en"}' | python -m json.tool
```

### Docker Compose (backend + frontend; Ollama stays on the Mac)

```bash
ollama list                         # Ollama app running on the Mac, qwen2.5:1.5b installed
docker compose up --build -d
open http://localhost:3000          # "AI Assistant (local model)" panel above the activity list
docker compose down                 # when finished
```

The backend container reaches the host's Ollama at `http://host.docker.internal:11434`.
- **Mac (Docker Desktop):** this works even though Ollama listens only on `127.0.0.1`.
- **Linux:** `extra_hosts: host-gateway` provides the name, but Ollama must then listen on an address the
  container can reach (`OLLAMA_HOST=0.0.0.0`).
- **No second Ollama:** none runs in Docker, and no model is copied.

### Troubleshooting

| Message | Fix |
|---|---|
| `no Ollama server is reachable at …` | Start the Ollama app (or `ollama serve`). In Docker, check `AI_BASE_URL` is `http://host.docker.internal:11434`. |
| `model 'X' is not installed … (installed: …)` | Set `AI_MODEL` to an installed model (`ollama list`), or `ollama pull X` |
| `The AI assistant is turned off` | `AI_ENABLED=true` (Compose sets it by default) |
| `did not answer within 120s` | The first call loads the model into memory; retry, or raise `AI_TIMEOUT` |
| Answer text is wrong but cards look right | Expected occasionally with a 1.5B model: trust the cards and links. A larger Qwen (`AI_MODEL=qwen2.5:7b` after `ollama pull qwen2.5:7b`, about 4.7 GB) follows instructions better; not tested here. |

## Example prompts

- `Robotics for an 8 year old in San Jose`
- `Any events in San Francisco between 2026-11-20 and 2026-11-22?`
- `圣何塞有中文学校吗？`
- `我家孩子7岁，想找编程课`
- `Swimming in Fremont?` (correctly answers that none are tracked)

## Test results (2026-11-16)

**Automated:** `python -m pytest -q` gives **231 passed, 1 skipped**. The skip is the pre-existing real-OCR test
(no Tesseract). `tests/test_agent.py` has 30 tests:

| Area | Tests | Model |
|---|---|---|
| Model-selected tool runs and its result goes back to the model | `test_model_selected_tool_is_executed_and_result_sent_back` | Scripted (fake Ollama HTTP) |
| Multiple tool calls across steps, and several in one step | `test_multiple_tool_calls_narrow_the_results`, `test_several_calls_in_one_step_and_details` | Scripted |
| Unknown tools and invalid arguments are rejected, not executed (10 cases) | `test_invalid_and_unknown_tool_calls_are_rejected_not_executed` | Scripted |
| Extra arguments ignored; too many calls per step | `test_unknown_arguments_are_ignored_and_reported`, `test_too_many_calls_in_one_step_are_skipped` | Scripted |
| Maximum iterations | `test_maximum_iterations_stops_the_loop` | Scripted |
| Answer without tools | `test_answer_without_tools_is_nudged_once_then_flagged` | Scripted |
| No matching activities | `test_no_matching_activities` | Scripted |
| Source URLs preserved; invented links removed; no `<think>` | `test_source_urls_are_preserved_and_invented_links_removed`, `test_private_reasoning_is_never_returned` | Scripted |
| Ollama unreachable / model missing / disabled / non-Ollama provider / bad URL | `test_ollama_unreachable_…`, `test_missing_model_…`, `test_disabled_or_unsupported_configuration` | Real refused connection; scripted tags |
| Endpoint shape; `/courses` unchanged; data file byte-identical | `test_endpoint_returns_cards_and_leaves_the_data_unchanged` | Scripted |
| **Real local inference with an LLM-selected tool** | `test_live_ollama_selects_a_tool_and_answers` | **Real qwen2.5:1.5b** |
| **Real model chaining search → date filter** | `test_live_ollama_chains_search_and_date_filter` | **Real qwen2.5:1.5b** |

**Live runs:**
- **CI behavior:** the two live tests skip themselves when Ollama or the model isn't available, as in CI.
- **Pass rate:** both passed in 5 of 5 consecutive runs (about 4.4 s each, both tests together).

**Docker (manual check, 2026-11-16):**
- **Model visible from the container:** the backend container listed `qwen2.5:1.5b` from `http://host.docker.internal:11434`.
- **Real agent request:** `POST /agent/chat` returned `ok` in about 6.5 s, with one model-selected `search_activities` call
  and 3 cards carrying official links.
- **Frontend proxy:** the same request through the frontend proxy on port 3000 worked.
- **Error messages:** a wrong port and a missing model each returned HTTP 503 with the messages above.
- **Data untouched:** `data/courses.json` was unchanged afterwards.

## Limitations

- **The answer text comes from a small model.** In manual runs, `qwen2.5:1.5b` sometimes:
  - added an unrequested category, which can give "none found" (the tool result then tells it to retry with
    fewer arguments, which it doesn't always do);
  - invented an age the user never gave;
  - emitted 20 tool calls in one step (only 4 ran);
  - named an activity from an earlier, unfiltered step.

  The cards and trace stay accurate; the prose may not. A larger local Qwen would help but was not installed or
  tested.
- **Results vary between runs** even at temperature 0.
- **No memory between messages.** Each request is independent; there is no chat history.
- **Relative dates are the model's job.** "This weekend" relies on the model converting it using today's date,
  which the prompt includes; small models get this wrong at times.
- **Search is the existing keyword and glossary search.** It is not semantic: topics outside the glossary match
  only literally.
- **Answer language** follows the user's language most of the time, but the model doesn't guarantee it.
- **UI checks:** the assistant panel was verified by compiling the frontend and calling the endpoint through its
  proxy. It was not clicked through in a browser for this document.

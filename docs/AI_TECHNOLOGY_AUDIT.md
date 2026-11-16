# AI Technology Audit — AIAgentClassSelect

| | |
|---|---|
| Audited state | Commit `6ba91c9` ("Add Real AI Agent", branch `main`), 2026-11-16. The application code in the working tree is identical to that commit; only this document differs. |
| Added in `6ba91c9` (since `8eb961d`) | `activity_tracker/agent.py`, `frontend/src/Assistant.js`, `tests/test_agent.py`, `docs/AI_AGENT_MVP.md` (new); `backend/app.py`, `activity_tracker/recommend.py`, `frontend/src/App.js`, `docker-compose.yml`, `README.md` (modified) |
| Method | Read the source at the line numbers cited; repo-wide searches for model providers, prompts, vector and agent libraries; list of installed packages; full test suite plus repeated live-model tests; one manual Docker check (Section 8). No cloud model was called. |
| Secrets | None in tracked or new files. The agent uses no API keys. The only credential reference is the built-in `secrets.GITHUB_TOKEN` for the GHCR login (`.github/workflows/docker-build.yml:31`). |

## 1. Executive summary

The project now contains **one real, local LLM integration: an optional AI Assistant with
model-driven tool calling**. A `qwen2.5:1.5b` model served by Ollama on the user's Mac reads a question,
chooses among four Python tools, receives their results, and writes an answer. The loop and its safety checks
are in `activity_tracker/agent.py`. It is exposed as `POST /agent/chat` and as a panel in the React viewer.

Everything else is unchanged and **not** AI:
- discovery (fetching and parsing);
- rule-based extraction of ages, dates and prices;
- change tracking;
- the Markdown report;
- the GitHub Actions workflows.

The assistant is off unless `AI_ENABLED=true`, only reads `data/courses.json`, and is never called by
discovery, the CLI, reports or workflows.

| Capability | Status |
|---|---|
| Local LLM inference (Ollama, `qwen2.5:1.5b`) | Implemented, **tested with real local inference** |
| Model-driven tool selection and execution loop | Implemented, **tested with real local inference** |
| Prompting (system prompt, tool schemas, native tool calls) | Implemented and used |
| Conversation memory, RAG, embeddings, vector search, multi-agent, cloud AI | **Not implemented** |
| OCR (Tesseract) | Implemented, not used by any configured source (unchanged) |
| Extraction, search, recommendations, change detection | Rule-based, not AI (unchanged) |

**Maturity:** a working single-agent MVP on a small local model. The tools and data are grounded; the free-text
answer is only as reliable as a 1.5B model (Section 7).

## 2. AI technology inventory

| Technology | Classification | Evidence |
|---|---|---|
| Ollama (local LLM server) via plain HTTP | IMPLEMENTED_AND_USED (when `AI_ENABLED=true`) | `agent.py:116-163` `OllamaClient`: `GET /api/tags` model check (:132), `POST /api/chat` with tools and `temperature: 0` (:146-163). HTTP is `requests`, an existing dependency; no AI SDK is installed. |
| Qwen 2.5 1.5B (`qwen2.5:1.5b`, Q4_K_M) | IMPLEMENTED_AND_USED | Default model `agent.py:27`; Compose default `docker-compose.yml:17`. The local Ollama 0.40.11 lists it, with `tools` among its capabilities. |
| Tool / function calling (Ollama native `tool_calls`) | IMPLEMENTED_AND_USED | Tool schemas `agent.py:65-85`; loop `agent.py:367-404` |
| Custom single agent (no framework) | IMPLEMENTED_AND_USED | `run_agent` `agent.py:367-404`; dispatch `agent.py:326-349` |
| System prompt and prompt construction | IMPLEMENTED_AND_USED | `SYSTEM_PROMPT` `agent.py:48-61` (today's date and category keys filled in at :369-370); nudge `agent.py:62` |
| OpenAI, Anthropic, Gemini, Hugging Face, other cloud providers | NOT_FOUND | No package or import. `AI_PROVIDER` values other than `ollama` are refused (`agent.py:419-421`). |
| LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen, Agents SDK | NOT_FOUND | No package or import |
| Embeddings, vector database, semantic search | NOT_FOUND | Search is the existing glossary/keyword search (`search.py:55-79`) |
| RAG | NOT_FOUND | No document chunking, embedding or retrieval-to-context step. Tools return structured records. |
| Conversation memory | NOT_FOUND | Each request starts a new message list (`agent.py:369-371`); no history is stored |
| Multi-agent orchestration | NOT_FOUND | One model, one loop |
| OCR (Tesseract via subprocess) | IMPLEMENTED_BUT_NOT_USED | `ocr.py:27-39`; no configured source uses `parser: "poster"` (unchanged) |
| Rule-based extraction, language detection, glossary search, recommendation filters, change detection | IMPLEMENTED_AND_USED (not AI) | Section 6 |
| Machine translation | CONFIGURED_BUT_NOT_IMPLEMENTED | Label only (`i18n.py:7,14`); none generated (unchanged) |

## 3. LLM integration and execution path

**Configuration** comes only from the environment (`AgentSettings.from_env`, `agent.py:97-113`):

| Variable | Default | Notes |
|---|---|---|
| `AI_ENABLED` | off | `true` turns the assistant on |
| `AI_PROVIDER` | `ollama` | Only accepted value |
| `AI_MODEL` | `qwen2.5:1.5b` | |
| `AI_BASE_URL` | `http://localhost:11434` | Must be `http(s)`; otherwise the request is refused with an error (`agent.py:119-121`) |
| `AI_TIMEOUT` | 120 s | |
| `AI_MAX_ITERATIONS` | 5 | |

**Execution path:**

```
React panel  frontend/src/Assistant.js:45 fetch("/agent/chat")      (mounted at frontend/src/App.js:80)
 → Flask     backend/app.py:72-85 agent_chat
             load_courses (app.py:28-37): same list as GET /courses (no past, adult or duplicate records)
 → agent     handle_chat (agent.py:407-428): validates message (≤500 chars), AI_ENABLED, provider;
             OllamaClient.check_model → GET /api/tags
 → loop      run_agent (agent.py:367-404), at most AI_MAX_ITERATIONS model calls:
               POST /api/chat {messages, tools, temperature 0}
               tool_calls → ActivityTools.execute (agent.py:326-349): fixed dispatch table, validate (:277-324),
                            run tool, result appended as a "tool" message
               text       → clean_answer (agent.py:360-364) → final response
 → response  {answer, activities, tools_used, agent_status, model, error}; activities formatted by
             course_item (app.py:40-43), the same shape as GET /courses
```

**Error handling:**
- Server unreachable, model not installed, timeout, non-200 response and malformed replies all raise
  `OllamaError` (`agent.py:125-163`).
- These return HTTP 503 with `agent_status: "unavailable"` and a specific message (`agent.py:426-427`).
- There is **no cloud fallback**.

**Docker:** `docker-compose.yml:12-20` points the backend at the host's Ollama via
`http://host.docker.internal:11434`, with `extra_hosts: host-gateway`. No Ollama runs inside Docker.

## 4. Prompts and tools

**Prompt:** one system prompt (`agent.py:48-61`) states the rules:
- call a tool before answering;
- never invent activities, ages, dates, prices or links;
- call `filter_by_age` or `filter_by_date` when the user gives an age or dates;
- answer briefly in the user's language.

There are no few-shot examples and no JSON-mode output.

**Tools** (`agent.py:70-82` schemas, `agent.py:196-275` implementations). All four are read-only and reuse
existing logic:

| Tool | Reuses | Notes |
|---|---|---|
| `search_activities(keyword?, category?, location?)` (`agent.py:223-243`) | `search.search` + `Glossary`, `extract.detect_cities` | Starts a new result set. "Bay Area" or 湾区 is not a city filter (`agent.py:44`). Generic words like "classes" or 课 are dropped (`agent.py:166-170`). An empty multi-filter result asks the model to retry with fewer arguments. |
| `filter_by_age(age)` (`agent.py:245-255`) | `recommend.age_fit`, `age_fit_note` | Narrows the latest results; reports how many records had no published age |
| `filter_by_date(start_date, end_date?)` (`agent.py:257-267`) | `recommend.date_span` (new helper, `recommend.py:55-66`, same date parser as the lifecycle rule) | Overlap test; reports how many undated records were left out |
| `get_activity_details(activity_id)` (`agent.py:269-275`) | — | Published fields, including `detail_url`, `registration_url`, `source_url` and `original_event_url` |

**Guards:**
- **Unknown tool names are rejected** without execution (`agent.py:333-335`), and arguments are type- and
  range-checked (`agent.py:277-324`).
- **Unknown extra arguments** are ignored and listed in the trace.
- **Limits:** at most 4 tool calls per model step (`agent.py:387,397-401`) and at most 5 model calls per request.
- **No answer from memory:** a reply given without any tool is nudged once, then flagged `no_tools_used`
  (`agent.py:378-385`).
- **Clean answers:** `<think>` blocks are removed, and URLs not present in the activity data are replaced
  (`agent.py:360-364`).
- **Small context:** older list results are collapsed to a "superseded" note (`agent.py:392-395`).
- **No code execution:** no Python, shell or SQL is ever executed from model output.

## 5. Embeddings, vector search, RAG, memory

Not implemented. The assistant's "retrieval" is the existing structured search and filters, invoked as tools.
Answers are grounded in tool results, but that is tool calling over structured data, not RAG: there is no
document chunking, embedding, vector store or retrieved-passage context. There is no memory across requests.

## 6. Non-AI processing (unchanged)

| Area | Technique | Evidence |
|---|---|---|
| Fetching | `requests`, robots.txt, per-host delay, retries | `fetcher.py:48-109` |
| Parsing and extraction | BeautifulSoup, JSON-LD, Next.js payload, EN/ZH regex for ages, prices, dates, schedules | `extract.py:29-110,182-290,413-780` |
| Language and script | Character counts; Traditional→Simplified table | `i18n.py:19-55` |
| Search | Curated bilingual glossary + literal match, title-weighted score | `search.py:15-79` |
| Recommendations | Date lifecycle, age overlap, adult-title rules; filtering only, no ranking model | `recommend.py:69-169` |
| Change detection | Field-by-field normalized diff, bounded history | `tracker.py:64-68,131-182` |
| OCR | System Tesseract; not used by any configured source | `ocr.py:27-39`, `extract.py:744-761` |

## 7. Grounding and known limitations

**What is grounded:**
- **Activity cards** are the records from the latest search/filter tool results plus any detail lookups
  (`ActivityTools.shown`, `agent.py:351-353`).
- **Links** on the cards are the records' own official URLs.
- **The trace** (`tools_used`) is the real list of calls with validated arguments and result counts.

**What is not:** the **answer text** is written by a 1.5B-parameter model and **can be inaccurate**. In manual
runs on 2026-11-16, `qwen2.5:1.5b`:
- added categories the user didn't ask for, sometimes producing "none found";
- invented an age the user never gave;
- once emitted 20 tool calls in a single step (only 4 ran);
- named an activity from an earlier, unfiltered result while answering a date question.

The cards and trace stayed correct in each case; only the prose was wrong.

**Other limitations:**
- Results vary between runs even at temperature 0.
- There is no conversation memory.
- Relative dates ("this weekend") depend on the model's date arithmetic.
- Search is keyword and glossary based, not semantic.
- A larger local model was not installed or tested.
- On Linux hosts, Ollama must listen on an address the container can reach.

## 8. Test coverage and runtime verification

**Automated, verified for this update.** `python -m pytest -q` gives **231 passed, 1 skipped**. The skip is
the pre-existing real-OCR test (no Tesseract). `tests/test_agent.py` collects **30 tests** (19 functions, two
parametrized):

| Category | Tests | Model |
|---|---|---|
| Implemented and tested (scripted) | Tool executed and result returned; multi-step and same-step calls; 10 invalid/unknown-call cases; ignored arguments; per-step cap; iteration limit; nudge and `no_tools_used`; no matches; Bay Area handling; URL preservation and invented-link removal; `<think>` removal; missing model; disabled, non-Ollama and bad-URL configurations; endpoint shape, `GET /courses` unchanged, data file byte-identical | Fake Ollama HTTP session (runs in CI, no model needed) |
| Real failure path | `test_ollama_unreachable_gives_a_clear_error` | Real refused connection to `127.0.0.1:9` |
| **Tested with real local inference** | `test_live_ollama_selects_a_tool_and_answers`; `test_live_ollama_chains_search_and_date_filter` (model must call both `search_activities` and `filter_by_date`) | **Real Ollama 0.40.11 + `qwen2.5:1.5b`**; both skip when unavailable (e.g. in CI) |

**Live tests:** both passed in 5 of 5 runs during implementation, and in 3 of 3 more runs for this update
(about 4.4 s per run, both tests together).

**Docker (manual check during implementation on 2026-11-16, not repeated for this update):**
- **Model visible:** the backend container listed `qwen2.5:1.5b` from `http://host.docker.internal:11434`.
- **Real request:** `POST /agent/chat` returned `ok` in about 6.5 s with a model-selected `search_activities`
  call and 3 cards with official links.
- **Frontend proxy:** the same endpoint worked through the frontend proxy on port 3000.
- **Error messages:** a wrong port and a missing model each returned HTTP 503 with specific messages.
- **Data untouched:** `data/courses.json` was unchanged afterwards.

**Not verified:**
- The React panel was compiled ("Compiled successfully!") and its endpoint exercised through the proxy, but
  it was not clicked through in a browser.
- Answer-text accuracy has no automated evaluation.

## 9. README and GitHub positioning

| Item | Current claim | Recommendation |
|---|---|---|
| Repo name "AIAgentClassSelect" | AI agent | **KEEP.** A local tool-calling agent now exists. |
| GitHub description "AI-powered course selection agent … saas aws" | AI-powered, SaaS, AWS | **REWORD**, e.g. "Bay Area kids' activity tracker: rule-based extraction from official pages, change history, bilingual viewer, and an optional local AI assistant (Ollama + tool calling)." No SaaS or AWS code exists. |
| Topics `ai`, `agent` | | **KEEP** |
| Topics `saas`, `aws` | | **REMOVE** |
| Topic `dokcer` | | **REWORD** to `docker` |
| `README.md` "AI Assistant (optional, local)" section | Local Ollama tools assistant; cards from tool results; off unless enabled | **KEEP.** Accurate. |
| `README.md:7` | "no schedule, no paid API and no secrets" | **KEEP.** Still true. |
| `README.md:33` | "There are no ratings or recommendations." | **REWORD.** Rule-based default filtering exists; no ratings. |
| `doc/worflowchinese.md` | Discovery workflow "调用 GPT API 摘要", weekly cron | **REWORD** or label as an early design. Discovery uses no LLM and has no schedule. |
| Terms "RAG", "semantic search", "machine learning", "memory", "multi-agent" | Not claimed | **Do not introduce.** Not implemented. |

## 10. Roadmap (updated)

1. **Done:** LLM natural-language queries over the existing filters, as a local tool-calling assistant.
2. **Answer accuracy:** evaluate a larger local Qwen behind `AI_MODEL`, and add a small offline evaluation set
   of prompts with expected tool calls.
3. **Optional conversation memory** (prior turns in the request) if follow-up questions matter.
4. **Semantic search, RAG over official pages, multi-agent:** still deferred, for the reasons in the historical
   audit below. Not needed for the current data size, and RAG would add hallucination and copyright risk.

## Historical: audit of commit `8eb961d` (before the AI Assistant)

At `8eb961d`, the project had **no LLM, no prompts, no tool calling and no agent**. No model SDK or model HTTP
call existed. Only OCR (unused) was model-adjacent, and everything else was the rule-based pipeline in
Section 6. That audit flagged the repository name, GitHub description and topics, and `doc/worflowchinese.md`
as overstating AI capabilities. The name and the `ai`/`agent` topics are now supported by the assistant; the
other findings in Section 9 still apply.

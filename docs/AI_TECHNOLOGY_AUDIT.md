# AI Technology Audit — AIAgentClassSelect

| | |
|---|---|
| Audited commit | `8eb961d` (branch `main`, clean working tree) |
| Audit date | 2026-11-15 |
| Scope | All 46 tracked files outside `tests/fixtures/` (37 fixture files checked only as test inputs). `.venv/`, `node_modules/`, caches and build output excluded. |
| Method | Static reading of the source, repo-wide searches for provider SDKs, model names, prompts, vector/agent libraries and key patterns, a list of installed packages, the existing offline test suite, and a read-only look at the GitHub repository description. No model API was called and nothing was installed. |
| Secrets | A pattern search for API keys, tokens and private keys found **none** in tracked files. The only credential reference is the built-in `secrets.GITHUB_TOKEN` used for the GHCR login in `.github/workflows/docker-build.yml:31`. |

---

## 1. Executive summary

**The project contains no generative AI, no machine-learning model and no AI agent.** It is a
well-tested, deterministic, rule-based web-data pipeline:

> polite HTTP fetching → HTML / JSON-LD / Next.js-payload parsing with BeautifulSoup and regular expressions →
> rule-based field extraction (ages, dates, prices, schedules in English and Chinese) → ID assignment and
> field-by-field change detection → rule-based filtering ("recommendations") → Markdown report, Flask API and
> React viewer.

- **LLM integration: NOT_FOUND.** No provider SDK is in `requirements*.txt`, `package.json` or the installed
  virtual environment. No code calls a model endpoint. The only outbound HTTP code is the page fetcher
  (`activity_tracker/fetcher.py:76,96`) and the frontend's call to its own backend (`frontend/src/App.js:55`).
- **Prompts, embeddings, vector search, RAG, agents: NOT_FOUND.**
- **The only "AI-adjacent" technology is OCR** (system Tesseract, a classical OCR engine with an LSTM text
  recognizer bundled inside the binary). It is implemented and tested with a stub, but **no configured source
  uses it**, Tesseract is not installed in CI or the Docker image, and 0 of the 637 stored records came from OCR.
- **Everything else that looks intelligent is rules**: regex extraction, a hand-written bilingual glossary
  (29 concepts), a Traditional→Simplified character table, character-count language detection, and
  date/age/title rules for what to recommend.

**AI maturity: Level 0 (no AI in operation).** The engineering quality of the non-AI parts is high: 202 offline
tests, explicit "never guess" rules, provenance on every field. The repository's **name, GitHub description and
topics** ("AIAgentClassSelect", "AI-powered course selection agent", topics `ai`, `agent`) and one design
document (`doc/worflowchinese.md`, "调用 GPT API") describe AI capabilities that do not exist in the code.
The README body itself is accurate about this ("no paid API and no secrets", "None are generated today").

---

## 2. AI technology inventory

| # | Technology | Classification | Evidence | Operational status |
|---|---|---|---|---|
| A1 | OpenAI / GPT | NOT_FOUND | No `openai` package, import, endpoint, model name or `OPENAI_*` variable in code. The only occurrence is a guard asserting its absence: `tests/test_workflow.py:30`. Mentioned in prose only in `doc/worflowchinese.md:7,18,71`. | Not present |
| A2 | Anthropic / Claude | NOT_FOUND | No package, import or endpoint | Not present |
| A3 | Google Gemini | NOT_FOUND | No package, import or endpoint | Not present |
| A4 | Ollama / local LLM | NOT_FOUND | No package, import or `localhost:11434`-style call | Not present |
| A5 | Hugging Face Transformers / Inference API | NOT_FOUND | No `transformers`, `huggingface_hub` or `torch` | Not present |
| A6 | Other providers (Mistral, Cohere, …) | NOT_FOUND | No package, import or endpoint | Not present |
| B | Prompts, templates, few-shot, JSON mode, tool calling | NOT_FOUND | No prompt strings and no message/role structures. Repo-wide search for `prompt` in code: 0 hits. | Not present |
| C | Embeddings / semantic similarity | NOT_FOUND | No embedding model, vectors or cosine similarity. Similarity is exact field comparison: `search.py:91-112`. | Not present |
| D | Vector database (FAISS, Chroma, Pinecone, Qdrant, pgvector, …) | NOT_FOUND | Storage is JSON files: `tracker.py:71-99` (`Store`) | Not present |
| E | RAG pipeline | NOT_FOUND | None of the retrieve → construct context → generate steps exist | Not present |
| F1 | Agent framework (LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen, Agents SDK) | NOT_FOUND | No package or import | Not present |
| F2 | Custom agent (model-driven tool selection or loop) | NOT_FOUND | `cli.py:23-136` `run_discovery` is a fixed, configuration-driven loop over sources; no model decides anything | Not present |
| G1 | OCR (Tesseract via subprocess) | IMPLEMENTED_BUT_NOT_USED | `ocr.py:27-39` `ocr_image`; called from `extract.py:744-761` `extract_poster` when `parser == "poster"` (`extract.py:767-768`) | Code path works, verified with a stub. **No source in `config/sources.json` uses `poster`**, Tesseract isn't installed in CI or Docker, and 0 of 637 records came from OCR. |
| G2 | Rule-based information extraction (regex, EN + ZH) | IMPLEMENTED_AND_USED | `extract.py:29-110` patterns; `parse_age` :182, `find_price` :203, `find_dates` :243, `find_schedule` :269, `find_enrollment` :275 | Runs on every discovery run |
| G3 | Rule-based language / script detection | IMPLEMENTED_AND_USED | `i18n.py:40-55` `detect_language` (character counts, no model) | Runs on every record |
| G4 | Dictionary-based script conversion and bilingual synonyms | IMPLEMENTED_AND_USED | `i18n.py:36-37` `to_simplified` (character table); `search.py:15-31` `Glossary`, with 29 concepts in `config/settings.json` | Used by search and duplicate linking |
| G5 | Keyword search with simple scoring | IMPLEMENTED_AND_USED | `search.py:55-79` (AND match; title hits score higher) | `GET /courses?q=` (`backend/app.py:46-50`) |
| G6 | Rule-based "recommendation" filter | IMPLEMENTED_AND_USED | `recommend.py:55-77` lifecycle, `:80-96` age_fit, `:134-144` audience, `:147-155` not_recommended_reason | Report (`report.py:162-167`) and API (`backend/app.py:43-45`) |
| G7 | Change detection (diff) | IMPLEMENTED_AND_USED | `tracker.py:64-68` `diff_fields`; `:131-182` `merge_source` | Every run |
| G8 | Machine translation | CONFIGURED_BUT_NOT_IMPLEMENTED | The label `"machine"` exists (`i18n.py:7,14`; `App.js:10`), but no code generates translations. The README says "None are generated today" (`README.md:70`). Stored data has 0 translations of any method. | Display label only |
| G9 | ML models, classifiers, NER, ranking models, NLP libraries (spaCy, NLTK, jieba, scikit-learn, …) | NOT_FOUND | None installed or imported | Not present |

No technology is classified DEPENDENCY_ONLY: **no AI-related package is declared or installed at all.**
The installed environment contains only beautifulsoup4, requests, Flask, flask-cors, pytest, PyYAML and their
transitive dependencies. The frontend depends only on react, react-dom and react-scripts.

---

## 3. LLM and model integration

**No LLM integration exists.**

| Check | Result |
|---|---|
| SDK dependencies | None. `requirements.txt` has `requests` and `beautifulsoup4`; `requirements-dev.txt` adds `pytest`, `PyYAML`, `flask` and `flask-cors`; `frontend/package.json` has `react`, `react-dom` and `react-scripts`. |
| HTTP calls to model APIs | None. All Python HTTP goes through `Fetcher.get` (`fetcher.py:86-109`) to the configured provider pages and their `robots.txt` (`fetcher.py:69-84`). The frontend only calls `/courses` (`App.js:55`). |
| Model initialization or configuration | None. `config/settings.json` has no model, endpoint or key fields. |
| API key handling | None. The code reads only `COURSES_FILE`, `SETTINGS_FILE` and `TODAY` (`backend/app.py:16,17,41`). |
| Inference execution | None |
| Error handling / fallback for models | Not applicable. The existing fallbacks are for fetching (`merge_source` keeps data when a source fails, `tracker.py:143-148`), OCR (`OCRUnavailable`, `ocr.py:15,30,33,38`) and time zone (`recommend.py:37-39`). |

The test suite actively guards against an AI dependency entering discovery:
`tests/test_workflow.py:25-30` asserts the discovery workflow contains no `secrets.` and no `OPENAI`.

**Execution path for any AI claim:** none can be traced. There is no model invocation anywhere between an entry
point (`python -m activity_tracker` → `cli.py:152` `main`, `GET /courses` → `backend/app.py:27`, or the React app)
and its output.

---

## 4. Prompt engineering

**NOT_FOUND.** There are no system prompts, user prompts, templates, few-shot examples, JSON-mode or
structured-output schemas, or tool/function definitions. The only "prompt-like" texts are:

- UI placeholder strings for the search box (`frontend/src/App.js:6,13,20`), which are shown to people, not models.
- `doc/worflowchinese.md`, which describes a planned "AI 智能处理 → 调用 GPT API" step but contains no prompt
  and has no corresponding code.

---

## 5. Embeddings, vector search and RAG

### What exists (non-AI)

| RAG-like step | What the project does instead | Evidence |
|---|---|---|
| 1. Data ingestion | Fetches configured official pages (robots.txt, per-host delay, retries) | `fetcher.py:48-109`, `cli.py:55` |
| 2. Document parsing | BeautifulSoup HTML, JSON-LD, Next.js flight payload, CSS-selector listings | `extract.py:413-780` |
| 3. Chunking | Not done. Records are extracted as structured fields, not text chunks. | — |
| 4. Embedding generation | **NOT_FOUND** | — |
| 5. Vector storage | **NOT_FOUND.** Structured JSON in `data/courses.json` | `tracker.py:71-99` |
| 6. Retrieval | Keyword/glossary match with AND semantics and title-weighted integer score | `search.py:55-79` |
| 7. Context construction | **NOT_FOUND** | — |
| 8. LLM generation | **NOT_FOUND** | — |
| 9. Source attribution | Present, but for extracted data, not generated text: every record keeps `source_url`, `detail_url` and an `extraction` method, and the report links each row to the official page | `extract.py:353-365` `_base_record`; `report.py:33-38` `link` |

### Cross-language matching is not semantic search

"机器人" finds "robotics" because both are listed as terms of the same glossary concept in
`config/settings.json`, segmented longest-first (`search.py:15-31`). A query word that is not in the glossary
is matched literally (`search.py:76`). Synonyms outside the glossary ("droid", "STEAM lab") will not match.
This is curated dictionary lookup, not semantic search.

**Conclusion:** steps 1, 2, 6 and 9 exist in a non-AI form. Steps 3, 4, 5, 7 and 8 do not exist. **There is no
RAG pipeline, no embedding and no vector search.**

---

## 6. Agent architecture

**No AI agent exists.**

| Agent property | Present? | Evidence |
|---|---|---|
| Model-driven decisions or tool selection | No | No model is present (Section 3) |
| Tool execution chosen at run time | No | `cli.py:23-136` iterates `config.sources` in order and calls a parser chosen by each source's configured `parser` field (`extract.py:764-780`) |
| Planning or multi-step reasoning | No | Fixed pipeline: fetch → extract → geo-filter → assign IDs → merge → link duplicates → annotate → save (`cli.py:55-132`) |
| Memory and state | Persistent *data* state only (`data/*.json`), not agent memory | `tracker.py:71-99` |
| Agent loop with termination conditions | No. The loop ends when the configured source list ends. | `cli.py` |
| Autonomous task selection | No. Discovery mode only *suggests* links that match configured keywords, for human review. | `discovery.py:1-5,26-50` |

The closest thing to autonomy is `discover_new_sources` mode: `find_candidates` (`discovery.py:26-50`) scans
anchors on known pages with configured keyword regexes and writes suggestions to
`data/candidate_sources.json`. It never adds a source by itself. This is deliberate, conservative design, but
it is keyword matching, not an agent.

The word "Agent" appears only in the repository name, the GitHub description and topics, and the HTTP
`User-Agent` header (`fetcher.py:56`).

---

## 7. Traditional NLP, OCR and rule-based processing

These are the project's real "intelligent" capabilities. None of them is generative AI or machine learning.

| Capability | Technique | Evidence | Strengths | Limits |
|---|---|---|---|---|
| Age extraction | Regex for EN ("ages 7-9", "Grades K-2") and ZH ("7-9岁", "一至三年级", "8岁及以上"); grade→age table; refuses ambiguous multi-statement notes | `extract.py:45-53,153-200,696-716` | Never guesses; handles full-width text and Chinese numerals | Phrasings outside the patterns are missed (age stays "Not published") |
| Price | Regex for $, 美元/元, units (/week, /周); skips deposits, fees and discounts | `extract.py:55-64,203-220` | Explicit skip list | First matching price only; no currency normalization |
| Dates / schedule | Regex for EN/ZH ranges, numeric and Y-M-D dates; year hint from the page | `extract.py:66-84,243-273` | A single date or one without a year is not guessed | Free-form phrasing ("every other Saturday") not interpreted |
| Enrollment / season | Pattern lists | `extract.py:85-108,275-290` | Bilingual | Fixed vocabulary |
| City / region | Alias table plus Bay Area terms | `extract.py:292-302,719-741` | Chinese city names (圣何塞 → San Jose) | Only cities in the table |
| Language detection | Count of CJK vs Latin characters; Simplified/Traditional character sets | `i18n.py:40-55` | Fast, deterministic | Heuristic; short mixed strings may be "mixed" |
| Script conversion | Character pair table | `i18n.py:19-37` | Search works across scripts | Limited table, not a full converter |
| Bilingual search | Curated glossary (29 concepts) + literal match, title-weighted score | `search.py:15-79` | Precise and explainable | No fuzzy, typo-tolerant or semantic matching |
| Cross-language duplicates | Same site + same registration URL, or equal dates/ages + shared glossary concept | `search.py:91-112,140-168` | Conservative (missing fields never match) | Misses pairs with no shared glossary term |
| Aggregator duplicates | Exact original-URL match to exactly one provider record | `search.py:115-137` | Ambiguous matches are not linked | Exact URLs only |
| Recommendation filter | Lifecycle from explicit dates in the Bay Area time zone; age-range overlap; adult/child title regex | `recommend.py:31-155` | Transparent reasons ("past", "adult course", "age mismatch") | Filtering only: no ranking, personalization or preference learning |
| Change detection | Field-by-field normalized comparison with bounded history | `tracker.py:13-14,19-29,64-68,131-182` | Never deletes history; failed sources never downgrade data | Exact-field diff; no semantic "is this meaningfully different" |
| Source discovery | Keyword regex over links on known pages | `discovery.py:15-50` | Suggestions only | Only the same site; keyword-limited |
| OCR | System Tesseract (`chi_sim`, `chi_tra`, `eng`, `--psm 6`) via `subprocess`, then the same regex extraction | `ocr.py:19-39`, `extract.py:744-761` | No Python ML dependency; fails loudly when unavailable | **Not used by any configured source;** quality on stylized posters is untested |

Tesseract 4+ uses an LSTM neural network internally, so OCR is the one place a trained model would run. It is
an external binary, though, not a model the project trains, loads or calls through an AI API. Even this is
dormant in production today.

---

## 8. Test coverage and runtime verification

`python -m pytest -q` at the audited commit: **202 collected, 201 passed, 1 skipped**. The skip is the real-OCR
test (`tests/test_i18n.py:281`, Tesseract with `chi_sim` not installed on the audit machine). All tests are
offline.

| Capability | Tested? | How | Evidence |
|---|---|---|---|
| Any LLM / embedding / RAG / agent | Not applicable (nothing to test) | No mocked model calls exist either | — |
| Absence of AI and secrets in discovery | Yes | Asserts no `secrets.` or `OPENAI` in `discover.yml` | `tests/test_workflow.py:25-30` |
| HTML/JSON-LD/listing/section/aggregator extraction | Yes | Real HTML fixtures (`tests/fixtures/`) | `tests/test_extract.py`, `tests/test_six_sources.py`, `tests/test_runs.py` |
| EN/ZH age, price, date, schedule rules | Yes | Fixture text and parametrized cases | `tests/test_i18n.py`, `tests/test_six_sources.py`, `tests/test_recommend.py` |
| OCR pipeline | **Stub only** | `ocr_image` is monkeypatched to return fixture text; the "tesseract missing" path is tested; the real engine test is skipped here | `tests/test_i18n.py:269,281,290,298` |
| Fetching / robots / retries | Yes, with mocks | `MagicMock` HTTP session (no network) | `tests/test_fetcher.py:1-16` |
| Search and duplicate linking | Yes | Rule-based expectations | `tests/test_i18n.py`, `tests/test_six_sources.py` |
| Recommendation filter, time zone, API | Yes | Pinned clock, Flask test client | `tests/test_recommend.py` |
| Change detection | Yes | Two-run fixture comparisons | `tests/test_tracker.py`, `tests/test_runs.py` |
| Real OCR on real posters | **Not verified** | — | — |
| Live-site extraction accuracy | Not verified by tests (by design: offline) | Covered only by manual live runs recorded in `data/` | — |

---

## 9. README and GitHub positioning review

### Where AI terminology appears

| Location | Text | Code reality | Recommendation |
|---|---|---|---|
| Repository name / README title (`README.md:1`) | "AIAgentClassSelect" | No AI and no agent | **KEEP the name** (renaming breaks URLs, GHCR package names and `docker-build.yml` tags), but **REWORD the title line**. See the wording below. |
| GitHub description | "AI-powered course selection agent with web UI and Docker deployment saas aws" | Not AI-powered; not an agent; no SaaS or AWS code or configuration in the repo | **REWORD** |
| GitHub topics | `ai`, `agent` | Not supported by code | **REMOVE**. Better-fitting topics: `web-scraping`, `bilingual`, `chinese`, `flask`, `react`, `github-actions` |
| GitHub topics | `saas`, `aws` | No multi-tenant service and no AWS code or configuration | **REMOVE** (or FUTURE ROADMAP ONLY) |
| GitHub topics | `dokcer` | Typo | **REWORD** to `docker` |
| `doc/worflowchinese.md:7,18,28,70-74` | "AI 处理 → GPT API 摘要", "AI 智能处理 / 调用 GPT API", "推荐等级/标签" | No GPT call, no summarization, no rating | **FUTURE ROADMAP ONLY**: mark the file as an early design sketch, or move the GPT step to a "planned" section |
| `doc/worflowchinese.md:15,26,47` | "每周定时触发 / 定时触发 (cron)" (weekly schedule) | No schedule, and a test forbids one (`tests/test_workflow.py:25-27`) | **REWORD** (not AI, but equally inaccurate) |
| `doc/classdemo.md` | Hand-written list of "recommended" Bay Area programs for ages 6–7 | Static text; not produced by the code. Its origin cannot be verified from the repo. | **REWORD** with a heading saying it is a manual note, not tool output |
| `README.md:33` | "There are no ratings or recommendations." | Partly outdated: the report now has rule-based "default recommendations" that hide past, adult and age-mismatched activities (`report.py:162-167`). There are still no ratings. | **REWORD** |
| `README.md:7` | "no paid API and no secrets" | Accurate | **KEEP** |
| `README.md:67-70` | "machine translation … None are generated today" | Accurate | **KEEP** |
| `README.md:80-82` | Glossary-based search | Accurate and appropriately non-AI | **KEEP** |
| `README.md:86-89` | Optional OCR via tesseract | Accurate | **KEEP**; optionally add "no source uses it yet" |

### Terms checked

| Term | Used where? | Supported by code? | Recommendation |
|---|---|---|---|
| AI-powered | GitHub description | No | **REMOVE** |
| AI Agent | Repo name, description, topics | No | **REWORD** the description; **FUTURE ROADMAP ONLY** for actual agent features |
| LLM / GPT | `doc/worflowchinese.md` | No | **FUTURE ROADMAP ONLY** |
| RAG | Not used anywhere | No | Don't introduce it |
| Semantic search | Not used anywhere | No | Don't introduce it; say "bilingual glossary search" |
| Machine learning | Not used (only "machine translation", correctly marked as not generated) | No | Don't introduce it |
| AI recommendation | Implied by "AI-powered course selection agent" and "推荐等级" | Recommendations are rule-based filters | **REWORD** as "rule-based filtering by date, age and audience" |

### Suggested replacement wording (evidence-based)

**GitHub description** (under 350 characters):

> Personal tracker for Bay Area kids' classes and camps: fetches official provider pages politely, extracts
> ages, dates and prices from English and Chinese text with rules, tracks changes over time, and serves a
> bilingual Flask + React viewer. Manual GitHub Actions runs, no paid APIs.

**README title line:**

> # AIAgentClassSelect — Kids Activity Discovery & Tracking
>
> *(The name is historical: the tool is rule-based and uses no AI models today. See
> `docs/AI_TECHNOLOGY_AUDIT.md`.)*

**`README.md:33`:**

> There are no ratings. The report's default list leaves out activities that are past, explicitly for
> adults, or outside the requested ages (by published values only). Hidden records stay in the history.

---

## 10. Recommended AI roadmap

The project's existing principles constrain any AI addition: **never invent activity information, keep
discovery free of paid APIs and secrets, keep tests offline, and keep children's and parents' data out of
third-party services.** Each item below is weighed against those. With 637 records, 29 glossary concepts
and one primary user, the bar for adding AI is high. **Step 0 (free, do first): correct the positioning in
Section 9.**

| Priority | Item | Benefit | Cost and complexity | Dependencies and risks | Verdict |
|---|---|---|---|---|---|
| 1 | **LLM natural-language query → structured filters** ("周六 圣何塞 机器人 适合8岁" → `{category: stem, city: San Jose, age: 8, day: Sat}`) | Real usability gain for a bilingual parent; the model only *parses the question* into the existing filters and never states facts about activities | Low. One structured-output call per query, short input, no activity data sent. Can run on a small hosted model or a local model (Ollama). | Needs an API key (breaks "no secrets" for the viewer, though not for discovery) or a local model runtime. Needs an offline fallback to the current glossary search. Tests must mock the model. | **Worth doing, optional and off by default** |
| 2 | **AI-assisted recommendations** | Explaining or ranking the already-filtered list ("closest to home, fits Saturdays") | Low to medium | Must stay *on top of* the rule-based filter (`recommend.py`), never override published ages or dates. Personalization needs user preferences, which raises privacy questions. Little gain at this data size. | **Later; only as explanation or ranking of rule-filtered results** |
| 3 | **Multilingual semantic search (embeddings)** | Catches synonyms outside the glossary | Medium. A multilingual embedding model adds hundreds of MB (and PyTorch) to the backend image, or needs a hosted embeddings API. Index rebuilt per run. A plain array suffices at 637 records; no vector DB needed. | Must keep glossary results first (precision). Harder to explain why something matched. Adding glossary terms is cheaper for now. | **Defer** until glossary maintenance becomes a burden |
| 4 | **RAG over official provider pages** | Answering detail questions ("is lunch provided?", "what's the refund policy?") with citations | High. Store page text, chunk, embed, retrieve, generate with citations, evaluate faithfulness. | Hallucination risk directly conflicts with "never invent activity information"; it would need strict citation and abstention. Pages change often; storing full page text raises copyright and robots questions. | **Future roadmap only** |
| 5 | **Tool-calling AI agent** | Autonomous discovery or monitoring | High, with ongoing per-run model cost | Conflicts with design rules: the fixed, polite, robots-respecting pipeline is a feature. An agent choosing what to fetch is harder to bound and audit. A no-registration/purchase rule must remain absolute. | **Not recommended** for this project's goals |

If only one item is pursued, item 1 gives the most user value per unit of cost and risk, provided it ships with
a deterministic fallback, mocked tests and an explicit opt-in setting.

---

## Appendix — Uncertainties and unverified areas

- **Real OCR quality** on actual posters was not tested: Tesseract isn't installed on the audit machine, and no
  production source uses the poster parser.
- **GitHub metadata** (description and topics) was read with `gh repo view`. Settings outside the repository
  (GitHub Apps, external deployments, any AWS account) cannot be audited from the source and were not checked.
- **`doc/classdemo.md`** may originally have been written with help from an AI chat assistant. The repository
  can't show that either way. It is static text, not produced or used by the code.
- **Tesseract's internal LSTM** is part of an external binary. The project neither configures nor trains a model.
- This audit covers commit `8eb961d`. Uncommitted or other-branch work is not included.

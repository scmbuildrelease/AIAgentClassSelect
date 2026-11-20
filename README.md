# AIAgentClassSelect — Kids Activity Discovery & Tracking

Find kids' classes, camps and activities in the **San Francisco Bay Area**, from your Mac and your iPhone,
with an optional AI assistant that runs entirely on your own computer.

The project has two parts:

1. **A personal app** you run on your Mac with Docker and open in a browser on the Mac or on an iPhone on the same
   Wi-Fi. No account, cloud server, paid service, API key, Apple Developer account or App Store app.
2. **An activity tracker** that checks official provider pages for new and changed activities. It runs when the
   maintainer starts it in GitHub Actions and commits the results to `data/courses.json`, which the app reads.

Each person who installs the app runs their own independent copy; nothing is shared between installations.

## Features

- **Discover**: search in English or Chinese (机器人 = robotics, 夏令营 = summer camp), filter by category, the
  child's age, city and dates. Each card shows ages, dates, price and place as the source publishes them ("Not
  published" otherwise, never guessed) and links to the official page.
- **AI Assistant** (optional, needs [Ollama](https://ollama.com)): ask in plain English or Chinese, e.g. "Robotics
  for an 8 year old in San Jose". A local model searches the activity data with tools; the cards it shows come
  from the data, and its written summary is labelled as AI-generated.
- **Saved**: keep a list of activities. It is stored in the browser on each device.
- **Settings**: English, 简体中文 or 繁體中文; the child's age, preferred city and favorite categories as default
  filters; live status of the backend, data, AI and Ollama.
- Phone-first layout (bottom tab bar, large touch targets, safe areas, dark mode); tablets and desktops get a top
  navigation bar.

## How it works

```
iPhone Safari / Mac browser ──http──▶ frontend :3000 (React, the only port on the network)
                                         │ same-origin API proxy over the internal Docker network
                                         ▼
                                      backend :8000 (Flask; published on the Mac's 127.0.0.1 only)
                                         │ reads data/courses.json (read-only)
                                         │ AI Assistant only:
                                         ▼
                                      Ollama :11434 on the Mac (127.0.0.1 only), local model e.g. qwen2.5:1.5b
```

**AI agent.** For each question, the model chooses among four tools: `search_activities`, `filter_by_age`,
`filter_by_date` and `get_activity_details`. They reuse the app's own search and filters and only read the data. The
model sees the tool results and writes a short answer. The activity cards and links come from the tool results;
links in the model's text that are not in the data are removed; each answer shows which searches ran. There is no
RAG or vector database. Details: [docs/AI_AGENT_MVP.md](docs/AI_AGENT_MVP.md).

**Why Ollama.** It runs open models locally on the Mac (using the Apple Silicon GPU), so questions never leave
your computer, there are no API keys or usage costs, and nothing depends on an online AI service. The trade-off is that a small model that fits on an 8 GB Mac writes less reliable prose than large cloud
models; that is why the facts on the cards never come from the model's text.

## Install and run (Mac + iPhone)

```bash
git clone https://github.com/scmbuildrelease/AIAgentClassSelect.git && cd AIAgentClassSelect
cp .env.example .env                          # optional: ports, AI model, AI on/off
ollama pull qwen2.5:1.5b                      # optional: only for the AI Assistant (needs the Ollama app)
docker compose up --build -d                  # then open http://localhost:3000 on the Mac
ipconfig getifaddr en0                        # the Mac's LAN IP (en1 on some Macs); it can change
# iPhone Safari, same Wi-Fi:  http://<that IP>:3000
docker compose down                           # stop
```

Requirements: Docker Desktop for Mac (Apple Silicon or Intel). Ollama is needed only for the AI Assistant;
Discover, Saved and Settings work without it. **[docs/INSTALL_MAC.md](docs/INSTALL_MAC.md)** is the complete guide:
prerequisites, choosing a model by Mac memory, every `.env` setting, the iPhone and same-Wi-Fi requirements,
security, updating, uninstalling and troubleshooting.

**Network and privacy.** Only the frontend (port 3000) is reachable from the network; the backend
(`127.0.0.1:8000`) and Ollama (`127.0.0.1:11434`) are not. **There is no login:** anyone on the same Wi-Fi who can
reach port 3000 can use the app, and a Wi-Fi password is not a substitute for one. Set `FRONTEND_BIND=127.0.0.1`
to allow only the Mac itself. Saved activities and preferences stay in each device's browser. Don't port-forward
the app to the internet.

## Current limitations

- **Bay Area only.** The included data covers the San Francisco Bay Area. Other regions need new sources (see
  [Adding sources](#adding-sources-cities-categories-ages)) and a discovery run.
- **Data freshness** depends on when the discovery workflow was last run (Settings shows the last check date).
- **The AI summary can be wrong** (the tested `qwen2.5:1.5b` sometimes misses a filter, mistranslates names, or
  answers a Traditional Chinese question in Simplified Chinese). Trust the cards and official pages.
- **No accounts or sync.** Saved activities are per browser and device.
- **Development web server.** The frontend runs on the Create React App development server, which is no longer
  maintained; fine for a trusted home network, not for public hosting.
- **Testing so far:** one Apple Silicon Mac (macOS 15.7), with phone and tablet sizes checked in a desktop browser.
  A physical iPhone, a second Mac and Intel Macs have not been tested yet
  ([docs/PHASE5_IPHONE_TEST.md](docs/PHASE5_IPHONE_TEST.md)).

## Documentation

| Document | Contents |
|---|---|
| [docs/INSTALL_MAC.md](docs/INSTALL_MAC.md) | Installation, iPhone access, security, troubleshooting |
| [docs/AI_AGENT_MVP.md](docs/AI_AGENT_MVP.md) | AI agent design, tools, configuration, limitations |
| [docs/PHASE5_IPHONE_TEST.md](docs/PHASE5_IPHONE_TEST.md) | Manual acceptance checklist (iPhone, second Mac) |
| [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) | Step-by-step demo script (Mac browser, AI Assistant, iPhone) |
| [docs/AI_TECHNOLOGY_AUDIT.md](docs/AI_TECHNOLOGY_AUDIT.md) | Audit of the AI technology (snapshot) |

# Activity tracker

The tracker checks a curated list of **official** Bay Area provider pages (initial target: ages 7–8, South Bay
first), keeps a history in this repo, and shows what is **new / updated / unchanged / no longer listed** on each
run. It runs only when you click **Run workflow** in GitHub Actions. There is no schedule, no paid API and no
secrets.

## How to use it (GitHub)

1. Open the repo → **Actions** → **Activity Discovery** → **Run workflow**.
2. Optionally change the inputs:
   | Input | Default | Meaning |
   |---|---|---|
   | `min_age` / `max_age` | 7 / 8 | Report filter. Activities with no published age are still shown. |
   | `categories` | `all` | `all`, or comma-separated keys such as `stem,music,camps` |
   | `search_mode` | `refresh_known_sources` | `refresh_known_sources` re-checks configured sources; `discover_new_sources` only suggests new pages; `both` does both |
3. When the run finishes, open it. The report is on the run's **Summary** page. A copy is attached as the
   `activity-report-N` artifact.
4. If data changed, the workflow commits `data/*.json` back to the branch it ran on.

## What the report contains

- Run time and parameters, plus summary counts.
- 🆕 New, ✏️ Updated (field: old → new), 🏕️ camps and seasonal programs, ✅ unchanged (collapsed),
  ❔ not found this run.
- ⚠️ Sources that failed (HTTP error, robots.txt, or nothing extractable), plus sites to check manually.
- 🔎 Candidate pages found by discovery mode (suggestions only).

Every value comes from the linked official page. A field the page doesn't state shows as
**"Not published"**. Rows marked **†** are program-level records whose fields were found by text
patterns, so confirm them on the official page. Rows without † come from structured listings or schema.org data.
There are no ratings or recommendations.

## Status meanings

| Status | Meaning |
|---|---|
| `NEW` | First time seen (everything is NEW on the first, baseline run) |
| `UPDATED` | Name, ages, location, schedule, sessions, dates, price, enrollment or description changed |
| `UNCHANGED` | Re-checked and the same, after normalizing whitespace, case and dash styles and ignoring HTML changes |
| `NOT_FOUND` | The source page was read but no longer lists it. The record is kept. |
| `FETCH_FAILED` | Its source could not be fetched or yielded nothing. The previous data is kept and marked not verified. |

If **every** source fails, nothing is written and the run is marked failed, so history is never overwritten
with an empty result.

## Adding sources, cities, categories, ages

All of this is configuration. No code changes are needed.

- **`config/sources.json`**: add an entry with `id` (never change it later), `provider`, `url`,
  `categories`, `city`, and optionally `program_type`, `season`, `course_name`.
  - `"parser": "page"` (default) gives one program-level record per page.
  - `"parser": "listing"` gives one record per item, using CSS selectors (see the Club SciKidz entry).
  - `"manual_only": true` lists the site in the report for manual checking and never fetches it. Use it for
    sites that block bots or render with JavaScript.
  - Promising pages from discovery mode show up in `data/candidate_sources.json`. Copy one into
    `sources.json` to start tracking it.
- **`config/settings.json`**: categories (label, keywords), cities, default ages, request politeness
  (user agent, delay, retries).

## Chinese and English (中文 / English)

- **Originals are never changed.** `name` and `description` are stored as the source published them
  (whitespace runs collapsed only). `original_language` is `en`, `zh-Hans`, `zh-Hant`, `zh` or `mixed`.
- **`translations`** sit next to the original: `{"en": {"name": ..., "method": ...}}`, where `method` is:
  - `provider`: the provider's own page in the other language (a linked duplicate)
  - `manual`: written by a person in `config/sources.json` (`"translations"` on a source)
  - `machine`: always labelled "machine translation". **None are generated today.**
- **Extraction** handles English, Simplified and Traditional Chinese, and mixed text:
  - ages: 7-9岁 / 6至10歲 / 一至三年级
  - dates: 2027年6月14日至6月18日
  - times: 周一至周五 9:00-15:00, 每週六 上午9點到12點
  - prices: $450/周, 450美元, 学费：免费
  - enrollment: 报名中 / 名额已满 / 报名已截止
  - registration links: 立即报名 / Register
  - Chinese city names: 圣何塞 → San Jose
  - Full-width characters are handled. Single dates and unstated fields are never guessed.
- **Search** (`GET /courses?q=…&lang=en|zh`) uses the `glossary` in `config/settings.json`
  (机器人 = robotics, 编程 = coding, 数学 = math, 美术 = art, 夏令营 = summer camp, 中文学校 = Chinese school, …).
  It works across Simplified and Traditional script. Add terms there; no code changes needed.
- **Cross-language duplicates**: the same activity on a provider's Chinese and English pages is linked, not
  merged. Matching requires the same site plus the same registration link, or the same dates, ages and a shared
  glossary concept. It's shown once, with the other title as a `provider` translation.
- **Posters (OCR)** are optional. Set `"parser": "poster"` on a source whose URL is an image. This needs the
  system `tesseract` with Chinese data: `brew install tesseract tesseract-lang`, or
  `apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra`. Without it, the poster
  source is reported as not readable instead of being silently skipped.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python -m pytest -q                                   # offline tests (no network)

# offline demo with fixtures: baseline run, then a simulated second run
python -m activity_tracker --config-dir tests/fixtures/config --data-dir /tmp/demo \
    --fixtures tests/fixtures/site_v1 --report /tmp/demo/r1.md
python -m activity_tracker --config-dir tests/fixtures/config --data-dir /tmp/demo \
    --fixtures tests/fixtures/site_v2 --mode both --report /tmp/demo/r2.md

# real run (fetches the live sites; writes data/ and reports/report.md)
python -m activity_tracker --min-age 7 --max-age 8 --mode refresh_known_sources
```

## Viewer images (Docker)

The app's backend/frontend images are also published by `.github/workflows/docker-build.yml` as multi-platform
images for **linux/amd64 and linux/arm64** (Apple Silicon pulls arm64 automatically):

```bash
docker pull ghcr.io/<owner>/aiagentclassselect-backend:latest
docker pull ghcr.io/<owner>/aiagentclassselect-frontend:latest
docker buildx imagetools inspect ghcr.io/<owner>/aiagentclassselect-backend:latest   # lists both platforms
docker compose up --build                                                             # or build locally
```

## Layout

```
activity_tracker/   fetcher (robots.txt, delays, retries) · extract · tracker (IDs, diff, storage) · discovery · report · cli · agent (optional AI assistant)
config/             settings.json, sources.json  (edit these)
data/               sources.json, courses.json, candidate_sources.json  (written by runs; committed)
tests/              offline tests and HTML fixtures
backend/, frontend/ the personal app (Flask API + React UI) that reads data/courses.json
docs/               installation, AI agent, test checklist
```

## Politeness

Requests identify themselves honestly (`AIAgentClassSelect/1.0 (+repo URL)`), respect robots.txt, wait
2 seconds between requests to the same host, and retry only on timeouts and 429/5xx errors. Sites that
block automated access are reported as failures or listed for manual checking. The tool does not try to
work around them.

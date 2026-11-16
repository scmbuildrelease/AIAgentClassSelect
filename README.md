# AIAgentClassSelect — Kids Activity Discovery & Tracking

A personal tool that checks a curated list of **official** Bay Area provider pages for kids' classes,
camps and activities (initial target: ages 7–8, South Bay first), keeps a history in this repo, and
shows what is **new / updated / unchanged / no longer listed** on each run.

It runs only when you click **Run workflow** in GitHub Actions. There is no schedule, no paid API and no secrets.

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

The optional backend/frontend viewer is published by `.github/workflows/docker-build.yml` as multi-platform
images for **linux/amd64 and linux/arm64** (Apple Silicon pulls arm64 automatically):

```bash
docker pull ghcr.io/<owner>/aiagentclassselect-backend:latest
docker pull ghcr.io/<owner>/aiagentclassselect-frontend:latest
docker buildx imagetools inspect ghcr.io/<owner>/aiagentclassselect-backend:latest   # lists both platforms
docker compose up --build                                                             # or build locally
```

## Layout

```
activity_tracker/   fetcher (robots.txt, delays, retries) · extract · tracker (IDs, diff, storage) · discovery · report · cli
config/             settings.json, sources.json  (edit these)
data/               sources.json, courses.json, candidate_sources.json  (written by runs; committed)
tests/              offline tests and HTML fixtures
backend/, frontend/ optional small viewer that reads data/courses.json
```

## Politeness

Requests identify themselves honestly (`AIAgentClassSelect/1.0 (+repo URL)`), respect robots.txt, wait
2 seconds between requests to the same host, and retry only on timeouts and 429/5xx errors. Sites that
block automated access are reported as failures or listed for manual checking. The tool does not try to
work around them.

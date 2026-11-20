# AIAgentClassSelect v0.1.0 — Local Mac MVP Demo Guide

| | |
|---|---|
| Version | 0.1.0 (Local Mac MVP) |
| Runs on | One Mac with Docker Desktop; opened from Mac browsers and iPhone Safari on the same Wi-Fi |
| AI | Ollama on the Mac with `qwen2.5:1.5b` (no cloud AI, no API key) |
| Data | `data/courses.json`, San Francisco Bay Area kids' activities |

This guide lets another developer reproduce the demo from a fresh clone. The complete installation reference
is [INSTALL_MAC.md](INSTALL_MAC.md). The AI design is in [AI_AGENT_MVP.md](AI_AGENT_MVP.md), the limits are in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md), and the test evidence is in
[V0.1.0_READINESS_REPORT.md](V0.1.0_READINESS_REPORT.md).

v0.1.0 is local only. AWS hosting, user accounts, cloud AI and multi-tenancy are planned for v1.0.0 and are
not part of this demo.

## 1. What the demo shows

- **Discover**: search real activity records in English or Chinese and filter them by category, age, city and
  date.
- **Saved** and **Settings**: these are stored in each browser. Settings offers English, 简体中文 and 繁體中文.
- **AI Assistant**: a local model on the Mac picks among four Python tools. The backend checks the tool
  arguments and runs the tools over the real data. The app shows the model's summary, the activity cards from
  the tool results, and a trace of every tool call.
- **iPhone Safari**: opens the app the Mac serves over the same Wi-Fi. Nothing is installed on the iPhone.

## 2. Architecture

```text
Mac browser / iPhone Safari
        │ HTTP :3000  (the only port reachable from the Wi-Fi)
        ▼
frontend container: React (Create React App dev server)
        │ same-origin proxy of /courses /options /health /agent over Docker's internal network
        ▼
backend container: Flask :8000  (published on the Mac's 127.0.0.1 only)
        ├── reads ./data/courses.json (mounted read-only)
        └── AI agent loop (activity_tracker/agent.py)
                │ http://host.docker.internal:11434
                ▼
        Ollama app on the Mac (127.0.0.1:11434) running qwen2.5:1.5b
                │ tool calls, which the backend checks and runs in Python:
                └── search_activities · filter_by_age · filter_by_date · get_activity_details
```

## 3. Mac prerequisites

| Need | Check |
|---|---|
| macOS on Apple Silicon or Intel; 8 GB of memory is enough for `qwen2.5:1.5b` | `uname -m`; `sysctl -n hw.memsize` |
| git | `git --version` (accept the command-line tools prompt if macOS shows it) |
| Docker Desktop for Mac | `docker version --format '{{.Server.Version}}'`; `docker compose version` |
| Ollama (AI Assistant only) | `ollama --version`; `curl -s http://127.0.0.1:11434/api/version` |
| Internet | Only for the first downloads (repository, Docker base images, model) |

The recorded demo used an Apple M3 with 8 GB of memory, macOS 15.7.3, Docker Engine 28.0.4, Compose
v2.34.0-desktop.1 and Ollama 0.40.11. No other Mac has been tested.

### Docker Desktop setup

1. Download Docker Desktop from <https://www.docker.com/products/docker-desktop/>, choosing Apple Silicon or
   Intel to match `uname -m`.
2. Open Docker.app, accept the terms and wait for "Docker Desktop is running". Signing in is not required.
3. The default resources are enough, because the model runs in Ollama, outside Docker.

### Ollama installation

1. Download the macOS app from <https://ollama.com/download>, move it to Applications and open it. It stays
   in the menu bar.
2. Check that it is running: `curl -s http://127.0.0.1:11434/api/version` prints `{"version":"..."}`.
3. Keep Ollama on its default `127.0.0.1`. Do not set `OLLAMA_HOST=0.0.0.0`, and do not run Ollama inside
   Docker.

### Qwen model download

```bash
ollama pull qwen2.5:1.5b      # about 1 GB
ollama list                   # qwen2.5:1.5b must be listed
```

`qwen2.5:1.5b` is the only model tested with this app. Larger Qwen 2.5 models are untested; see
[INSTALL_MAC.md → Choose and download an AI model](INSTALL_MAC.md#choose-and-download-an-ai-model).

## 4. Clean installation and configuration

```bash
cd ~
git clone https://github.com/scmbuildrelease/AIAgentClassSelect.git
cd AIAgentClassSelect
cp .env.example .env          # optional: every setting has a default
```

These are the settings in `.env.example`:

| Setting | Default | Meaning |
|---|---|---|
| `FRONTEND_PORT` | `3000` | Port of the app in the browser |
| `FRONTEND_BIND` | empty | Empty: the Mac and devices on the Wi-Fi. `127.0.0.1`: this Mac only |
| `BACKEND_PORT` | `8000` | Backend port, always published on `127.0.0.1` only |
| `AI_ENABLED` | `true` | `false` turns the AI Assistant off |
| `AI_MODEL` | `qwen2.5:1.5b` | A tool-calling model you have pulled |
| `AI_BASE_URL` | `http://host.docker.internal:11434` | How the backend container reaches Ollama on the Mac |
| `AI_TIMEOUT` | `120` | Seconds per model reply (above 0, at most 3600) |
| `AI_MAX_ITERATIONS` | `5` | Model calls per question (1–20) |

`.env` is ignored by git. Settings exported in your shell take precedence over `.env`.

## 5. Docker Compose startup

```bash
docker compose up --build -d     # the first build takes a few minutes
docker compose ps                # backend 127.0.0.1:8000->8000/tcp, frontend 0.0.0.0:3000->3000/tcp
curl -s http://localhost:3000/health
```

`/health` should return JSON with `"backend":"ok"`, `"data":{"available":true,...}` and, when Ollama is
running, `"ollama":"ok"`. The frontend needs about 30 seconds to compile after each start; reload the page if it
isn't ready yet.

## 6. Mac browser demo

Open `http://localhost:3000`.

### 6.1 Settings → Status

All four rows show **Connected**: Backend, Activity data (with the activity count and last-checked date), AI
Assistant (with the model name) and Ollama (local model).

### 6.2 Discover

Counts are from the recorded test against the data checked on 2026-11-16. They will change when the data is
updated.

| Step | Recorded result |
|---|---|
| Open Discover | 589 activities |
| Search `robotics` | 14 activities |
| Search `机器人` | 14 activities (the same set) |
| Clear the search box | 589 activities |
| Tap the **STEM** chip | 17 activities |
| Filters → Age 8, City San Jose | 9 activities |
| Filters → From 2031-01-01 | "No matching activities." |
| Tap **Official page ↗** on a card | The provider's page opens in a new tab |

### 6.3 Saved

1. Tap **Save** on two cards. The tab shows **Saved (2)**.
2. Reload the page. Both are still listed.
3. Remove one with its ★ button. One remains.

Saved activities live in the browser's local storage until removed or until the site data is cleared.

## 7. AI Agent demonstration

Open **AI Assistant** and ask the prompts below **exactly as written**. Under each answer, open **Searches
the assistant ran** to show the actual tool calls.

**Recorded results are history, not guarantees.** The counts below come from live runs with `qwen2.5:1.5b`
and the data last checked on 2026-11-16 (see the [readiness report](V0.1.0_READINESS_REPORT.md)). A small
local model can choose different tools on another day or another Mac, and the counts change when the data is
updated. Judge a run by its trace and cards, not only by the numbers.

### Prompt 1: natural-language tool selection

`STEM classes for age 8`

This shows whether the model works out by itself that it needs the age filter. **It is not reliable:**

| When | Tool calls | Cards |
|---|---|---|
| 2026-11-18 (live API, and the UI in headless Chrome) | `search_activities` {category: stem} → 17, then `filter_by_age` {age: 8} → 13 | 13; all were checked against `data/courses.json` and include age 8 |
| 2026-11-19 (live API, 8 of 8 runs) | `search_activities` {category: stem} → 17 only; **`filter_by_age` was not called** | 17, including activities outside age 8 |
| Date pinned to 2026-11-18 (test container) | search → 17, then age filter → 13 | 13 |
| Date pinned to 2026-11-19, 11-20, 11-21, 11-23, 11-25, 12-01 or 12-15 (test containers) | `search_activities` → 17 only | 17 |

The behavior changed when the system date changed: the agent's system prompt contains today's date, and that
alone changed this small model's tool choice. If the trace shows only "Keyword search → 17", the model skipped
the age filter. That is the known limitation, not a crash.

### Prompt 1b: age filter, reliable wording

`Find STEM classes, then filter them by age 8`

| When | Tool calls | Cards |
|---|---|---|
| 2026-11-19 (live API, 4 runs) | `search_activities` {category: stem} → 17, then `filter_by_age` {age: 8} → 13 | 13 |
| Date pinned to each date from 2026-11-18 to 2026-12-15 above (test containers) | search → 17, then age filter → 13 | 13 |

In the 2026-11-19 live run, all 13 cards were checked against `data/courses.json`: the same ID, name and link,
and a published age range that includes 8. This wording behaved consistently in every recorded run; that is
still not a guarantee for every future run.

### Prompts 2 and 3: date filter and activity details

| # | Prompt | Tool calls in the recorded runs | Recorded result |
|---|---|---|---|
| 2 | `What activities happen between 2027-06-01 and 2027-06-30?` | `filter_by_date` {start_date: 2027-06-01, end_date: 2027-06-30} | 9 activities, all with dates that overlap June 2027 (checked against the data) |
| 3 | `Get details for activity id clubscikidz-ages-7-9-3c3f893a3e` | `get_activity_details` {activity_id: …} | 1 card: Junior Robot Engineer (Club SciKidz Silicon Valley, ages 7–9) |

Both gave the same tool calls and counts in every live run (2026-11-18 and 2026-11-19) and with the date
pinned to each date tested up to 2026-12-15. `get_activity_details` needs the activity ID in the question.

### Reading the answer

Each answer shows three parts:

1. An **AI-generated summary**, labelled with the model name. The model writes this text.
2. **Activities found by the assistant's searches**: cards built from the tool results, not from the model's
   text.
3. **Searches the assistant ran**: each tool call with its arguments and result count. A call the backend
   rejected appears in red with the reason.

The same question on the same day gave the same tool calls in every repeat. A different date, a different
wording or a different model can change them. If the model repeats calls, the trace shows "Skipped calls …
(limit 4)"; that is the per-step limit working. Always compare the cards with Discover and the official pages.

Don't use prompts such as "Find activities in June" or "Robotics for a 10 year old" in a demo. The model can
skip the date or age filter and return activities that don't match. Prompt 1 is included on purpose, to show
this. See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

Optional extra prompts that behaved correctly in the recorded runs:
- `Find underwater basket weaving in Gilroy`: the answer says no activities match.
- `圣何塞适合8岁孩子的机器人课`: 3 robotics cards and a Simplified Chinese answer (recorded 2026-11-18). The
  age filter was not used; the cards fit age 8 because those robotics activities happen to cover it.

### The four tools

All four tools only read the data. The backend checks every argument before running a tool: types, ages 0–18,
known categories, `YYYY-MM-DD` dates, the end date not before the start date, and required arguments.

| Tool | Arguments | What it does |
|---|---|---|
| `search_activities` | `keyword`, `category`, `location`; all optional | Keyword search in English or Chinese (the same search as Discover), optionally limited to one category key and a city |
| `filter_by_age` | `age` (required, integer) | Keeps the activities from the latest search whose published ages include the child's age. Activities without published ages are counted and left out |
| `filter_by_date` | `start_date` (required), `end_date` | Keeps activities whose published dates overlap the range. It filters the latest search, or the whole catalog when nothing has been searched yet |
| `get_activity_details` | `activity_id` (required) | Returns every known field of one activity and its official link; an unknown ID is an error |

The model sees at most 8 activities per tool result. It may make at most 4 tool calls per step and
`AI_MAX_ITERATIONS` model calls per question. Links in the model's text that are not in the data are removed.

### AI unavailable (optional)

1. Quit the Ollama app (menu bar → Quit Ollama).
2. Ask a question. The app shows "Local AI model unavailable: no Ollama server is reachable at …" with no
   answer and no cards.
3. **Settings → Status → Refresh**: Ollama shows **Unavailable** with the reason.
4. Reopen Ollama, press Refresh and ask again.

In the recorded test (run in temporary backend containers), these cases also returned HTTP 503 with a clear
message and no answer:
- a missing model, with the exact `ollama pull <model>` command;
- a timeout;
- an invalid `AI_TIMEOUT` or `AI_MAX_ITERATIONS`;
- `AI_ENABLED=false`.

## 8. iPhone Safari demo

1. Find the Mac's LAN address and check it:

   ```bash
   ipconfig getifaddr en0                       # use en1 if this prints nothing
   curl -s "http://$(ipconfig getifaddr en0):3000/health"
   ```

   The second command must print the same JSON as in step 5. If macOS asks whether Docker may accept incoming
   connections, choose **Allow**.
2. On the iPhone, join the **same Wi-Fi** (not a guest network) and turn off any VPN.
3. In Safari, open `http://<Mac IP>:3000`, for example `http://192.168.1.23:3000`. Use the numeric IP, not
   `<name>.local`, which gets "Invalid Host header".
4. Repeat the Discover, Saved and AI steps above. Then change the language in Settings.
5. Optional: Share → Add to Home Screen.

The iPhone needs no app and no Ollama, because the AI runs on the Mac. Saved activities on the iPhone are
separate from the Mac's. The full device checklist is [PHASE5_IPHONE_TEST.md](PHASE5_IPHONE_TEST.md). **A
physical iPhone has not been tested yet**; its layout was checked only in headless Chrome at iPhone sizes.

## 9. Network security

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(3000|8000|11434) '
```

Expected (Docker's ports appear under the `com.docker` process):

```text
com.docke ... TCP 127.0.0.1:8000 (LISTEN)
com.docke ... TCP *:3000 (LISTEN)
ollama    ... TCP 127.0.0.1:11434 (LISTEN)
```

From the Mac's LAN address, port 3000 answers; ports 8000 and 11434 refuse the connection:

```bash
IP=$(ipconfig getifaddr en0)
for p in 3000 8000 11434; do curl -s -m 3 -o /dev/null -w "$p %{http_code}\n" "http://$IP:$p/" || echo "$p refused"; done
```

- There is **no login**. Anyone on the Wi-Fi who can reach port 3000 can use the app, including the AI on your
  Mac. A Wi-Fi password is not an app login. Use the app only on a trusted network, and set
  `FRONTEND_BIND=127.0.0.1` to allow only the Mac itself.
- Traffic is plain HTTP on the local network.
- Do not port-forward the app on your router, and do not expose it to the internet.
- The API sends no CORS headers, and the dev server rejects foreign `Host` headers.

## 10. Test commands

```bash
# Python tests (offline; the 2 live Ollama tests run only when Ollama is reachable)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# Frontend tests and production build, inside the frontend image
docker run --rm -v "$PWD/frontend/src:/app/src:ro" -v "$PWD/frontend/public:/app/public:ro" \
  -v "$PWD/frontend/package.json:/app/package.json:ro" -e CI=true aiagentclassselect-frontend:latest \
  sh -c 'npm test -- --watchAll=false && npx react-scripts build'

# Compose file check
docker compose config --quiet
```

Recorded results: pytest 272 passed and 1 skipped (OCR); Jest 16/16. GitHub Actions runs the same pytest suite
and, from v0.1.0, the Jest tests (`.github/workflows/tests.yml`).

## 11. Restart, shutdown and cleanup

```bash
docker compose down              # stop
docker compose up -d             # start again (wait ~30 s, then reload Mac and iPhone)
docker compose logs --tail=100 frontend backend
```

Saved activities and preferences are in each browser, so restarting doesn't affect them. Ollama keeps running
on its own; quit it from the menu bar if you want to stop it.

To remove the app completely:

```bash
docker compose down --rmi local      # this app's containers, network and images
cd .. && rm -rf AIAgentClassSelect   # code, data and .env
ollama rm qwen2.5:1.5b               # optional: the model
```

## 12. Troubleshooting

| Problem | Resolution |
|---|---|
| `Cannot connect to the Docker daemon` | Open Docker Desktop and wait until it is running |
| Page doesn't load right after start | The frontend compiles for ~30 s; reload |
| Backend or data unavailable in Settings | `docker compose ps`; `docker compose logs backend` |
| iPhone can't connect | Same Wi-Fi (not guest)? VPN off? The `curl …:3000/health` check from step 8 works on the Mac? Firewall: System Settings → Network → Firewall → Options → allow Docker |
| "Invalid Host header" | Use the numeric IP, not `.local` |
| "no Ollama server is reachable" | Start the Ollama app; `curl -s http://127.0.0.1:11434/api/version` |
| "model … is not installed" | Run the `ollama pull …` command from the message, or set `AI_MODEL` to a model in `ollama list` |
| "did not answer within … seconds" | Try again (the first question loads the model); raise `AI_TIMEOUT` in `.env`, then `docker compose up -d` |
| "Invalid AI configuration" | Fix `AI_TIMEOUT` (above 0, at most 3600) or `AI_MAX_ITERATIONS` (1–20) in `.env`, then `docker compose up -d` |
| AI answer doesn't match the question | A known model limitation; use the verified prompts and check the cards ([KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)) |
| `port is already allocated` | Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env` |
| iPhone can't open `:8000` | Expected: the backend is not on the network |

More in [INSTALL_MAC.md → Troubleshooting](INSTALL_MAC.md#6-troubleshooting).

## 13. Demo acceptance checklist

Only tick a box after doing the step yourself.

- [ ] Docker Desktop and Ollama are running; `ollama list` shows `qwen2.5:1.5b`
- [ ] `docker compose ps`: backend on `127.0.0.1:8000`, frontend on `3000`
- [ ] Settings → Status: all four rows Connected
- [ ] Discover: `robotics`, `机器人`, STEM chip, age and city filters work
- [ ] Saved: survives a reload
- [ ] AI prompt 1 (`STEM classes for age 8`): record which tools the trace shows and how many cards appear (13 with the age filter, 17 without)
- [ ] AI prompt 1b: trace shows `search_activities` and then `filter_by_age`; 13 cards, all fitting age 8
- [ ] AI prompt 2: trace shows `filter_by_date`; the cards are in June 2027
- [ ] AI prompt 3: trace shows `get_activity_details`; one card, Junior Robot Engineer
- [ ] With Ollama stopped, the app reports the AI as unavailable and shows no answer
- [ ] iPhone Safari opens `http://<Mac IP>:3000`; Discover and AI work; `:8000` does not load
- [ ] `docker compose down` and `up -d`: the app works again
- [ ] No cloud AI key or account was needed

Record: date, Mac model, chip and memory, macOS, Docker, Ollama, model, and iPhone model and iOS version.

## 14. Roadmap

- **v0.1.0 — Local Mac MVP (this release):** Mac + Docker + React + Flask + Ollama + Qwen + iPhone Safari on the
  same Wi-Fi.
- **v1.0.0 — AWS SaaS (planned):** cloud deployment, user accounts, multi-user data, cloud AI services,
  security hardening, monitoring and production infrastructure. None of this is in v0.1.0.

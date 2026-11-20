# AIAgentClassSelect v0.1.0 — release notes (DRAFT, not published)

> This is a draft for review. No `v0.1.0` tag or GitHub release has been created.

**v0.1.0 is a local Mac MVP.** It finds kids' classes, camps and activities in the **San Francisco Bay Area**.
Run it on one Mac with Docker Compose and open it from Mac browsers or from iPhone Safari on the same Wi-Fi. The
AI Assistant runs on the Mac with Ollama and Qwen 2.5. You need no cloud AI, API key, account or App Store app.

AWS SaaS (cloud hosting, user accounts, multi-user data, cloud AI services) is planned for **v1.0.0** and is not
part of this release.

## Highlights

- **Discover**: search in English or Chinese (`robotics` / `机器人`) with category, age, city and date filters
  over the tracked activity data. Every card links to the official page and shows "Not published" instead of
  guessing.
- **Local AI agent**: Ollama with `qwen2.5:1.5b` chooses among four read-only Python tools: `search_activities`,
  `filter_by_age`, `filter_by_date` and `get_activity_details`.
  - The backend checks every tool argument.
  - The activity cards come from the tool results.
  - Links not in the data are removed from the summary.
  - Each answer shows the tool calls that ran.
  - Clear errors when Ollama isn't running, the model isn't installed, a reply times out or the AI settings
    are invalid. The app never shows a made-up answer.
- **Saved** and **Settings** (English, 简体中文, 繁體中文; default age, city and favorite categories), stored in
  each browser.
- **Mobile-first UI** for iPhone Safari: safe areas, 44 px touch targets, no zoom on input, dark mode and WCAG AA
  text contrast. Desktop layout from 768 px.
- **Local network boundary**: only the frontend (port 3000) is reachable from the Wi-Fi. The backend
  (`127.0.0.1:8000`) and Ollama (`127.0.0.1:11434`) are not. The API sends no CORS headers, and the data is
  mounted read-only. `FRONTEND_BIND=127.0.0.1` limits the app to the Mac itself.
- **Reproducible demo**: `.env.example`, [INSTALL_MAC.md](INSTALL_MAC.md) and [DEMO_GUIDE.md](DEMO_GUIDE.md),
  with AI prompts verified live.
- **CI**: GitHub Actions runs the Python tests and the frontend Jest tests.

## Requirements

- macOS with Docker Desktop. It was tested only on Apple Silicon (M3, 8 GB, macOS 15.7.3).
- For the AI Assistant: the Ollama app and `ollama pull qwen2.5:1.5b` (about 1 GB).

## Verified

See [V0.1.0_READINESS_REPORT.md](V0.1.0_READINESS_REPORT.md) for the evidence:
- the Mac environment, ports and LAN boundary;
- Discover, Saved and Settings in the real UI;
- live AI runs that used all four tools;
- the AI failure handling;
- the test suites.

## Known limitations

The full list with observed examples is in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md). In short:

- `qwen2.5:1.5b` may choose the wrong tool or skip age and date filters in plain-language questions. Its summary
  can then describe real activities that don't match the question. Check the cards and official pages.
- `get_activity_details` is reliable only when the question gives the activity ID.
- Traditional Chinese questions get Simplified Chinese answers.
- No login and no rate limit: anyone on the same Wi-Fi can use the app. Plain HTTP. The frontend runs on the
  Create React App dev server, for trusted home networks only.
- Bay Area data only. Saved activities are per browser.
- **Not yet tested:** a physical iPhone, a second Mac, Intel Macs and other models.

## Upgrading from an earlier checkout

```bash
git pull
cp -n .env.example .env     # optional; keeps an existing .env
docker compose up --build -d
```

The backend is now published on `127.0.0.1` only. If you used `http://<Mac IP>:8000` from another device, use
the app on port 3000 instead.

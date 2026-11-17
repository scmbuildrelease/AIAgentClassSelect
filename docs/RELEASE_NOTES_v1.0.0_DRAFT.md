# AIAgentClassSelect v1.0.0 — release notes (DRAFT, not published)

> Draft for review. No tag or GitHub release has been created.

AIAgentClassSelect is a personal, self-hosted app for finding kids' classes, camps and activities in the
**San Francisco Bay Area**. Run it on your Mac with Docker and open it from your iPhone on the same Wi-Fi.
An optional AI assistant runs entirely on your Mac with Ollama. No accounts, cloud services, API keys or App Store.

## Highlights

- **Discover**: bilingual keyword search (English / 中文) with category, age, city and date filters over the
  tracked activity data; every card links to the official page and shows "Not published" instead of guessing.
- **AI Assistant** (optional): ask questions in English or Chinese; a local model (default `qwen2.5:1.5b` via
  Ollama) searches the data with four read-only tools. Activity cards come from the data; the model's summary is
  labelled AI-generated, and links not found in the data are removed. Clear messages when Ollama is not running,
  the model is not installed, a reply times out, or the AI settings are invalid.
- **Saved** activities and **Settings** (English, 简体中文, 繁體中文; default age, city and favorite categories),
  stored in each device's browser.
- **Mobile-first UI** for iPhone Safari (safe areas, 44 px touch targets, no input zoom, dark mode, WCAG AA text
  contrast), with a desktop layout from 768 px.
- **Private by default on the network**: only the frontend (port 3000) is reachable from the LAN; the backend and
  Ollama listen on the Mac's loopback only; no CORS headers on the API; the data is mounted read-only.
  `FRONTEND_BIND=127.0.0.1` limits the app to the Mac itself.
- **Independent installs**: `.env.example` for ports and AI settings, no Docker volumes or database, per-clone
  images; step-by-step guide in `docs/INSTALL_MAC.md` (Docker Desktop, Ollama, model choice by Mac memory, iPhone
  access, firewall, update, uninstall).

## Requirements

- macOS with Docker Desktop (Apple Silicon or Intel).
- Optional for the AI Assistant: Ollama and a tool-calling model (`ollama pull qwen2.5:1.5b`, about 1 GB).

## Known limitations

- Activity data covers the San Francisco Bay Area only and is as fresh as the last discovery run.
- No login: anyone on the same Wi-Fi who can reach port 3000 can use the app. A Wi-Fi password is not an app login.
- The frontend runs on the Create React App development server (unmaintained; `npm audit` reports issues in its
  build and dev-server dependencies). Suitable for a trusted home network, not for public hosting.
- The small default model's summaries can be imprecise: it may miss a filter, mistranslate names, or answer a
  Traditional Chinese question in Simplified Chinese. Cards and official pages are authoritative.
- Saved activities are per browser and device; there is no sync.
- Tested on one Apple Silicon Mac (macOS 15.7) with headless-browser checks at iPhone, iPad and desktop sizes.
  Physical-iPhone and second-Mac acceptance: see `docs/PHASE5_IPHONE_TEST.md` (fill in before publishing).
  Intel Macs and other models are untested.

## Upgrading from a pre-1.0 checkout

```bash
git pull
cp -n .env.example .env     # optional; keeps an existing .env
docker compose up --build -d
```

The backend is now published on `127.0.0.1` only. If you previously called `http://<Mac IP>:8000` from another
device, use the app on port 3000 instead.

# Phase 5 acceptance checklist: physical iPhone and second Mac

Use this to check the app on a real iPhone (and, if available, a second Mac). Mark each line ✅ / ❌ and note the
iPhone model, iOS version and anything odd. Nothing in the "Physical iPhone" and "Second Mac" sections has been
tested yet.

This checklist is the physical-device acceptance step for **v0.1.0 (Local Mac MVP)**; see
[V0.1.0_READINESS_REPORT.md](V0.1.0_READINESS_REPORT.md).

## What was already tested, and where

| Kind | What | Status |
|---|---|---|
| Automated (offline) | Python tests (API filters and errors, `/health`, AI agent with a scripted Ollama: tools, limits, timeouts, malformed replies, invalid settings) and frontend Jest tests (all four tabs, saving, language, errors) | Run in Phase 5; see the Phase 5 report |
| On the Mac | Headless Chrome at 430×932, 390×844, 768×1024 and 1440×900, light and dark mode, loaded through the Mac's LAN address: no sideways scrolling, touch targets ≥ 44 px, inputs at 17 px (no iOS zoom), nothing hidden behind the tab bar, text contrast ≥ 4.5:1 | Passed in Phase 5 |
| On the Mac | Real AI questions (English, Simplified and Traditional Chinese) through the frontend with the local `qwen2.5:1.5b`; ports 8000 and 11434 refused on the LAN address; `FRONTEND_BIND=127.0.0.1` | Passed in Phase 5 (Traditional Chinese answers came back in Simplified Chinese; known limitation) |
| On the Mac | Clean copy of the repository built without caches in an empty environment (Phase 4) | Passed |
| **Physical iPhone** | Everything in sections 2–7 below | **Not tested** |
| **Second Mac** | Section 8 below | **Not tested** |

Headless Chrome is not Safari: it does not show the iOS keyboard, the Safari toolbar, the notch or the home
indicator, and it does not apply iOS font and date-picker behavior. Those are what this checklist is for.

## 1. Set up (on the Mac)

```bash
cd ~/AIAgentClassSelect            # your clone
docker compose up --build -d
docker compose ps                  # backend 127.0.0.1:8000->8000/tcp, frontend 0.0.0.0:3000->3000/tcp
ipconfig getifaddr en0             # the Mac's LAN IP, e.g. 192.168.1.23 (try en1 if empty)
curl -s "http://$(ipconfig getifaddr en0):3000/health"   # must print JSON
ollama list                        # for the AI tests: the model in AI_MODEL (default qwen2.5:1.5b) is listed
```

On the iPhone: **Settings → Wi-Fi** → the same network as the Mac (not a guest network); turn off any VPN.

## 2. Connect (iPhone Safari)

- [ ] Open `http://<Mac LAN IP>:3000` (type `http://` and `:3000`). The page loads within ~30 s of starting Docker.
- [ ] The title "Kids Activities" is fully visible below the status bar / Dynamic Island (not under it).
- [ ] The bottom tab bar (Discover, AI Assistant, Saved, Settings) sits above the home indicator, not under it.
- [ ] Rotate to landscape and back: nothing is cut off at the sides; no sideways scrolling.
- [ ] From the iPhone, `http://<Mac LAN IP>:8000/health` does **not** load (backend not on the network).
- [ ] Optional: Share → Add to Home Screen; open it from the icon; it loads the app.

## 3. Discover

- [ ] The list shows "N activities" and cards; scrolling is smooth; the last card can be scrolled fully above the tab bar.
- [ ] Tap the search box: the page does **not** zoom in. The keyboard shows a "Search" key.
- [ ] Search `robotics` → Search: results mention robotics. Search `机器人`: robotics results too.
- [ ] Clear the search box: the full list returns.
- [ ] Tap a category chip (e.g. STEM): the list narrows; the chip row scrolls sideways with a swipe.
- [ ] Open **Filters**: choose an age (e.g. 8), a city (e.g. San Jose); dates via the iOS date picker; the list
      updates after each change. "Clear filters" resets them.
- [ ] A combination with no results (e.g. a far-away date range) shows "No matching activities."
- [ ] Tap **Official page ↗** on a card: the provider's site opens in a new tab; return to the app tab.
- [ ] "Show more" at the end of a long list loads more cards.

## 4. AI Assistant (needs Ollama on the Mac)

- [ ] Tap the input: no zoom; the keyboard shows "Send"; the input stays visible above the keyboard.
- [ ] Ask `Robotics for an 8 year old in San Jose`: within ~30 s an answer labelled "AI-generated summary"
      appears, followed by activity cards and "Searches the assistant ran".
- [ ] The cards' names and links match activities you can also find in Discover.
- [ ] Ask in Chinese, e.g. `圣何塞适合8岁孩子的机器人课`: answer and cards appear.
- [ ] Ask something with no matches, e.g. `Underwater basket weaving in Gilroy`: the answer says nothing was found.
- [ ] Save an activity from an AI card; it appears in Saved.
- [ ] Quit the Ollama app on the Mac, ask again: a clear "Local AI model unavailable … no Ollama server is reachable"
      error, no made-up answer. Reopen Ollama afterwards.
- [ ] "Clear conversation" empties the chat.

## 5. Saved

- [ ] Save 2 activities in Discover: the tab shows "Saved (2)" and both cards are listed.
- [ ] Remove one with its ★ button: it disappears.
- [ ] Pull to refresh / reload the page: the saved activity is still there.
- [ ] Close Safari completely (swipe it away) and reopen the URL: still there.
- [ ] On the Mac's browser, Saved is separate (expected: saved lists are per device).

## 6. Settings

- [ ] Language → 简体中文, then 繁體中文, then English: all labels change; the choice survives a reload.
- [ ] Child's age 8 and Preferred city San Jose: Discover's filters start with them.
- [ ] Favorite categories: chosen chips appear first on Discover.
- [ ] Status shows Backend, Activity data (with a date), AI Assistant and Ollama as Connected (Ollama running).
- [ ] Quit Ollama on the Mac → Refresh: Ollama shows Unavailable with a reason. Reopen Ollama → Refresh: Connected.
- [ ] Clear saved activities → a confirmation appears; Cancel keeps them; OK removes them.
- [ ] Dark mode (iPhone Settings → Display & Brightness → Dark): all text is readable on every tab.

## 7. Refresh and reconnect

- [ ] Lock the iPhone for a minute, unlock: the app still works (search again).
- [ ] On the Mac: `docker compose down`; on the iPhone a search shows an error (or the page won't load).
      `docker compose up -d`, wait ~30 s, reload: it works again; Saved is unchanged.
- [ ] Turn the iPhone's Wi-Fi off (cellular only): the app does not load (expected, local network only). Back on Wi-Fi: it loads.
- [ ] If the Mac's IP changed (e.g. after a restart), `ipconfig getifaddr en0` shows the new address to use.

## 8. Second Mac (independent installation)

Follow [INSTALL_MAC.md](INSTALL_MAC.md) on another Mac, ideally one that never had this project.

- [ ] Note: chip (`uname -m`), memory, macOS version, Docker Desktop version, Ollama version and model.
- [ ] `git clone`, `cp .env.example .env`, `docker compose up --build -d` succeed with no other setup.
- [ ] macOS asks whether Docker may accept incoming connections → Allow (then the iPhone can connect).
- [ ] Settings → Status on that Mac shows its own data and Ollama status.
- [ ] Its own iPhone opens `http://<that Mac's IP>:3000`; saved activities are separate from the first Mac's.
- [ ] Without Ollama installed: Discover, Saved and Settings work; the AI Assistant explains that the model is unavailable.
- [ ] `docker compose down --rmi local` removes it cleanly.

## Troubleshooting

| Symptom | Check |
|---|---|
| Safari can't connect | Same Wi-Fi (not guest)? VPN off? `curl -s http://$(ipconfig getifaddr en0):3000/health` on the Mac prints JSON? Firewall: System Settings → Network → Firewall → Options → Docker "Allow incoming connections" |
| "Invalid Host header" | Use the numeric IP, not the Mac's name |
| Page loads, data errors | `docker compose ps`, `docker compose logs backend` |
| AI unavailable | Ollama app running? `ollama list` shows the model in `AI_MODEL`? Settings → Status → Refresh |
| Very slow AI answers | First question loads the model (slower); larger models and Intel Macs are slower; raise `AI_TIMEOUT` |

More in [INSTALL_MAC.md → Troubleshooting](INSTALL_MAC.md#6-troubleshooting).

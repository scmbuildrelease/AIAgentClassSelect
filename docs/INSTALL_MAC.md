# Install and run on a Mac (v0.1.0 — Local Mac MVP)

The app runs on one Mac with Docker. You open it in a browser on that Mac, or on an iPhone (or any other phone,
tablet or computer) connected to the same Wi-Fi network. Nothing is put on the internet: there is no cloud server,
account, paid service, API key, Apple Developer account or App Store app. Each Mac that follows this guide runs its
own independent copy.

| Where | Address |
|---|---|
| On the Mac | `http://localhost:3000` |
| iPhone / other device on the same Wi-Fi | `http://<Mac LAN IP>:3000`, e.g. `http://192.168.1.23:3000` |

**About the activity data:** the repository includes activities collected for the **San Francisco Bay Area**
(`data/courses.json`, updated when the maintainer runs the discovery workflow; it is not on a schedule). Every
installation shows that same data; `git pull` gets the latest.
Tracking activities in another region means adding your own sources and running discovery yourself (see
"Adding sources, cities, categories, ages" in the [README](../README.md)); that is not covered by this guide.

**What has been tested:** one Apple Silicon Mac (M3, 8 GB, macOS 15.7, Docker Desktop with Engine 28.0.4,
Ollama 0.40.11, model `qwen2.5:1.5b`), including a clean copy of the repository built without caches in an empty
environment. Not yet tested: a physical iPhone, a second Mac, an Intel Mac, other macOS versions, and other models.
If you try one of these, the checklist in [PHASE5_IPHONE_TEST.md](PHASE5_IPHONE_TEST.md) helps.

## What needs Ollama

| Feature | Without Ollama | Needs Ollama + a model |
|---|---|---|
| Discover: search (English/Chinese), categories, age/city/date filters, activity cards, official links | ✓ | |
| Saved activities (stored in each browser) | ✓ | |
| Settings: language, child's age, preferred city, favorite categories, status | ✓ | |
| **AI Assistant** tab: questions in plain English or Chinese, answered by a local model that searches the activities | | ✓ |

Without Ollama, the AI Assistant tab shows why it is unavailable and Settings → Status shows Ollama as unavailable;
everything else works.

## 1. Prerequisites (once)

Check your Mac first:

```bash
uname -m                                                     # arm64 = Apple Silicon (M1–M4), x86_64 = Intel
sysctl -n hw.memsize | awk '{print $1/1073741824 " GB"}'     # memory, used to pick the AI model below
```

1. **git** (to download the repository): run `git --version`. If macOS offers to install the command line
   developer tools, accept (or run `xcode-select --install`).
2. **Docker Desktop for Mac** (free for personal use): download it from
   <https://www.docker.com/products/docker-desktop/>, choosing **Apple Silicon** or **Intel** to match `uname -m`.
   Open Docker.app, accept its terms, and wait until it shows "Docker Desktop is running". You don't need to sign
   in. Check:

   ```bash
   docker version --format '{{.Server.Version}}'     # prints a version, not "Cannot connect to the Docker daemon"
   docker compose version
   ```

   The default Docker Desktop resources are enough; the AI model runs in Ollama, outside Docker.
3. **Ollama** (optional, only for the AI Assistant): download the macOS app from <https://ollama.com/download>,
   move it to Applications and open it (it keeps running in the menu bar and starts at login). Check:

   ```bash
   ollama --version
   curl -s http://127.0.0.1:11434/api/version        # {"version":"..."} while the Ollama app is running
   ```

   Ollama runs natively on the Mac so it can use the Apple Silicon GPU. Don't run it inside Docker, and don't
   change it to listen on the network (`OLLAMA_HOST=0.0.0.0`); see [Network security](#5-network-security).

### Choose and download an AI model

The assistant needs a model that supports **tool calling**. The Qwen 2.5 family does. Pick by memory. The model
shares memory with macOS, Docker and your other apps, so leave several GB free:

| Mac memory | Model (`AI_MODEL`) | Download | Notes |
|---|---|---|---|
| 8 GB | `qwen2.5:1.5b` (default) | ≈1 GB | **The only model tested with this app.** Answers in seconds; it sometimes misses a filter (e.g. age), so check the activity cards. |
| 16 GB | `qwen2.5:3b` or `qwen2.5:7b` | ≈1.9 GB / ≈4.7 GB | Untested here; larger models usually follow instructions better but answer more slowly. |
| 32 GB or more | `qwen2.5:7b` or `qwen2.5:14b` | ≈4.7 GB / ≈9 GB | Untested here. |

Intel Macs run models on the CPU: use `qwen2.5:1.5b` and set `AI_TIMEOUT=300` (step 2).

```bash
ollama pull qwen2.5:1.5b      # or the model you chose
ollama list                   # the model must be listed
```

Activity facts on the cards (dates, ages, prices, links) always come from the data, whichever model you use. The
model only writes the summary text, which can be imprecise.

## 2. Install, configure and start

```bash
cd ~                                     # or any folder you like
git clone https://github.com/scmbuildrelease/AIAgentClassSelect.git
cd AIAgentClassSelect
cp .env.example .env                     # optional: only needed to change the defaults
```

**Configuration (`.env`, optional).** Every setting has a default, so you can skip this. Otherwise edit `.env`
(e.g. `open -e .env`); each setting is explained in [`.env.example`](../.env.example):

| Setting | Default | Change it when |
|---|---|---|
| `AI_MODEL` | `qwen2.5:1.5b` | you pulled a different model |
| `AI_ENABLED` | `true` | `false` turns the AI Assistant off (no Ollama needed) |
| `AI_TIMEOUT` | `120` | larger models or Intel Macs (e.g. `300`) |
| `AI_MAX_ITERATIONS` | `5` | rarely |
| `AI_BASE_URL` | `http://host.docker.internal:11434` | Ollama listens on a non-default port |
| `FRONTEND_PORT` | `3000` | port 3000 is already used on your Mac |
| `FRONTEND_BIND` | empty (all interfaces) | `127.0.0.1`: only this Mac can open the app |
| `BACKEND_PORT` | `8000` | port 8000 is already used (the backend is always on `127.0.0.1` only) |

`.env` is ignored by git, so `git pull` never overwrites it. Variables exported in your shell take precedence
over `.env`; `env | grep -E '^(AI_|FRONTEND_|BACKEND_)'` shows any.

**Start:**

```bash
docker compose up --build -d      # first start downloads base images and builds (a few minutes)
docker compose ps                 # backend and frontend should be "running"/"Up"
```

Open `http://localhost:3000` on the Mac (or your `FRONTEND_PORT`). The frontend takes about 30 seconds to compile
after each start; reload if the page is not ready yet. **Settings → Status** shows whether the backend, the
activity data, the AI Assistant and Ollama are connected.

### Everyday commands

```bash
cd ~/AIAgentClassSelect
docker compose up -d                       # start (after a reboot, start Docker Desktop first)
docker compose down                        # stop
docker compose ps                          # status
docker compose logs -f frontend backend    # logs (Ctrl-C to stop following)
docker compose up -d                       # apply changes made to .env
git pull && docker compose up --build -d   # update the app and the activity data
```

Stopping or updating does not affect saved activities and preferences; they are stored in each browser (see
[Privacy](#privacy)). The app reads `data/courses.json` on every request, so a `git pull` that only changes data
needs no restart.

### What each installation owns

- Its own clone of the repository, including its own `data/` (mounted **read-only** into the backend) and `.env`.
- Its own Docker images and containers, built from that clone and named after the folder (e.g.
  `aiagentclassselect-backend`). There are no Docker volumes and no database.
- Its own browser storage on each device for saved activities and preferences.
- Ollama and its models are outside Docker and are only used, never changed, by the app.

Nothing depends on another person's Mac, Docker images, models or settings. To run two copies on one Mac, clone
into two differently named folders and give the second one other ports in its `.env`.

### Uninstall

```bash
cd ~/AIAgentClassSelect
docker compose down --rmi local     # removes this app's containers, network and images
cd .. && rm -rf AIAgentClassSelect  # removes the code, data and .env
ollama rm qwen2.5:1.5b              # optional: removes the model
```

The shared base images (`python:3.12-slim`, `node:20-alpine`) stay in Docker; remove them with `docker image rm`
if nothing else uses them. In Safari, saved activities disappear when you clear the site's website data.

## 3. Find the Mac's LAN IP address

The address is assigned by your router and can change (for example after a restart or on another network), so it
is not written anywhere in the configuration. Look it up when you need it:

```bash
ipconfig getifaddr en0        # Wi-Fi on most Macs; prints e.g. 192.168.1.23
ipconfig getifaddr en1        # try this if en0 prints nothing (some Macs, or Ethernet)
```

Or: **System Settings → Wi-Fi → Details…** (next to the connected network) → **IP address**.

Use the private address (usually `192.168.x.x`, `10.x.x.x` or `172.16–31.x.x`). Check it from the Mac first:

```bash
IP=$(ipconfig getifaddr en0); echo "http://$IP:3000"; curl -s "http://$IP:3000/health"
```

## 4. Open it on the iPhone (Safari)

1. Connect the iPhone to the **same Wi-Fi network** as the Mac (see the requirements below).
2. In Safari, type `http://<Mac LAN IP>:3000`, including `http://` and `:3000`.
3. Optional: **Share → Add to Home Screen** for a full-screen shortcut.

Safari may label the page "Not Secure". That is expected: the app is served over plain HTTP on your home network.
Don't type passwords or personal information into it (the app never asks for any).

Use the IP address, not the Mac's name (`My-Mac.local`): the development server only accepts `localhost` and IP
addresses and answers "Invalid Host header" to other host names (this protects against DNS-rebinding attacks).

### Same-Wi-Fi requirements

- Both devices are on the same network: same Wi-Fi name, or the Mac on Ethernet from the same router.
  2.4 GHz and 5 GHz bands of the same router are fine.
- Not a **guest network** and not a network with **client/AP isolation** (common on public, office, school and
  hotel Wi-Fi), which blocks devices from reaching each other.
- No **VPN** active on the iPhone or the Mac that captures local traffic. Turn it off, or allow local network
  access in the VPN app.
- iCloud Private Relay and Safari's "Hide IP address" do not affect local addresses.
- The Mac must be awake and Docker must be running.

## 5. Network security

**What is reachable from the Wi-Fi network:** only the frontend on port **3000** (or your `FRONTEND_PORT`).

**There is no login or access code.** Anyone on the same Wi-Fi network who knows (or scans for) the Mac's address
can open the app, browse activities and use the AI Assistant, which runs on your Mac's Ollama. They cannot see
another device's saved activities or preferences, and the app cannot change the activity data. Use it on a home
network you trust; run `docker compose down` when you're on a shared network.

A private Wi-Fi password is **not** the same as a login for the app: it keeps strangers off the network, but every
device and person already on it (family members, guests, a smart TV, a compromised gadget) can use the app. Other
limitations to be aware of:

- Anyone who can open the app can send AI Assistant questions, which use your Mac's CPU/GPU (each question is
  limited to 500 characters and `AI_MAX_ITERATIONS` model calls, but there is no rate limit).
- The frontend is the React **development** server (Create React App 5, which is no longer maintained; `npm audit`
  reports known issues in its build and dev-server packages). It is fine for a personal app on a trusted network,
  not for anything public. The app's source code it serves is the same as the public repository.
- Traffic is plain HTTP on your network, not encrypted.

To use the app only on the Mac itself, set `FRONTEND_BIND=127.0.0.1` in `.env` and run `docker compose up -d`; the
iPhone can then no longer connect.

| Service | Listens on | Reachable from |
|---|---|---|
| Frontend (React development server) | all interfaces, port 3000 (`127.0.0.1` only with `FRONTEND_BIND=127.0.0.1`) | the Mac and the local network |
| Backend (Flask API) | `127.0.0.1:8000` on the Mac; `0.0.0.0:8000` inside its container | the Mac, and the frontend container over the internal Docker network (`backend:8000`) |
| Ollama | `127.0.0.1:11434` on the Mac (Ollama's default) | the Mac, and the backend container through `host.docker.internal` |

- Phones never talk to the backend directly. The frontend server forwards the API paths (`/courses`, `/options`,
  `/health`, `/agent/chat`) to `backend:8000` (`frontend/src/setupProxy.js`), so the browser only uses port 3000.
  Create React App's own `proxy` setting (kept because it enables the Host-header check) also forwards other
  non-page requests to the backend, which has no other routes and answers them with 404.
- The backend sends no CORS headers, and API responses through the frontend carry none either, so other websites
  open in a browser cannot read the API. CORS is not an access control, though; the network rules above are.
- The backend mounts `data/` read-only.
- Do **not** set `OLLAMA_HOST=0.0.0.0`, remove `127.0.0.1:` from the backend's port mapping in
  `docker-compose.yml`, or set up router port forwarding. Any of these would expose more than the frontend.
  This edition is not meant for the internet.

Check what is listening:

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(3000|8000|11434) '
# expected:  *:3000   127.0.0.1:8000   127.0.0.1:11434
docker compose ps        # backend 127.0.0.1:8000->8000/tcp, frontend 0.0.0.0:3000->3000/tcp
```

## 6. Troubleshooting

**The iPhone can't connect (Safari times out or "could not connect to the server")**

1. On the Mac, `curl -s http://$(ipconfig getifaddr en0):3000/health` should print JSON. If it doesn't, the app is
   not running: `docker compose ps`, `docker compose logs frontend`.
2. Check the IP again (it may have changed) and that both devices are on the same Wi-Fi (see the requirements).
3. **macOS firewall:** System Settings → Network → Firewall → Options…. Docker must be allowed to receive incoming
   connections (an entry for Docker, "Allow incoming connections"). "Block all incoming connections" must be off.
   macOS usually asks the first time Docker publishes a port; if you clicked Deny, change it here. From Terminal:

   ```bash
   /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate --getblockall
   /usr/libexec/ApplicationFirewall/socketfilterfw --listapps | grep -A1 -i docker
   ```

   Third-party firewalls (Little Snitch, LuLu, security software) need the same permission.
4. Try another device on the Wi-Fi, or turn on the iPhone's hotspot, connect the Mac to it, and use the Mac's new
   IP. If that works, the router is isolating devices.

**"Invalid Host header"**: you used a host name; use the numeric IP address.

**The page loads but shows errors, or Settings shows the backend as unavailable**: `docker compose ps` and
`docker compose logs backend`. `curl -s localhost:8000/health` on the Mac checks the backend directly.

**Port 3000 or 8000 already in use** ("port is already allocated"): set `FRONTEND_PORT` / `BACKEND_PORT` in `.env`
(e.g. `3001`), then `docker compose up -d`, and use that port in the URLs.

**"Cannot connect to the Docker daemon"**: open Docker Desktop and wait until it is running.

**The build fails while downloading** (`failed to resolve source metadata`, timeouts): check the internet connection
and retry `docker compose up --build -d`. The base images are public; no Docker login is needed.

**AI Assistant: "Local AI model unavailable"**: the message says why (see the next entries). After fixing it,
use Settings → Status → Refresh. Answers take several seconds on the 1.5B model.

**AI Assistant: "model '…' is not installed"**: run the `ollama pull` it suggests, or set `AI_MODEL` in `.env` to a
model from `ollama list`, then `docker compose up -d`.

**AI Assistant: "no Ollama server is reachable"**: open the Ollama app (`curl -s http://127.0.0.1:11434/api/version`
should answer). If you changed Ollama's port, update `AI_BASE_URL`.

**AI Assistant: "The AI assistant is turned off"**: `AI_ENABLED=false` is set in `.env` or in your shell.

**AI answers time out or are very slow**: use a smaller model, or raise `AI_TIMEOUT` in `.env` (Intel Macs: `300`).

**Settings changed in `.env` have no effect**: run `docker compose up -d` after editing, and check that the shell
doesn't override them: `env | grep -E '^(AI_|FRONTEND_|BACKEND_)'`.

**Something still looks wrong after an update**: rebuild without cache with `docker compose build --no-cache` and
then `docker compose up -d`.

## Privacy

Saved activities, the child's age, preferred city, favorite categories and language are stored only in the
browser on each device (localStorage). They are not sent to the backend or anywhere else, are not shared between
devices, and are lost if you clear Safari's website data. AI Assistant questions are sent to the backend and to
Ollama on the Mac; the app does not save them, and they do not leave the Mac. The backend's container log
(`docker compose logs backend`) records each request line, which includes Discover search words and filters (they
are part of the URL) but not AI Assistant questions; the log is deleted with `docker compose down`.

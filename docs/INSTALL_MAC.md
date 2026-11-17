# Install and run on a Mac (personal edition)

The app runs on one Mac with Docker. You open it in a browser on that Mac, or on an iPhone (or any other phone,
tablet or computer) connected to the same Wi-Fi network. Nothing is put on the internet.

| Where | Address |
|---|---|
| On the Mac | `http://localhost:3000` |
| iPhone / other device on the same Wi-Fi | `http://<Mac LAN IP>:3000`, e.g. `http://192.168.1.23:3000` |

## 1. Prerequisites (once)

- **Docker Desktop for Mac** (Apple Silicon or Intel), started.
- **git**, to get the repository: `xcode-select --install` provides it.
- **Ollama** (optional, only for the AI Assistant): install the Ollama app from <https://ollama.com>, start it, and
  download the model once:

  ```bash
  ollama pull qwen2.5:1.5b
  ollama list            # qwen2.5:1.5b should be listed
  ```

  Without Ollama, Discover, Saved and Settings still work, and the AI Assistant shows that the local model is
  unavailable. To turn it off completely, start with `AI_ENABLED=false docker compose up -d`.

## 2. Start the app

```bash
git clone <repository URL> AIAgentClassSelect
cd AIAgentClassSelect
docker compose up --build -d      # first start builds the images (a few minutes)
docker compose ps                 # backend and frontend should be "running"
```

Open `http://localhost:3000` on the Mac. The frontend takes about 30 seconds to compile after a start; reload if
the page is not ready yet. **Settings → Status** shows whether the backend, the activity data, the AI Assistant and
Ollama are connected.

Stop it with `docker compose down`. Your saved activities and preferences are not affected; they are stored in each
browser (see [Privacy](#privacy)).

Activity data comes from `data/courses.json` in the repository. `git pull` gets the latest published data; the
app reads it on every request, so no restart is needed.

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

**What is reachable from the Wi-Fi network:** only the frontend on port **3000**.

**There is no login or access code.** Anyone on the same Wi-Fi network who knows (or scans for) the Mac's address
can open the app, browse activities and use the AI Assistant, which runs on your Mac's Ollama. They cannot see
another device's saved activities or preferences, and the app cannot change the activity data. Use it on a home
network you trust; run `docker compose down` when you're on a shared network.

| Service | Listens on | Reachable from |
|---|---|---|
| Frontend (React development server) | `0.0.0.0:3000` | the Mac and the local network |
| Backend (Flask API) | `127.0.0.1:8000` on the Mac; `0.0.0.0:8000` inside its container | the Mac, and the frontend container over the internal Docker network (`backend:8000`) |
| Ollama | `127.0.0.1:11434` on the Mac (Ollama's default) | the Mac, and the backend container through `host.docker.internal` |

- Phones never talk to the backend directly. The frontend server forwards the API paths (`/courses`, `/options`,
  `/health`, `/agent/chat`) to `backend:8000` (`frontend/src/setupProxy.js`), so the browser only uses port 3000.
- The backend sends no CORS headers, and API responses through the frontend carry none either, so other websites
  open in a browser cannot read the API. CORS is not an access control, though; the network rules above are.
- The backend mounts `data/` read-only.
- Do **not** set `OLLAMA_HOST=0.0.0.0`, change the backend port to `"8000:8000"`, or set up router port
  forwarding. Any of these would expose more than the frontend. This edition is not meant for the internet.

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

**AI Assistant: "Local AI model unavailable"**: start the Ollama app, check `ollama list` shows `qwen2.5:1.5b`,
then Settings → Status → Refresh. Answers take several seconds on the 1.5B model.

**Port 3000 or 8000 already in use**: stop the other program, or change the left-hand side of the mapping in
`docker-compose.yml` (for example `"3001:3000"`, and keep `127.0.0.1:` on the backend's).

## Privacy

Saved activities, the child's age, preferred city, favorite categories and language are stored only in the
browser on each device (localStorage). They are not sent to the backend or anywhere else, are not shared between
devices, and are lost if you clear Safari's website data. AI Assistant questions are sent to the backend and to
Ollama on the Mac; the app does not save them, and they do not leave the Mac. The backend's container log
(`docker compose logs backend`) records each request line, which includes Discover search words and filters (they
are part of the URL) but not AI Assistant questions; the log is deleted with `docker compose down`.

# AIAgentClassSelect — Local MVP Demo Guide

**Version:** 0.1.0
**Edition:** Local Mac + iPhone + Local AI Agent
**AI Runtime:** Ollama + Qwen 2.5
**Deployment:** Docker Compose on macOS
**Network:** Private local Wi-Fi only

## 1. What You Will Demonstrate

AIAgentClassSelect is a kids' activity discovery application with a local AI Agent.

The v0.1.0 MVP demonstrates:

- A React frontend and Python Flask backend.
- Kids' activity search using real activity data.
- English, Simplified Chinese and Traditional Chinese support.
- A local AI Agent powered by Ollama and Qwen.
- Real Python tool execution by the AI Agent.
- Docker-based local deployment.
- Access from Mac browsers and iPhone Safari over the same Wi-Fi network.

**Important:** v0.1.0 is a local MVP. AWS hosting, SaaS accounts, cloud AI and multi-tenant services are planned for v1.0.0.

## 2. Architecture

```text
Mac Browser / iPhone Safari
          |
          | HTTP :3000
          v
React Frontend (Docker)
          |
          | Internal API Proxy
          v
Flask Backend (Docker)
          |
          +---- data/courses.json
          |
          +---- Agent Orchestrator
                    |
                    v
              Ollama on Mac
                    |
                    v
              Qwen 2.5
                    |
                    v
              Python Tools
                - search_activities
                - filter_by_age
                - filter_by_date
                - get_activity_details
```

Only the frontend is accessible from the local network.

The backend and Ollama remain restricted to the Mac and Docker internal network.

## 3. Requirements

On the Mac:

- macOS
- Git
- Docker Desktop for Mac
- Ollama (required for AI Agent)
- At least 8 GB RAM recommended
- A supported local model, such as `qwen2.5:1.5b`

On the iPhone:

- Safari
- Same Wi-Fi network as the Mac
- No additional application installation

Internet access is needed for initial downloads and repository cloning. The local application and AI inference do not require a cloud AI API.

## 4. Installation on Mac

### Step 1 — Verify prerequisites

```bash
git --version
docker version
docker compose version
ollama --version
```

Make sure Docker Desktop is running.

Make sure the Ollama application is running.

### Step 2 — Download the project

```bash
git clone https://github.com/scmbuildrelease/AIAgentClassSelect.git

cd AIAgentClassSelect
```

For a release-specific demonstration, check out the published `v0.1.0` tag after it is available.

### Step 3 — Download the AI model

```bash
ollama pull qwen2.5:1.5b

ollama list
```

Verify the model is listed.

### Step 4 — Configure the application

```bash
cp .env.example .env
```

The default configuration should work for the documented Docker setup.

Check the following settings if necessary:

```text
AI_ENABLED=true
AI_MODEL=qwen2.5:1.5b
AI_BASE_URL=http://host.docker.internal:11434
```

Do not expose Ollama on the network.

### Step 5 — Start the application

```bash
docker compose up --build -d
```

Check container status:

```bash
docker compose ps
```

Both frontend and backend should be running.

### Step 6 — Open the application

On the Mac:

```text
http://localhost:3000
```

Wait for the frontend to finish compiling if this is the first startup.

Open Settings → Status and verify:

- Backend: Connected
- Activity data: Connected (with the date of the data)
- AI Assistant: Connected (with the model name)
- Ollama (local model): Connected

## 5. Mac Browser Demo

### Demo A — Discover Activities

1. Open Discover.
2. Search for `robotics`.
3. Verify that matching activities appear.
4. Search for `机器人`.
5. Verify that Chinese keyword search works.
6. Select the STEM category.
7. Open Filters.
8. Select age 8.
9. Select San Jose.
10. Open an activity's official website (**Official page ↗**).

Expected result:

- Search returns real activity records.
- Filters update the results.
- Cards show available activity details ("Not published" where the provider does not state a detail).
- Official links point to the provider's website.

### Demo B — Saved Activities

1. Tap **Save** on an activity card.
2. Open Saved.
3. Verify the saved activity appears.
4. Remove it.
5. Reload the page.

Expected result:

Saved activities remain in the browser's local storage until removed or browser data is cleared.

## 6. Local AI Agent Demo

Open the AI Assistant tab.

Try the following questions.

| Test | Question |
|---|---|
| 1 | Find robotics classes |
| 2 | Find robotics for an 8-year-old in San Jose |
| 3 | Find summer camps in San Jose |
| 4 | Find activities in June |
| 5 | 圣何塞适合8岁孩子的机器人课 |
| 6 | Find underwater basket weaving in Gilroy |

Behind each request:

1. The local model receives the question.
2. The model selects one or more available tools.
3. The backend validates tool arguments.
4. Python executes the tools.
5. Tool results are returned to the model.
6. The model generates its final response.
7. The frontend displays the AI summary and activity cards.
8. The execution trace shows the tools actually used.

What you can verify on screen: the answer labelled **AI-generated summary**, the activity cards, and
**Searches the assistant ran**, which lists each tool call with its arguments. A call the backend rejected
(for example an unknown category) is shown in red with the reason. Test 6 should report that nothing was found.

The four available tools are:

- `search_activities`
- `filter_by_age`
- `filter_by_date`
- `get_activity_details`

**Important:** The model generates the summary, but activity cards and official links are based on actual activity data. Always verify activity details against the cards and official provider pages.

### AI failure demonstration

Optional:

1. Stop the Ollama application on the Mac.
2. Submit an AI question.
3. Verify that the application reports that local AI is unavailable ("Local AI model unavailable … no Ollama
   server is reachable").
4. Restart Ollama.
5. Refresh the status (Settings → Status → Refresh).
6. Submit the question again.

Expected result:

The application should report the failure clearly and should not pretend that an AI request succeeded.

## 7. iPhone Safari Demo

### Step 1 — Find the Mac IP address

On the Mac:

```bash
ipconfig getifaddr en0
```

If this returns nothing:

```bash
ipconfig getifaddr en1
```

Example:

```text
192.168.12.191
```

### Step 2 — Verify network access

On the Mac:

```bash
IP=$(ipconfig getifaddr en0)

curl -i "http://$IP:3000/health"
```

This goes through the frontend on port 3000, which forwards `/health` to the backend. It should return
`HTTP/1.1 200` and JSON containing `"backend":"ok"`.

### Step 3 — Connect the iPhone

1. Connect the iPhone to the same Wi-Fi network as the Mac.
2. Open Safari.
3. Enter:

```text
http://192.168.12.191:3000
```

Replace the example IP with the current Mac IP.

### Step 4 — Demonstrate on iPhone

1. Open Discover.
2. Search for robotics.
3. Open Filters.
4. Select age and city.
5. Open an activity.
6. Save an activity.
7. Open AI Assistant.
8. Ask a question in English.
9. Ask a question in Chinese.
10. Verify the AI-generated summary and activity cards.
11. Open Saved.
12. Change the application language in Settings.

Expected result:

The iPhone uses the Mac-hosted frontend and backend. The AI inference still runs locally on the Mac through Ollama.

The iPhone does not need Ollama installed.

Optional: Use Safari Share → Add to Home Screen.

For a full device checklist, see [PHASE5_IPHONE_TEST.md](PHASE5_IPHONE_TEST.md).

## 8. Verify Network Security

On the Mac:

```bash
docker compose ps

lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(3000|8000|11434) '
```

Expected output (Docker's ports appear under the `com.docker` process):

```text
com.docke ... TCP 127.0.0.1:8000 (LISTEN)
com.docke ... TCP *:3000 (LISTEN)
ollama    ... TCP 127.0.0.1:11434 (LISTEN)
```

Expected network boundaries:

| Service | Expected access |
|---|---|
| Frontend :3000 | Mac and trusted local Wi-Fi |
| Backend :8000 | Mac localhost and Docker internal network |
| Ollama :11434 | Mac localhost and Docker host bridge |

From the iPhone, the backend port should not be directly accessible (`http://<Mac IP>:8000/health` does not load).

Do not configure router port forwarding.

Do not expose this local MVP to the public internet.

There is no login or account system in v0.1.0. Anyone on the trusted Wi-Fi who can reach the frontend can use the application, including the AI Assistant on your Mac. A Wi-Fi password is not an app login. To limit the app to the Mac itself, set `FRONTEND_BIND=127.0.0.1` in `.env`.

## 9. Test Application Restart

On the Mac:

```bash
docker compose down

docker compose up -d

docker compose ps
```

Wait for the frontend to start, then reload the Mac browser and iPhone Safari.

Verify that the application works again.

## 10. Stop the Application

```bash
docker compose down
```

Ollama can remain running independently.

To stop Ollama, quit the Ollama application on macOS.

## 11. Troubleshooting

| Problem | Resolution |
|---|---|
| Docker cannot start | Open Docker Desktop and wait until ready |
| Frontend unavailable | Check `docker compose ps` and frontend logs |
| Backend unavailable | Check backend logs and `/health` |
| iPhone cannot connect | Verify same Wi-Fi (not a guest network), VPN off, Mac IP and firewall permissions |
| Invalid Host header | Use the numerical Mac IP instead of `.local` |
| AI model unavailable | Check Ollama and `ollama list` |
| Model not found | Run `ollama pull <AI_MODEL>` (the error message shows the exact command for the configured model) |
| AI response too slow | Check model and `AI_TIMEOUT` |
| Invalid AI configuration | Fix `AI_TIMEOUT` (1–3600 seconds) or `AI_MAX_ITERATIONS` (1–20) in `.env`, then `docker compose up -d` |
| Port already allocated | Change the corresponding port in `.env` |
| iPhone cannot reach backend | Expected: backend is not exposed to the LAN |

Useful commands:

```bash
docker compose logs --tail=100 frontend backend

docker compose ps

ollama list

curl http://127.0.0.1:11434/api/version

curl http://localhost:8000/health
```

## 12. Known Limitations

- Local deployment only.
- Bay Area activity data only.
- No user accounts or cloud synchronization.
- Saved activities are stored independently in each browser.
- AI summary quality depends on the selected local model.
- Small local models can misunderstand questions or filters.
- With `qwen2.5:1.5b`, questions in Traditional Chinese are usually answered in Simplified Chinese (cards and interface text are correct).
- No rate limit: anyone on the Wi-Fi can send AI questions to the Mac.
- The frontend runs on the Create React App development server, which is suitable for a trusted home network only.
- Internet-facing SaaS deployment is not included.
- AWS deployment and cloud AI are planned for v1.0.0.

## 13. Demo Acceptance Checklist

Before presenting the application:

- [ ] Docker Desktop is running.
- [ ] Ollama is running.
- [ ] The configured Qwen model is installed.
- [ ] Backend is healthy.
- [ ] Frontend is accessible.
- [ ] Discover search works.
- [ ] Chinese search works.
- [ ] Filters work.
- [ ] Saved works.
- [ ] AI Agent successfully calls tools.
- [ ] Agent execution trace is visible.
- [ ] AI cards match real activity data.
- [ ] iPhone Safari can access the application.
- [ ] iPhone AI requests work through the Mac.
- [ ] Restart and recovery work.
- [ ] No cloud AI credentials are required.

Record the actual test date, Mac model, macOS version, Docker version, Ollama version, model name and iPhone/iOS version.

| Item | Value |
|---|---|
| Test date | |
| Mac model / chip / memory | |
| macOS version | |
| Docker version | |
| Ollama version | |
| Model | |
| iPhone model / iOS version | |

Only mark a test as passed after performing it.

## 14. Product Roadmap

**v0.1.0 — Local MVP**

Mac + Docker + React + Flask + Ollama + Qwen + iPhone Safari.

**v1.0.0 — AWS SaaS**

Cloud deployment, user accounts, multi-user data management, cloud AI services, security, monitoring and production infrastructure.

---

Project: https://github.com/scmbuildrelease/AIAgentClassSelect

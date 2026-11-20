# Known limitations — v0.1.0

These were observed in live testing of v0.1.0 on 2026-11-18 and 2026-11-19 (Apple M3, 8 GB, macOS 15.7.3,
Ollama 0.40.11, `qwen2.5:1.5b`, data last checked 2026-11-16). **None of them is fixed in v0.1.0.** The evidence is in
[V0.1.0_READINESS_REPORT.md](V0.1.0_READINESS_REPORT.md).

The safeguard that does hold: the activity cards always come from the data, and the app never shows an
activity, link or tool result that doesn't exist. What can go wrong is *which* real activities the model
selects, and what its summary says about them.

## AI Assistant (local model `qwen2.5:1.5b`)

| Limitation | Observed example |
|---|---|
| **The model may pick the wrong tool or arguments.** | "Which activities are suitable for an 8-year-old?" searched the *language* category with keyword "coding". "Show me the details of activity clubscikidz-ages-7-9-3c3f893a3e" searched for "clubscikidz" instead of calling `get_activity_details`. |
| **Age and date constraints in natural language are not guaranteed.** The model often skips `filter_by_age` or `filter_by_date`. | "Find activities in June" (and "… in June 2027") returned November–December outdoor events while the summary said "activities in June". "Robotics classes for a 10 year old" listed camps for ages 7–9. "Camps for a 6 year old in July 2027" listed camps for ages 7–9 and a February camp. |
| **The tool choice can change with the date.** The system prompt contains today's date, and that alone changes what the model does. | "STEM classes for age 8" used `filter_by_age` (13 cards) on 2026-11-18. On 2026-11-19, 8 of 8 live API runs called only `search_activities` and returned 17 cards, some outside age 8. With the date pinned in test containers, it used the filter for 2026-11-18 only, not for any later date tested up to 2026-12-15. Asking explicitly ("Find STEM classes, then filter them by age 8") used the filter on every date tested. On a given date, repeating a question gave the same result. |
| **The summary can contradict the cards.** | "Find swimming lessons for age 8" showed the YMCA Swim Lessons card (ages not published), but the summary said there are none. |
| **`get_activity_details` is reliable only with an explicit activity ID.** | "Get details for activity id clubscikidz-ages-7-9-3c3f893a3e" worked in every run. "Search for Junior Robot Engineer, then get its full details" passed a placeholder ID, which the backend rejected. Questions about one activity by name usually get only `search_activities`. |
| **Traditional Chinese questions get Simplified Chinese answers.** The prompt asks for Traditional Chinese, but the 1.5B model doesn't follow it. | "聖荷西適合8歲孩子的機器人課程" with the app set to 繁體中文 gave correct cards, but the summary was in Simplified Chinese. |
| **Names and places can be mistranslated in Chinese answers.** | Church and school names in the Chinese summaries were transliterated inconsistently. Card text is not affected. |
| **Repeated tool calls.** | On 2026-11-18, "STEM classes for age 8" repeated search + age filter; the trace then showed "Skipped calls … (limit 4)". The result was still correct. |
| **The local model can be slow.** | Answers took 1–20 seconds on an M3 with 8 GB. The first question after Ollama starts is slower while the model loads. Intel Macs and larger models are slower (raise `AI_TIMEOUT`). |

**Always check AI results against the activity records:** the cards, Discover and the official provider pages.
For demos, use the verified prompts in [DEMO_GUIDE.md → AI Agent demonstration](DEMO_GUIDE.md#7-ai-agent-demonstration).

Only `qwen2.5:1.5b` has been tested. Larger models may follow instructions better; that is untested.

## Platform and deployment

- **Local only.** One Mac serves the app to devices on the same Wi-Fi. There is no cloud hosting, user accounts,
  sync or multi-tenancy; these are planned for v1.0.0 (AWS SaaS).
- **No login and no rate limit.** Anyone on the Wi-Fi who can reach port 3000 can use the app and the Mac's AI.
  `FRONTEND_BIND=127.0.0.1` restricts it to the Mac. Traffic is plain HTTP.
- **Development web server.** The frontend runs on the Create React App dev server (unmaintained). `npm audit`
  reports issues in its build and dev-server dependencies. It's fine for a trusted home network, not for public
  hosting.
- **No `package-lock.json`.** Frontend dependency versions can differ between builds.
- **Saved activities and settings are per browser and per device.**

## Data

- San Francisco Bay Area only.
- Only as fresh as the last manual discovery run (Settings shows the date).
- Ages, dates and prices appear only when the provider publishes them ("Not published" otherwise). Activities
  without published ages or dates are left out by the age and date filters.

## Not yet tested

- A physical iPhone in Safari. The layout was checked only in headless Chrome at iPhone sizes.
- A second Mac, Intel Macs, other macOS versions, and models other than `qwen2.5:1.5b`.
- The GitHub Actions Jest job, which hasn't run on GitHub yet.

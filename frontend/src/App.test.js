import React, { act } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// Discover / AI Assistant / Saved / Settings against a mocked same-origin API (fetch). No real network.
global.IS_REACT_ACT_ENVIRONMENT = true;

const COURSES = [
  { id: "robo", name: "LEGO Robotics Camp", provider: "Bot Lab", age_text: "Ages 7-9", price: "$450",
    start_date: "2026-12-21", end_date: "2026-12-23", city: "San Jose", detail_url: "https://botlab.example.org/robotics" },
  { id: "zhong", name: "中文学校周六班", provider: "谷雨中文学校", sessions: ["2026-11-21 10:00", "2026-11-28 10:00"],
    source_url: "https://school.example.org/" },
];
const AI_OK = {
  answer: "LEGO Robotics Camp by Bot Lab, ages 7-9.", agent_status: "ok", model: "qwen2.5:1.5b", error: null,
  activities: [{ ...COURSES[0], link: COURSES[0].detail_url, display: { name: "LEGO Robotics Camp", kind: "original" } }],
  tools_used: [{ tool: "search_activities", arguments: { keyword: "robotics" }, ok: true, result_count: 1 }],
};
const HEALTH = { backend: "ok", data: { available: true, activities: 589, last_checked: "2026-11-16T04:29:53Z" },
                 ai: { enabled: true, provider: "ollama", model: "qwen2.5:1.5b", ollama: "ok", error: null } };

let container, root, calls, agentReply, coursesReply, health;

function reply(body, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(body) });
}

function mockFetch(url, options = {}) {
  calls.push({ url, options });
  if (url === "/agent/chat") return reply(agentReply);
  if (url === "/health") return reply(health);
  if (url === "/options") {
    return reply({ categories: { stem: { label: "Math, Science, STEM & Coding", short: "STEM" },
                                 language: { label: "Chinese & Language Classes", short: "Language" } },
                   cities: [{ name: "San Jose", count: 98 }, { name: "Fremont", count: 30 }] });
  }
  if (coursesReply) return coursesReply();
  const params = new URLSearchParams(url.split("?")[1]);
  const q = (params.get("q") || "").toLowerCase();
  const items = COURSES.filter(c => !q || c.name.toLowerCase().includes(q.slice(0, 5))).map(c => ({
    ...c, title: c.name, link: c.detail_url || c.source_url, display: { name: `${c.name} (${params.get("lang")})`, kind: "original" },
  }));
  return reply(items);
}

const flush = () => act(async () => { for (let i = 0; i < 6; i++) await new Promise(r => setTimeout(r, 0)); });
const $ = sel => container.querySelector(sel);
const $$ = sel => [...container.querySelectorAll(sel)];
const visible = sel => $$(sel).filter(el => !el.closest("[hidden]"));
const tabButton = label => $$(".tabbar .tab").find(b => b.textContent.includes(label));
const cardNames = () => visible(".card-title").map(a => a.textContent);
const courseCalls = () => calls.filter(c => c.url.startsWith("/courses")).map(c => c.url);

async function mount() {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => { root.render(<App />); });
  await flush();
}

async function click(el) {
  await act(async () => { el.click(); });
  await flush();
}

async function typeInto(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => {
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function choose(select, value) {
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

async function submit(form) {
  await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
}

beforeEach(async () => {
  calls = [];
  agentReply = AI_OK;
  coursesReply = null;
  health = HEALTH;
  global.fetch = jest.fn(mockFetch);
  window.localStorage.clear();
  await mount();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test("four sections in the bottom tab bar (and the desktop top bar)", () => {
  expect($$(".tabbar .tab").map(b => b.textContent)).toEqual(["⌕Discover", "✦AI Assistant", "★Saved", "⚙Settings"]);
  expect($$(".topnav .tab")).toHaveLength(4);
  expect($$(".tabbar .tab")[0].getAttribute("aria-current")).toBe("page");
  expect(visible("section")).toHaveLength(1);
});

test("Discover shows real API data, including sessions when there is no start date", () => {
  expect(courseCalls()[0]).toBe("/courses?lang=en&q=");
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)", "中文学校周六班 (en)"]);
  const text = $(".cards").textContent;
  expect(text).toContain("2026-12-21 – 2026-12-23");
  expect(text).toContain("2026-11-21 10:00 (+1 more)");
  expect(text).toContain("Not published");                       // missing price is not invented
  expect(visible(".source")[0].getAttribute("href")).toBe("https://botlab.example.org/robotics");
});

test("search and filters are sent to GET /courses", async () => {
  await typeInto(visible('input[type="search"]')[0], "robotics");
  await submit(visible("form.searchbar")[0]);
  expect(courseCalls()).toContain("/courses?lang=en&q=robotics");
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)"]);
  await click(visible(".chips .chip").find(b => b.textContent === "STEM"));
  await choose(visible(".filters select")[0], "8");
  await choose(visible(".filters select")[1], "San Jose");
  expect(courseCalls().pop()).toBe("/courses?lang=en&q=robotics&age=8&city=San+Jose&category=stem");
});

test("API errors show a message and a retry button", async () => {
  coursesReply = () => reply({ error: "age must be a whole number from 0 to 18" }, false);
  await choose(visible(".filters select")[0], "8");
  expect(visible('[role="alert"]')[0].textContent).toContain("age must be a whole number");
  coursesReply = null;
  await click(visible(".banner .link-button")[0]);
  expect(cardNames()).toHaveLength(2);
});

test("saving keeps the activity in Saved across reloads (localStorage)", async () => {
  await click(visible(".save")[0]);
  expect(visible(".save")[0].getAttribute("aria-pressed")).toBe("true");
  expect(JSON.parse(window.localStorage.getItem("aiacs.saved"))[0].id).toBe("robo");
  act(() => root.unmount());
  container.remove();
  await mount();
  await click(tabButton("Saved"));
  expect(tabButton("Saved").textContent).toContain("(1)");
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)"]);
  expect(courseCalls()).toContain("/courses?lang=en&all=1");
  await click(visible(".save")[0]);
  expect(visible(".empty")[0].textContent).toContain("No saved activities");
});

test("AI Assistant posts to /agent/chat and labels the summary, cards and real tool calls", async () => {
  await click(tabButton("AI Assistant"));
  await typeInto(visible(".composer input")[0], "robotics for an 8 year old");
  await submit(visible(".composer")[0]);
  const chat = calls.find(c => c.url === "/agent/chat");
  expect(chat.options.method).toBe("POST");
  expect(JSON.parse(chat.options.body)).toEqual({ message: "robotics for an 8 year old", lang: "en" });
  expect(visible(".msg.user")[0].textContent).toContain("robotics for an 8 year old");
  expect(visible(".msg.ai .bubble")[0].textContent).toContain("AI-generated summary");
  expect(visible(".msg.ai .answer")[0].textContent).toBe("LEGO Robotics Camp by Bot Lab, ages 7-9.");
  expect(visible(".msg.ai")[0].textContent).toContain("Activities found by the assistant's searches");
  expect(visible(".trace li")[0].textContent).toBe('Keyword search {"keyword":"robotics"} → 1');
  expect(cardNames()).toEqual(["LEGO Robotics Camp"]);
});

test("AI answers render **bold** and http(s) links only, never raw HTML", async () => {
  agentReply = { ...AI_OK, answer: "1. **Junior Robot Engineer** - [Details](https://example.org/jre) " +
                 "<img src=x onerror=alert(1)> [bad](javascript:alert(1))" };
  await click(tabButton("AI Assistant"));
  await typeInto(visible(".composer input")[0], "robotics");
  await submit(visible(".composer")[0]);
  const answer = visible(".msg.ai .answer")[0];
  expect(answer.querySelector("strong").textContent).toBe("Junior Robot Engineer");
  expect([...answer.querySelectorAll("a")].map(a => a.getAttribute("href"))).toEqual(["https://example.org/jre"]);
  expect(answer.querySelector("img")).toBeNull();
  expect(answer.textContent).toContain("<img src=x onerror=alert(1)> [bad](javascript:alert(1))");
});

test("AI Assistant shows backend/Ollama errors instead of an answer", async () => {
  agentReply = { agent_status: "unavailable", model: "qwen2.5:1.5b", activities: [], tools_used: [], answer: null,
                 error: "Local AI model unavailable: no Ollama server is reachable" };
  await click(tabButton("AI Assistant"));
  await typeInto(visible(".composer input")[0], "robotics");
  await submit(visible(".composer")[0]);
  expect(visible('.msg.ai [role="alert"]')[0].textContent).toContain("no Ollama server is reachable");
  expect(visible(".msg.ai .answer")).toHaveLength(0);
});

test("Settings: live status, language and preferences used by Discover", async () => {
  await click(tabButton("Settings"));
  const rows = visible(".status-row").map(r => r.textContent);
  expect(rows[0]).toContain("Connected");
  expect(rows[1]).toContain("589 current activities, last checked 2026-11-16");
  expect(rows[3]).toContain("Ollama (local model)Connected");
  await choose(visible(".row select")[1], "8");
  expect(JSON.parse(window.localStorage.getItem("aiacs.prefs")).age).toBe("8");
  expect(courseCalls().pop()).toBe("/courses?lang=en&q=&age=8");
  await choose(visible(".row select")[0], "zh-Hans");
  expect($("h1").textContent).toBe("儿童活动");
  expect(tabButton("发现")).toBeTruthy();
  expect(courseCalls().pop()).toBe("/courses?lang=zh-Hans&q=&age=8");
});

async function remount() {
  act(() => root.unmount());
  container.remove();
  await mount();
}

async function ask(question) {
  await click(tabButton("AI Assistant"));
  await typeInto(visible(".composer input")[0], question);
  await submit(visible(".composer")[0]);
}

test("Saved keeps showing an activity that is no longer listed, with a note", async () => {
  window.localStorage.setItem("aiacs.saved", JSON.stringify([{ id: "gone", name: "Spring Pottery 2025",
    provider: "Clay Studio", link: "https://clay.example.org/", savedAt: "2025-03-01T10:00:00.000Z" }]));
  await remount();
  await click(tabButton("Saved"));
  expect(courseCalls()).toContain("/courses?lang=en&all=1");
  expect(cardNames()).toEqual(["Spring Pottery 2025"]);
  expect(visible(".note")[0].textContent).toBe("No longer listed or already past; showing what you saved. · Saved 2025-03-01");
});

test("Clear saved asks first and only clears when confirmed", async () => {
  await click(visible(".save")[0]);
  await click(tabButton("Settings"));
  const clear = () => visible(".secondary.danger")[0];
  window.confirm = jest.fn(() => false);
  await click(clear());
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Remove all 1 saved activities"));
  expect(JSON.parse(window.localStorage.getItem("aiacs.saved"))).toHaveLength(1);
  window.confirm = jest.fn(() => true);
  await click(clear());
  expect(JSON.parse(window.localStorage.getItem("aiacs.saved"))).toEqual([]);
  expect(visible(".secondary.danger")).toHaveLength(0);
});

test("Traditional Chinese interface, remembered after reload, and sent to the AI", async () => {
  await click(tabButton("Settings"));
  await choose(visible(".row select")[0], "zh-Hant");
  expect($("h1").textContent).toBe("兒童活動");
  expect(document.documentElement.lang).toBe("zh-Hant");
  calls = [];
  await remount();
  expect(tabButton("探索").getAttribute("aria-current")).toBeNull();  // still on Settings after reload
  expect(courseCalls()[0]).toBe("/courses?lang=zh-Hant&q=");
  await click(tabButton("AI 助手"));
  await typeInto(visible(".composer input")[0], "聖荷西的機器人課程");
  await submit(visible(".composer")[0]);
  expect(JSON.parse(calls.find(c => c.url === "/agent/chat").options.body).lang).toBe("zh-Hant");
  expect(visible(".msg.ai .bubble")[0].textContent).toContain("AI 生成的摘要");
});

test("links that are not http(s) are never rendered", async () => {
  coursesReply = () => reply([{ id: "x", name: "Bad link", link: "javascript:alert(1)", display: { name: "Bad link" } }]);
  await typeInto(visible('input[type="search"]')[0], "bad");
  await submit(visible("form.searchbar")[0]);
  expect(visible(".card-title")[0].tagName).toBe("SPAN");
  expect(visible(".card a")).toHaveLength(0);
});

test("Discover says so when nothing matches", async () => {
  coursesReply = () => reply([]);
  await typeInto(visible('input[type="search"]')[0], "underwater basket weaving");
  await submit(visible("form.searchbar")[0]);
  expect(cardNames()).toEqual([]);
  expect(visible(".status")[0].textContent).toBe("No matching activities.");
});

test("AI Assistant warns when the model used no tools or hit the step limit", async () => {
  agentReply = { ...AI_OK, agent_status: "no_tools_used", tools_used: [], activities: [], answer: "Try LEGO camps." };
  await ask("robotics");
  expect(visible(".msg.ai .banner.warn")[0].textContent).toContain("not based on the activity data");
  agentReply = { ...AI_OK, agent_status: "max_iterations", answer: "The assistant stopped after 5 model calls." };
  await typeInto(visible(".composer input")[0], "robotics again");
  await submit(visible(".composer")[0]);
  expect(visible(".msg.ai .banner.warn")[1].textContent).toContain("step limit");
  expect(visible(".msg.ai")[1].querySelectorAll(".card")).toHaveLength(1);  // cards still come from tool results
});

test("Settings shows Ollama problems and invalid AI settings", async () => {
  health = { ...HEALTH, ai: { ...HEALTH.ai, ollama: "unavailable", error: "no Ollama server is reachable at http://host.docker.internal:11434" } };
  await click(tabButton("Settings"));
  const refresh = () => click(visible(".group .secondary").find(b => b.textContent === "Refresh"));
  await refresh();  // Settings checked /health when the app started
  let rows = visible(".status-row").map(r => r.textContent);
  expect(rows[2]).toContain("AI AssistantConnected");
  expect(rows[3]).toContain("Unavailable");
  expect(rows[3]).toContain("no Ollama server is reachable");
  health = { ...HEALTH, ai: { ...HEALTH.ai, ollama: "not_checked", error: "invalid AI configuration: AI_TIMEOUT must be a number" } };
  await refresh();
  rows = visible(".status-row").map(r => r.textContent);
  expect(rows[2]).toContain("Unavailable");
  expect(rows[2]).toContain("AI_TIMEOUT must be a number");
  expect(rows[3]).toContain("Not checked");
});

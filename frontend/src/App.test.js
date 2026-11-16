import React, { act } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// One search box: AI agent on submit, keyword search as button and as fallback, cards from GET /courses.
global.IS_REACT_ACT_ENVIRONMENT = true;

const COURSES = [
  { id: "robo", name: "LEGO Robotics Camp", provider: "Bot Lab", age_text: "Ages 7-9", price: "$450",
    detail_url: "https://botlab.example.org/robotics" },
  { id: "zhong", name: "中文学校周六班", provider: "谷雨中文学校", source_url: "https://school.example.org/" },
];
const AI_OK = {
  answer: "LEGO Robotics Camp by Bot Lab, ages 7-9.", agent_status: "ok", model: "qwen2.5:1.5b", error: null,
  activities: [{ id: "robo", name: "LEGO Robotics Camp", link: "https://botlab.example.org/robotics" }],
  tools_used: [{ tool: "search_activities", arguments: { keyword: "robotics" }, ok: true, result_count: 1 }],
};

let container, root, calls, agentReply;

function mockFetch(url, options = {}) {
  calls.push({ url, options });
  if (url === "/agent/chat") return Promise.resolve({ json: () => Promise.resolve(agentReply) });
  const params = new URLSearchParams(url.split("?")[1]);
  const q = (params.get("q") || "").toLowerCase();
  const lang = params.get("lang");
  const items = COURSES.filter(c => !q || c.name.toLowerCase().includes(q.slice(0, 5))).map(c => ({
    ...c, title: c.name, link: c.detail_url || c.source_url,
    display: { name: `${c.name} (${lang})`, kind: "original" },
  }));
  return Promise.resolve({ json: () => Promise.resolve(items) });
}

const flush = () => act(async () => { for (let i = 0; i < 5; i++) await new Promise(r => setTimeout(r, 0)); });
const input = () => container.querySelector("input");
const button = label => [...container.querySelectorAll("button")].find(b => b.textContent === label);
const cardNames = () => [...container.querySelectorAll("a strong")].map(s => s.textContent);
const courseCalls = () => calls.filter(c => c.url.startsWith("/courses")).map(c => c.url);
const agentCalls = () => calls.filter(c => c.url === "/agent/chat");

async function type(value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => {
    setter.call(input(), value);
    input().dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function click(label) {
  await act(async () => { button(label).click(); });
  await flush();
}

beforeEach(async () => {
  calls = [];
  agentReply = AI_OK;
  global.fetch = jest.fn(mockFetch);
  window.localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => { root.render(<App />); });
  await flush();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test("renders exactly one text input and the full list", () => {
  expect(container.querySelectorAll("input, textarea")).toHaveLength(1);
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)", "中文学校周六班 (en)"]);
  expect(courseCalls()).toEqual(["/courses?lang=en&q="]);
});

test("typing does not search; submitting asks the AI agent and shows only its tool results", async () => {
  await type("robotics for an 8 year old");
  await flush();
  expect(agentCalls()).toHaveLength(0);
  expect(courseCalls()).toHaveLength(1);
  await click("Ask AI");
  const [chat] = agentCalls();
  expect(chat.options.method).toBe("POST");
  expect(JSON.parse(chat.options.body)).toEqual({ message: "robotics for an 8 year old", lang: "en" });
  expect(container.textContent).toContain("LEGO Robotics Camp by Bot Lab, ages 7-9.");
  expect(container.textContent).toContain('search_activities({"keyword":"robotics"}) → 1');
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)"]);
  expect(container.querySelector("a").getAttribute("href")).toBe("https://botlab.example.org/robotics");
  expect(container.querySelectorAll("input, textarea")).toHaveLength(1);
});

test("falls back to the keyword search when the AI is unavailable", async () => {
  agentReply = { agent_status: "unavailable", model: "qwen2.5:1.5b", activities: [], tools_used: [],
                 error: "Local AI model unavailable: no Ollama server is reachable" };
  await type("robotics");
  await click("Ask AI");
  expect(courseCalls()).toContain("/courses?lang=en&q=robotics");
  expect(container.textContent).toContain("AI assistant unavailable, so these are keyword search results");
  expect(container.textContent).toContain("no Ollama server is reachable");
  expect(cardNames()).toEqual(["LEGO Robotics Camp (en)"]);
});

test("the keyword search button uses the existing search without the AI", async () => {
  await type("中文学校");
  await click("Keyword search");
  expect(agentCalls()).toHaveLength(0);
  expect(courseCalls()).toContain("/courses?lang=en&q=%E4%B8%AD%E6%96%87%E5%AD%A6%E6%A0%A1");
  expect(cardNames()).toEqual(["中文学校周六班 (en)"]);
});

test("switching language keeps the AI results and refetches their display text", async () => {
  await type("robotics");
  await click("Ask AI");
  const select = container.querySelector("select");
  await act(async () => {
    select.value = "zh-Hans";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  expect(container.querySelector("h1").textContent).toBe("儿童活动");
  expect(button("问 AI")).toBeTruthy();
  expect(courseCalls()).toContain("/courses?lang=zh-Hans&q=");
  expect(cardNames()).toEqual(["LEGO Robotics Camp (zh-Hans)"]);
  expect(container.textContent).toContain("AI 助手（本地模型）");
});

test("clearing the input restores the full list", async () => {
  await type("robotics");
  await click("Keyword search");
  expect(cardNames()).toHaveLength(1);
  await type("");
  await flush();
  expect(cardNames()).toHaveLength(2);
});

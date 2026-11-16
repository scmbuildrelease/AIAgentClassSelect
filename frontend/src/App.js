import React, { useEffect, useState } from "react";
import Assistant from "./Assistant";

// UI text only. Activity titles/descriptions come from the API exactly as published.
const UI = {
  en: {
    title: "Kids Activities", search: "Ask or search (e.g. robotics for an 8 year old, 机器人, 夏令营)",
    ask: "Ask AI", keyword: "Keyword search", lang: "Language",
    original: "Original text", source: "Official page", notPublished: "Not published",
    ages: "Ages", dates: "Dates", price: "Price", none: "No matching activities.",
    kind: { provider: "From the provider's own page", manual: "Translation (human)",
            machine: "Machine translation", original_only: "Only available in the original language" },
  },
  "zh-Hans": {
    title: "儿童活动", search: "提问或搜索（如：圣何塞 8 岁孩子的机器人课、编程、summer camp）",
    ask: "问 AI", keyword: "关键词搜索", lang: "语言",
    original: "原文", source: "官方页面", notPublished: "未公布",
    ages: "年龄", dates: "日期", price: "费用", none: "没有符合条件的活动。",
    kind: { provider: "来自机构的中文/英文页面", manual: "人工翻译",
            machine: "机器翻译", original_only: "仅有原文" },
  },
  "zh-Hant": {
    title: "兒童活動", search: "提問或搜尋（如：聖荷西 8 歲孩子的機器人課、程式設計、summer camp）",
    ask: "問 AI", keyword: "關鍵字搜尋", lang: "語言",
    original: "原文", source: "官方頁面", notPublished: "未公布",
    ages: "年齡", dates: "日期", price: "費用", none: "沒有符合條件的活動。",
    kind: { provider: "來自機構的中文/英文頁面", manual: "人工翻譯",
            machine: "機器翻譯", original_only: "僅有原文" },
  },
};

const FONT_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "PingFang TC", ' +
  '"Hiragino Sans GB", "Microsoft YaHei", "Microsoft JhengHei", "Noto Sans CJK SC", "Noto Sans CJK TC", sans-serif';

function initialLang() {
  try {
    const saved = localStorage.getItem("lang");
    if (saved && UI[saved]) return saved;
  } catch (e) { /* storage unavailable */ }
  const nav = (navigator.language || "en").toLowerCase();
  if (nav.startsWith("zh")) return /tw|hk|mo|hant/.test(nav) ? "zh-Hant" : "zh-Hans";
  return "en";
}

function App() {
  const [lang, setLang] = useState(initialLang);
  const [query, setQuery] = useState("");
  const [courses, setCourses] = useState([]);
  // What the list shows: everything, keyword results (GET /courses?q=), or the AI agent's tool results.
  const [view, setView] = useState({ kind: "all" });
  const [ai, setAi] = useState(null);
  const [loading, setLoading] = useState(false);
  const t = UI[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    try { localStorage.setItem("lang", lang); } catch (e) { /* ignore */ }
  }, [lang]);

  // Cards always come from GET /courses in the current language; for AI answers, only the activities the
  // agent's tools returned are kept, in the agent's order.
  useEffect(() => {
    let current = true;
    const params = new URLSearchParams({ lang, q: view.kind === "keyword" ? view.q : "" });
    fetch(`/courses?${params}`)
      .then(res => res.json())
      .then(data => {
        if (!current) return;
        const list = Array.isArray(data) ? data : [];
        if (view.kind !== "ai") return setCourses(list);
        const byId = Object.fromEntries(list.map(c => [c.id, c]));
        setCourses(view.cards.map(c => byId[c.id] || c));
      });
    return () => { current = false; };
  }, [lang, view]);

  const keywordSearch = text => {
    setAi(null);
    setView(text.trim() ? { kind: "keyword", q: text.trim() } : { kind: "all" });
  };

  // The one input: the local AI agent answers; if it is turned off or unreachable, the same text runs the
  // existing keyword search instead.
  const ask = e => {
    e.preventDefault();
    const text = query.trim();
    if (!text) return keywordSearch("");
    setLoading(true);
    setAi(null);
    fetch("/agent/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, lang }),
    })
      .then(res => res.json())
      .catch(err => ({ agent_status: "error", error: String(err), activities: [], tools_used: [] }))
      .then(result => {
        if (["disabled", "unavailable", "error"].includes(result.agent_status)) {
          setAi({ ...result, fallback: true });
          setView({ kind: "keyword", q: text });
        } else {
          setAi(result);
          setView({ kind: "ai", cards: result.activities || [] });
        }
      })
      .finally(() => setLoading(false));
  };

  const field = value => value || <em>{t.notPublished}</em>;

  return (
    <div style={{ padding: 16, maxWidth: 860, margin: "0 auto", fontFamily: FONT_STACK, lineHeight: 1.5 }}>
      <h1>{t.title}</h1>
      <form onSubmit={ask} style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <input value={query} placeholder={t.search} aria-label={t.search} maxLength={500}
               onChange={e => { setQuery(e.target.value); if (!e.target.value.trim()) keywordSearch(""); }}
               style={{ flex: "1 1 240px", padding: 8, fontSize: 16 }} />
        <button type="submit" disabled={loading} style={{ padding: "8px 16px", fontSize: 16 }}>{t.ask}</button>
        <button type="button" disabled={loading} onClick={() => keywordSearch(query)}
                style={{ padding: "8px 16px", fontSize: 16 }}>{t.keyword}</button>
        <label>
          {t.lang}{" "}
          <select value={lang} onChange={e => setLang(e.target.value)} style={{ padding: 8, fontSize: 16 }}>
            <option value="en">English</option>
            <option value="zh-Hans">简体中文</option>
            <option value="zh-Hant">繁體中文</option>
          </select>
        </label>
      </form>
      <Assistant lang={lang} result={ai} loading={loading} />
      {courses.length === 0 && <p>{t.none}</p>}
      {courses.map(c => {
        const shown = c.display || { name: c.title, kind: "original" };
        return (
          <div key={c.id || c.link} style={{ borderBottom: "1px solid #ddd", padding: "12px 0", overflowWrap: "anywhere" }}>
            <a href={c.link} target="_blank" rel="noopener noreferrer" lang={shown.language || undefined}>
              <strong>{shown.name}</strong>
            </a>
            {shown.kind !== "original" && (
              <span style={{ marginLeft: 8, fontSize: 12, color: "#666" }}>({t.kind[shown.kind] || shown.kind})</span>
            )}
            <div style={{ fontSize: 14 }}>
              {c.provider} · {t.ages}: {field(c.age_text)} · {t.dates}: {field(c.start_date)}
              {c.end_date && c.end_date !== c.start_date ? ` – ${c.end_date}` : ""} · {t.price}: {field(c.price)}
            </div>
            {shown.kind !== "original" && (
              <details style={{ fontSize: 14 }}>
                <summary>{t.original}</summary>
                <div lang={c.original_language || undefined}>
                  <div>{c.name}</div>
                  {c.description && <div style={{ color: "#444" }}>{c.description}</div>}
                  <a href={c.detail_url || c.source_url} target="_blank" rel="noopener noreferrer">{t.source}</a>
                </div>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default App;

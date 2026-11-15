import React, { useEffect, useState } from "react";

// UI text only. Activity titles/descriptions come from the API exactly as published.
const UI = {
  en: {
    title: "Kids Activities", search: "Search (e.g. robotics, 机器人, 夏令营)", lang: "Language",
    original: "Original text", source: "Official page", notPublished: "Not published",
    ages: "Ages", dates: "Dates", price: "Price", none: "No matching activities.",
    kind: { provider: "From the provider's own page", manual: "Translation (human)",
            machine: "Machine translation", original_only: "Only available in the original language" },
  },
  "zh-Hans": {
    title: "儿童活动", search: "搜索（如：机器人、编程、summer camp）", lang: "语言",
    original: "原文", source: "官方页面", notPublished: "未公布",
    ages: "年龄", dates: "日期", price: "费用", none: "没有符合条件的活动。",
    kind: { provider: "来自机构的中文/英文页面", manual: "人工翻译",
            machine: "机器翻译", original_only: "仅有原文" },
  },
  "zh-Hant": {
    title: "兒童活動", search: "搜尋（如：機器人、程式設計、summer camp）", lang: "語言",
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
  const t = UI[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    try { localStorage.setItem("lang", lang); } catch (e) { /* ignore */ }
  }, [lang]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ lang, q: query });
      fetch(`/courses?${params}`)
        .then(res => res.json())
        .then(data => setCourses(Array.isArray(data) ? data : []));
    }, 250);
    return () => clearTimeout(timer);
  }, [lang, query]);

  const field = value => value || <em>{t.notPublished}</em>;

  return (
    <div style={{ padding: 16, maxWidth: 860, margin: "0 auto", fontFamily: FONT_STACK, lineHeight: 1.5 }}>
      <h1>{t.title}</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder={t.search}
               style={{ flex: "1 1 240px", padding: 8, fontSize: 16 }} />
        <label>
          {t.lang}{" "}
          <select value={lang} onChange={e => setLang(e.target.value)} style={{ padding: 8, fontSize: 16 }}>
            <option value="en">English</option>
            <option value="zh-Hans">简体中文</option>
            <option value="zh-Hant">繁體中文</option>
          </select>
        </label>
      </div>
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

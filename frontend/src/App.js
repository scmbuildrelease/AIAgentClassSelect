import React, { useCallback, useEffect, useState } from "react";
import Assistant from "./Assistant";
import Discover from "./Discover";
import Saved from "./Saved";
import Settings from "./Settings";
import { UI, initialLang } from "./i18n";
import { DEFAULT_PREFS, load, snapshot, store } from "./storage";

// Kids Activities: Discover (GET /courses), AI Assistant (POST /agent/chat), Saved and Settings.
// Phones get a bottom tab bar; wider screens get the same sections as a top bar. All API calls are
// same-origin (the frontend server proxies them to the backend), so the app works from any host name.
const TABS = [
  { key: "discover", icon: "⌕" }, { key: "assistant", icon: "✦" },
  { key: "saved", icon: "★" }, { key: "settings", icon: "⚙" },
];

function App() {
  const [lang, setLang] = useState(() => initialLang(load("lang", null)));
  const [tab, setTab] = useState(() => (TABS.some(x => x.key === load("tab", "")) ? load("tab", "") : "discover"));
  const [prefs, setPrefs] = useState(() => ({ ...DEFAULT_PREFS, ...load("prefs", {}) }));
  const [saved, setSaved] = useState(() => load("saved", []));
  const [messages, setMessages] = useState([]);
  const [options, setOptions] = useState({ categories: {}, cities: [] });
  const t = UI[lang];

  useEffect(() => { document.documentElement.lang = lang; store("lang", lang); }, [lang]);
  useEffect(() => store("tab", tab), [tab]);
  useEffect(() => store("prefs", prefs), [prefs]);
  useEffect(() => store("saved", saved), [saved]);
  useEffect(() => {
    fetch("/options").then(res => res.json()).then(o => o && o.categories && setOptions(o)).catch(() => {});
  }, []);

  const savedIds = new Set(saved.map(s => s.id));
  const toggleSave = useCallback(c => setSaved(list => (
    list.some(s => s.id === c.id) ? list.filter(s => s.id !== c.id) : [snapshot(c), ...list])), []);

  const nav = (
    TABS.map(({ key, icon }) => (
      <button type="button" key={key} className={`tab${tab === key ? " on" : ""}`}
              aria-current={tab === key ? "page" : undefined} onClick={() => setTab(key)}>
        <span className="icon" aria-hidden="true">{icon}</span>
        <span className="tab-label">{t.tabs[key]}{key === "saved" && saved.length ? ` (${saved.length})` : ""}</span>
      </button>
    ))
  );

  return (
    <div className="app">
      <header className="topbar">
        <h1>{t.title}</h1>
        <nav className="topnav" aria-label={t.title}>{nav}</nav>
      </header>
      <main className="content">
        <div hidden={tab !== "discover"}>
          <Discover lang={lang} t={t} prefs={prefs} options={options} savedIds={savedIds}
                    onToggleSave={toggleSave} />
        </div>
        <div hidden={tab !== "assistant"}>
          <Assistant lang={lang} t={t} messages={messages} setMessages={setMessages} savedIds={savedIds}
                     onToggleSave={toggleSave} />
        </div>
        <div hidden={tab !== "saved"}>
          <Saved lang={lang} t={t} saved={saved} onToggleSave={toggleSave} />
        </div>
        <div hidden={tab !== "settings"}>
          <Settings lang={lang} setLang={setLang} t={t} prefs={prefs} setPrefs={setPrefs} options={options}
                    savedCount={saved.length} onClearSaved={() => setSaved([])} />
        </div>
      </main>
      <nav className="tabbar" aria-label={t.title}>{nav}</nav>
    </div>
  );
}

export default App;

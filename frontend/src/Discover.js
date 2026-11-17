import React, { useEffect, useState } from "react";
import ActivityCard from "./ActivityCard";
import { categoryLabel } from "./i18n";

const PAGE = 30;
const AGES = Array.from({ length: 16 }, (_, i) => i + 3);  // 3..18
const EMPTY = { age: "", city: "", category: "", from: "", to: "" };

// Search and filter the tracked activities (GET /courses). Filters start from the Settings preferences.
function Discover({ lang, t, prefs, options, savedIds, onToggleSave }) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ ...EMPTY, age: prefs.age || "", city: prefs.city || "" });
  const [state, setState] = useState({ status: "loading", items: [], error: null });
  const [limit, setLimit] = useState(PAGE);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let current = true;
    setState(s => ({ ...s, status: "loading", error: null }));
    const params = new URLSearchParams({ lang, q: query });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    fetch(`/courses?${params}`)
      .then(res => res.json().then(body => ({ ok: res.ok, body })))
      .then(({ ok, body }) => {
        if (!current) return;
        if (!ok || !Array.isArray(body)) throw new Error((body && body.error) || "unexpected response");
        setState({ status: "ok", items: body, error: null });
        setLimit(PAGE);
      })
      .catch(err => current && setState({ status: "error", items: [], error: String(err.message || err) }));
    return () => { current = false; };
  }, [lang, query, filters, reload]);

  // Settings changes (child's age, preferred city) become the new default filters.
  useEffect(() => {
    setFilters(f => (f.age === (prefs.age || "") && f.city === (prefs.city || "") ? f
      : { ...f, age: prefs.age || "", city: prefs.city || "" }));
  }, [prefs.age, prefs.city]);

  const set = (key, value) => setFilters(f => ({ ...f, [key]: value }));
  const active = Object.values(filters).some(Boolean);
  const favorites = prefs.categories || [];
  const categoryKeys = [...favorites, ...Object.keys(options.categories || {}).filter(k => !favorites.includes(k))];

  return (
    <section aria-labelledby="discover-title">
      <h2 id="discover-title" className="visually-hidden">{t.tabs.discover}</h2>
      <form className="searchbar" role="search" onSubmit={e => { e.preventDefault(); setQuery(text.trim()); }}>
        <input type="search" value={text} onChange={e => { setText(e.target.value); if (!e.target.value) setQuery(""); }}
               placeholder={t.search} aria-label={t.search} enterKeyHint="search" autoComplete="off"
               autoCorrect="off" maxLength={200} />
        <button type="submit" className="primary">{t.searchButton}</button>
      </form>

      <div className="chips" role="group" aria-label={t.category}>
        <button type="button" className={`chip${filters.category ? "" : " on"}`} aria-pressed={!filters.category}
                onClick={() => set("category", "")}>{t.anyCategory}</button>
        {categoryKeys.map(k => (
          <button type="button" key={k} className={`chip${filters.category === k ? " on" : ""}`}
                  aria-pressed={filters.category === k} onClick={() => set("category", filters.category === k ? "" : k)}>
            {categoryLabel(k, options.categories[k], lang)}
          </button>
        ))}
      </div>

      <details className="filters">
        <summary>{t.filters}{active ? " •" : ""}</summary>
        <div className="filter-grid">
          <label>{t.age}
            <select value={filters.age} onChange={e => set("age", e.target.value)}>
              <option value="">{t.anyAge}</option>
              {AGES.map(a => <option key={a} value={a}>{t.ageN(a)}</option>)}
            </select>
          </label>
          <label>{t.city}
            <select value={filters.city} onChange={e => set("city", e.target.value)}>
              <option value="">{t.anyCity}</option>
              {(options.cities || []).map(c => <option key={c.name} value={c.name}>{c.name} ({c.count})</option>)}
            </select>
          </label>
          <label>{t.from}
            <input type="date" value={filters.from} onChange={e => set("from", e.target.value)} />
          </label>
          <label>{t.to}
            <input type="date" value={filters.to} min={filters.from || undefined}
                   onChange={e => set("to", e.target.value)} />
          </label>
        </div>
        {active && <button type="button" className="link-button" onClick={() => setFilters(EMPTY)}>{t.clear}</button>}
      </details>

      <div aria-live="polite">
        {state.status === "loading" && <p className="status">{t.loading}</p>}
        {state.status === "error" && (
          <div className="banner error" role="alert">
            {t.error}: {state.error}{" "}
            <button type="button" className="link-button" onClick={() => setReload(n => n + 1)}>{t.retry}</button>
          </div>
        )}
        {state.status === "ok" && (
          <p className="status">{state.items.length ? t.results(state.items.length) : t.none}</p>
        )}
      </div>
      <div className="cards">
        {state.items.slice(0, limit).map(c => (
          <ActivityCard key={c.id || c.link} c={c} t={t} saved={savedIds.has(c.id)} onToggleSave={onToggleSave} />
        ))}
      </div>
      {state.status === "ok" && state.items.length > limit && (
        <button type="button" className="secondary wide" onClick={() => setLimit(n => n + PAGE)}>
          {t.showMore} ({state.items.length - limit})
        </button>
      )}
    </section>
  );
}

export default Discover;

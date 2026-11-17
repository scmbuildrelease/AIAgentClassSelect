import React, { useCallback, useEffect, useState } from "react";
import { LANGS, categoryLabel } from "./i18n";

const AGES = Array.from({ length: 16 }, (_, i) => i + 3);

function StatusRow({ label, state, detail, t }) {
  const text = { ok: t.ok, unavailable: t.unavailable, off: t.off, checking: t.checking }[state] || state;
  return (
    <div className="status-row">
      <span>{label}</span>
      <span className={`pill ${state}`}>{text}</span>
      {detail && <div className="detail">{detail}</div>}
    </div>
  );
}

// Language, preferences (this browser) and live status from GET /health.
function Settings({ lang, setLang, t, prefs, setPrefs, options, savedCount, onClearSaved }) {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  const check = useCallback(() => {
    setHealth(null);
    setError(null);
    fetch("/health")
      .then(res => res.json())
      .then(setHealth)
      .catch(err => setError(String(err.message || err)));
  }, []);
  useEffect(check, [check]);

  const toggleCategory = k => setPrefs(p => ({
    ...p, categories: p.categories.includes(k) ? p.categories.filter(x => x !== k) : [...p.categories, k] }));
  const ai = health && health.ai;
  const aiState = !health ? "checking" : !ai.enabled ? "off" : ai.ollama === "ok" ? "ok" : "unavailable";

  return (
    <section aria-labelledby="settings-title">
      <h2 id="settings-title" className="section-title">{t.tabs.settings}</h2>

      <div className="group">
        <label className="row">{t.language}
          <select value={lang} onChange={e => setLang(e.target.value)}>
            {Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>

      <h3 className="group-title">{t.preferences}</h3>
      <div className="group">
        <label className="row">{t.childAge}
          <select value={prefs.age} onChange={e => setPrefs(p => ({ ...p, age: e.target.value }))}>
            <option value="">{t.anyAge}</option>
            {AGES.map(a => <option key={a} value={a}>{t.ageN(a)}</option>)}
          </select>
        </label>
        <label className="row">{t.preferredCity}
          <select value={prefs.city} onChange={e => setPrefs(p => ({ ...p, city: e.target.value }))}>
            <option value="">{t.anyCity}</option>
            {(options.cities || []).map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <div className="row column">
          <span>{t.categories}</span>
          <div className="chips wrap">
            {Object.keys(options.categories || {}).map(k => (
              <button type="button" key={k} className={`chip${prefs.categories.includes(k) ? " on" : ""}`}
                      aria-pressed={prefs.categories.includes(k)} onClick={() => toggleCategory(k)}>
                {categoryLabel(k, options.categories[k], lang)}
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className="hint">{t.prefsNote}</p>

      <h3 className="group-title">{t.status}</h3>
      <div className="group" aria-live="polite">
        {error && <div className="banner error" role="alert">{t.backend}: {error}</div>}
        <StatusRow t={t} label={t.backend} state={error ? "unavailable" : health ? "ok" : "checking"} />
        <StatusRow t={t} label={t.data} state={!health ? "checking" : health.data.available ? "ok" : "unavailable"}
                   detail={health && (health.data.available
                     ? t.activitiesN(health.data.activities, (health.data.last_checked || "").slice(0, 10))
                     : health.data.error)} />
        <StatusRow t={t} label={t.aiAgent} state={!health ? "checking" : ai.enabled ? "ok" : "off"}
                   detail={ai && ai.enabled ? ai.model : null} />
        <StatusRow t={t} label={t.ollama} state={aiState} detail={ai && ai.error} />
        <button type="button" className="secondary" onClick={check}>{t.refresh}</button>
      </div>

      <h3 className="group-title">{t.privacy}</h3>
      <div className="group">
        <p className="hint">{t.privacyNote}</p>
        {savedCount > 0 && <button type="button" className="secondary danger" onClick={onClearSaved}>
          {t.clearSaved} ({savedCount})</button>}
      </div>
    </section>
  );
}

export default Settings;

import React, { useEffect, useState } from "react";
import ActivityCard from "./ActivityCard";

// Saved activities (this browser only). Shows the current published version when the activity is still
// tracked (GET /courses?all=1), otherwise the snapshot taken when it was saved.
function Saved({ lang, t, saved, onToggleSave }) {
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    let live = true;
    if (!saved.length) return undefined;
    fetch(`/courses?${new URLSearchParams({ lang, all: "1" })}`)
      .then(res => res.json())
      .then(data => live && Array.isArray(data) && setCurrent(Object.fromEntries(data.map(c => [c.id, c]))))
      .catch(() => live && setCurrent(null));
    return () => { live = false; };
  }, [lang, saved.length]);

  const savedIds = new Set(saved.map(s => s.id));
  return (
    <section aria-labelledby="saved-title">
      <h2 id="saved-title" className="section-title">{t.tabs.saved}</h2>
      <p className="hint">{t.savedNote}</p>
      {saved.length === 0 && <p className="empty">{t.savedEmpty}</p>}
      <div className="cards">
        {saved.map(s => {
          const live = current && current[s.id];
          const past = live && live.lifecycle === "PAST";
          return (
            <ActivityCard key={s.id} c={live || s} t={t} saved={savedIds.has(s.id)} onToggleSave={onToggleSave}
                          note={[current && (!live || past) ? t.noLongerListed : null,
                                 t.savedOn(s.savedAt.slice(0, 10))].filter(Boolean).join(" · ")} />
          );
        })}
      </div>
    </section>
  );
}

export default Saved;

import React from "react";

// One activity, as published by its source. Missing values say "Not published"; nothing is filled in.
// Links are only rendered for http(s) URLs: the extractor already drops other schemes, and this also covers
// snapshots kept in browser storage.
const safeLink = url => (typeof url === "string" && /^https?:\/\//i.test(url) ? url : null);

function dates(c, t) {
  if (c.start_date) return c.end_date && c.end_date !== c.start_date ? `${c.start_date} – ${c.end_date}` : c.start_date;
  const sessions = c.sessions || [];
  if (!sessions.length) return null;
  return sessions.length > 1 ? `${sessions[0]} (${t.more(sessions.length - 1)})` : sessions[0];
}

function ActivityCard({ c, t, saved, onToggleSave, note }) {
  const shown = c.display || { name: c.title || c.name, kind: "original" };
  const field = value => value || <em className="muted">{t.notPublished}</em>;
  const place = c.location || c.city;
  const link = safeLink(c.link);

  return (
    <article className="card">
      <div className="card-head">
        {link ? <a className="card-title" href={link} target="_blank" rel="noopener noreferrer"
                   lang={shown.language || undefined}>{shown.name}</a>
              : <span className="card-title" lang={shown.language || undefined}>{shown.name}</span>}
        {onToggleSave && (
          <button type="button" className={`save${saved ? " on" : ""}`} aria-pressed={!!saved}
                  aria-label={saved ? t.unsave : t.save} onClick={() => onToggleSave(c)}>
            <span aria-hidden="true">{saved ? "★" : "☆"}</span> {saved ? t.saved : t.save}
          </button>
        )}
      </div>
      {shown.kind && shown.kind !== "original" && <div className="kind">{t.kind[shown.kind] || shown.kind}</div>}
      <div className="provider">{c.provider}</div>
      <dl className="facts">
        <div><dt>{t.ages}</dt><dd>{field(c.age_text)}</dd></div>
        <div><dt>{t.dates}</dt><dd>{field(dates(c, t))}</dd></div>
        <div><dt>{t.price}</dt><dd>{field(c.price)}</dd></div>
        <div><dt>{t.where}</dt><dd>{field(place)}</dd></div>
        {c.organizer && <div><dt>{t.organizer}</dt><dd>{c.organizer}</dd></div>}
      </dl>
      {note && <p className="note">{note}</p>}
      {shown.kind && shown.kind !== "original" && (
        <details className="original">
          <summary>{t.original}</summary>
          <div lang={c.original_language || undefined}>
            <div>{c.name}</div>
            {c.description && <div className="muted">{c.description}</div>}
          </div>
        </details>
      )}
      {link && <a className="source" href={link} target="_blank" rel="noopener noreferrer">{t.source} ↗</a>}
    </article>
  );
}

export default ActivityCard;

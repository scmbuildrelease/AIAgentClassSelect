// Per-browser storage for saved activities and preferences. Nothing here is sent to the backend.
// Private browsing or blocked storage makes reads return the fallback and writes do nothing.
const PREFIX = "aiacs.";

export function load(key, fallback) {
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (e) {
    return fallback;
  }
}

export function store(key, value) {
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch (e) { /* storage unavailable: keep working without persistence */ }
}

export const DEFAULT_PREFS = { age: "", city: "", categories: [] };

// A saved activity keeps a snapshot of what was shown, so it still displays if it later leaves the list.
export function snapshot(c) {
  return {
    id: c.id, name: c.name, display: c.display, provider: c.provider, organizer: c.organizer,
    city: c.city, location: c.location, age_text: c.age_text, start_date: c.start_date, end_date: c.end_date,
    sessions: (c.sessions || []).slice(0, 3), price: c.price, link: c.link, savedAt: new Date().toISOString(),
  };
}

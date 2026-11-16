"""Markdown report for $GITHUB_STEP_SUMMARY and the downloadable artifact.

All scraped text is untrusted: cell() escapes Markdown/HTML, link() only links http(s) URLs.
"""
import re

from . import NOT_PUBLISHED
from .config import AGGREGATOR
from .i18n import lang_group
from .tracker import NEW, UPDATED, UNCHANGED, NOT_FOUND, FETCH_FAILED

STATUS_ICON = {NEW: "🆕 NEW", UPDATED: "✏️ UPDATED", UNCHANGED: "✅ UNCHANGED",
               NOT_FOUND: "❔ NOT_FOUND", FETCH_FAILED: "⚠️ NOT VERIFIED"}
FIELD_LABELS = {"name": "Name", "age_text": "Ages", "location": "Location", "schedule": "Schedule",
                "sessions": "Sessions", "start_date": "Start", "end_date": "End", "price": "Price",
                "enrollment_status": "Enrollment", "description": "Description"}


def cell(value, limit: int = 120) -> str:
    if value in (None, "", []):
        return f"_{NOT_PUBLISHED}_"
    if isinstance(value, list):
        value = "; ".join(map(str, value))
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([|\\`*_\[\]])", r"\\\1", text)


def link(text, url) -> str:
    label = cell(text, 80)
    url = (url or "").strip()
    if not re.match(r"https?://[^\s<>\"'()]+$", url):
        return label  # never link javascript:, data: or malformed URLs from scraped pages
    return f"[{label}]({url})"


def age_matches(rec: dict, min_age: int, max_age: int) -> bool:
    lo, hi = rec.get("age_min"), rec.get("age_max")
    if lo is None and hi is None:
        # an aggregator's age group (e.g. preschool 0–5) can rule an event out, never confirm it fits
        g_lo, g_hi = rec.get("age_group_min"), rec.get("age_group_max")
        if g_lo is not None and g_hi is not None:
            return g_lo <= max_age and g_hi >= min_age
        return True  # unknown ages are shown, flagged as not published
    return (lo if lo is not None else 0) <= max_age and (hi if hi is not None else 99) >= min_age


def ages(rec: dict) -> str:
    groups = " " + cell("(listed under: " + "; ".join(rec["age_groups"]) + ")") if rec.get("age_groups") else ""
    if not rec.get("age_text"):
        return f"_{NOT_PUBLISHED}_" + groups
    return cell(rec["age_text"]) + (" (grades)" if rec.get("age_basis") == "grade" else "") + groups


def dates(rec: dict) -> str:
    s, e = rec.get("start_date"), rec.get("end_date")
    if not s and not e:
        return f"_{NOT_PUBLISHED}_"
    return cell(s if s == e or not e else f"{s} → {e}")


def activity_cell(rec: dict) -> str:
    """Original title (as published) plus any other-language title, labelled by where it came from."""
    marker = "" if rec.get("extraction") in ("listing", "json-ld", "aggregator") else " †"
    out = link(rec.get("name"), rec.get("detail_url") or rec.get("source_url")) + marker
    if rec.get("campus"):
        out += f" · campus: {cell(rec['campus'], 40)}"
    if rec.get("extraction") == "aggregator":
        out += (f"<br>📋 listed by {link('aggregator', rec.get('aggregator_url'))}; organizer: "
                f"{link(rec.get('organizer') or NOT_PUBLISHED, rec.get('original_event_url'))} "
                f"_(not confirmed by the organizer; {RECURRENCE.get(rec.get('recurrence') or '', 'unknown')})_")
    own = lang_group(rec.get("original_language"))
    for lang, tr in sorted((rec.get("translations") or {}).items()):
        if lang != own and tr.get("name"):
            label = {"machine": "machine translation", "manual": "translation"}.get(tr.get("method"), "provider")
            out += f"<br>🌐 {cell(tr['name'], 80)} _({label})_"
    return out


def category_labels(rec: dict, categories: dict) -> str:
    return ", ".join(categories.get(c, {}).get("short") or categories.get(c, {}).get("label", c)
                     for c in rec.get("categories", []))


def activity_table(recs: list[dict], categories: dict, max_rows: int, with_status=False) -> list[str]:
    head = ["Activity", "Provider", "Category", "Ages", "Dates", "Schedule", "Price", "Enrollment", "Location"]
    if with_status:
        head.insert(0, "Status")
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in recs[:max_rows]:
        row = [activity_cell(r), link(r.get("provider"), r.get("source_url")), cell(category_labels(r, categories)),
               ages(r), dates(r), cell(r.get("schedule")), cell(r.get("price")), cell(r.get("enrollment_status")),
               cell(r.get("location"), 80)]
        if with_status:
            row.insert(0, STATUS_ICON.get(r.get("status"), r.get("status", "")))
        lines.append("| " + " | ".join(row) + " |")
    if len(recs) > max_rows:
        lines.append(f"\n_…{len(recs) - max_rows} more rows in the downloadable report artifact / data/courses.json._")
    return lines


RECURRENCE = {"one_time": "one-time", "multiple_sessions": "several sessions"}
SOURCE_TYPE_LABELS = {"activity_provider": "Activity provider", "education_provider": "Education provider",
                      "community_education_provider": "Community education provider",
                      AGGREGATOR: "Community activity aggregator"}


def source_overview(src: list[dict], store: dict, categories: dict) -> list[str]:
    """Per-source type, language, area and extraction status; organization pages vs. activity records."""
    typed = [s for s in src if not s.get("seed")]
    if not typed:
        return []
    out = ["## 📚 Sources by type", "",
           "_Organization pages are checked to verify the source; they never become activity records. "
           "Aggregator events are listings by a third party, not confirmation by the organizer._", "",
           "| Source | Type | Language | Location / scope | Status | Organization pages | Activity records "
           "| Excluded (outside Bay Area) |", "|---|---|---|---|---|---|---|---|"]
    for s in typed:
        recs = [r for r in store.values() if r["source_id"] == s["id"]]
        kinds: dict[str, int] = {}
        for r in recs:
            kinds[r.get("record_type") or "program"] = kinds.get(r.get("record_type") or "program", 0) + 1
        org_pages = ", ".join("{} ({})".format(p["url"].split("://")[-1], p["status"])
                              for p in s.get("pages", []) if p["role"] == "organization") or "—"
        counts = ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items())) or "0"
        excluded = "; ".join("{} ({})".format(e["name"], e.get("location") or "no location published")
                             for e in s.get("excluded") or []) or "—"
        kind = SOURCE_TYPE_LABELS.get(s.get("source_type") or "", s.get("source_type") or "")
        out.append(f"| {link(s['provider'], s['url'])} | {kind} | {cell('/'.join(s.get('language') or []))} "
                   f"| {cell(s.get('locations'), 80)} | `{s['status']}` | {cell(org_pages, 160)} | {cell(counts)} "
                   f"| {cell(excluded, 200)} |")
    return out + [""]


def _sort_key(r):
    return (r.get("provider") or "", r.get("start_date") or "9999", r.get("name") or "")


def build_report(run: dict, config, max_rows: int | None = None) -> str:
    p = run["params"]
    categories = config.categories
    max_rows = max_rows or config.settings.get("report", {}).get("max_rows_per_table", 75)
    store = run["courses"]["courses"]
    processed = set(run["processed_source_ids"])
    selected = set(p["categories"])

    # cross-language duplicates are shown once, under the primary record (see search.link_language_variants)
    in_scope = [r for r in store.values() if selected & set(r.get("categories", [])) and not r.get("duplicate_of")]
    shown = sorted((r for r in in_scope if age_matches(r, p["min_age"], p["max_age"])), key=_sort_key)
    outside_age = len(in_scope) - len(shown)
    checked = [r for r in shown if r["source_id"] in processed]
    by_status = {s: [r for r in checked if r.get("status") == s] for s in STATUS_ICON}
    changes = {e["id"]: e.get("changes", []) for e in run["events"] if e["status"] == UPDATED}

    src = run["source_results"]
    failed = [s for s in src if s["status"] not in ("OK", "MANUAL", "PENDING_VERIFICATION")]
    manual = [s for s in src if s["status"] == "MANUAL"]

    out = ["# 🧭 Kids Activity Discovery Report", ""]
    if run.get("is_baseline"):
        out += ["> [!NOTE]", "> **Initial baseline run.** Every activity found is marked NEW. "
                "Later runs will compare against this baseline.", ""]
    if not run.get("saved", True):
        out += ["> [!CAUTION]", f"> **Data was NOT saved:** {run.get('not_saved_reason')}. "
                "Existing history was left untouched.", ""]
    out += [
        f"**Run:** {run['run_at']} · **Mode:** `{p['mode']}` · **Ages:** {p['min_age']}–{p['max_age']} · "
        f"**Categories:** {'all' if set(p['categories']) == set(categories) else ', '.join(p['categories'])}",
        "",
        "## Summary", "",
        "| Sources checked | Sources failed | Manual-check sources | Activities in scope | 🆕 New | ✏️ Updated "
        "| ✅ Unchanged | ❔ Not found | ⚠️ Not verified |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| {len(src) - len(manual)} | {len(failed)} | {len(manual)} | {len(shown)} | {len(by_status[NEW])} "
        f"| {len(by_status[UPDATED])} | {len(by_status[UNCHANGED])} | {len(by_status[NOT_FOUND])} "
        f"| {len(by_status[FETCH_FAILED])} |",
        "",
        f"_Ages filter: activities with no published age are included and labelled \"{NOT_PUBLISHED}\"; "
        f"{outside_age} tracked activities fall outside {p['min_age']}–{p['max_age']} and are hidden._",
        "",
        "**How to read this:** all values are copied from the official pages linked. "
        f"\"{NOT_PUBLISHED}\" means the page did not state it. "
        "Rows marked **†** are program-level records whose fields were found by text patterns on the page — "
        "confirm details on the official page before enrolling. Unmarked rows come from structured listings.",
        "",
    ]

    if p["mode"] != "discover_new_sources":
        out += [f"## 🆕 New activities ({len(by_status[NEW])})", ""]
        out += activity_table(by_status[NEW], categories, max_rows) if by_status[NEW] else ["_None this run._"]
        out += ["", f"## ✏️ Updated activities ({len(by_status[UPDATED])})", ""]
        if by_status[UPDATED]:
            out += ["| Activity | Provider | Field | Old → New |", "|---|---|---|---|"]
            for r in by_status[UPDATED][:max_rows]:
                for ch in changes.get(r["id"], []):
                    out.append(f"| {activity_cell(r)} | {cell(r.get('provider'))} | "
                               f"{FIELD_LABELS.get(ch['field'], ch['field'])} | "
                               f"{cell(ch['old'], 80)} → **{cell(ch['new'], 80)}** |")
        else:
            out.append("_None this run._")

        seasonal = [r for r in checked if r.get("program_type") in ("camp", "seasonal_program") or r.get("season")]
        out += ["", f"## 🏕️ Camps & seasonal programs ({len(seasonal)})", ""]
        seasonal.sort(key=lambda r: (r.get("season") or "zz", r.get("start_date") or "9999", r.get("name") or ""))
        out += activity_table(seasonal, categories, max_rows, with_status=True) if seasonal else ["_None found._"]

        out += ["", "<details><summary><b>✅ Unchanged activities "
                f"({len(by_status[UNCHANGED])})</b> — previously known, re-checked this run</summary>", ""]
        out += activity_table(by_status[UNCHANGED], categories, max_rows) if by_status[UNCHANGED] else ["_None._"]
        out += ["", "</details>", ""]

        out += [f"## ❔ Not found this run ({len(by_status[NOT_FOUND])})", "",
                "_Source page was read successfully but these activities were no longer listed. "
                "Kept in history; they may have ended or been renamed._", ""]
        if by_status[NOT_FOUND]:
            out += ["| Activity | Provider | Last seen | Missing since |", "|---|---|---|---|"]
            out += [f"| {activity_cell(r)} | {cell(r.get('provider'))} | {r.get('last_seen')} | "
                    f"{r.get('missing_since')} |" for r in by_status[NOT_FOUND][:max_rows]]
        else:
            out.append("_None._")
        out.append("")

    out += source_overview(src, store, categories)
    out += [f"## ⚠️ Sources that failed or need manual verification ({len(failed) + len(manual)})", ""]
    if failed:
        out += ["| Source | Status | Detail | Last successful fetch | Activities kept (not re-verified) |",
                "|---|---|---|---|---|"]
        for s in failed:
            out.append(f"| {link(s['provider'], s['url'])} | `{s['status']}` | {cell(s.get('error'))} | "
                       f"{s.get('last_success_at') or 'never'} | {s.get('kept_records', 0)} |")
        out.append("")
        out.append("_A failed source does **not** mean it has no classes — its previous records are kept "
                   "and marked not verified._")
        out.append("")
    if manual:
        out += ["**Check these manually** (sites block automated access or render listings with JavaScript):", "",
                "| Source | Category | Why manual |", "|---|---|---|"]
        for s in manual:
            out.append(f"| {link(s['provider'], s['url'])} | {cell(', '.join(categories[c]['label'] for c in s['categories']))} "
                       f"| {cell(s.get('notes'))} |")
        out.append("")
    pending = [s for s in src if s["status"] == "PENDING_VERIFICATION"]
    if pending:
        out += ["**Pending verification** (configured but not fetched until marked VERIFIED):", ""]
        out += [f"- {link(s['provider'], s['url'])}" for s in pending] + [""]
    if not failed and not manual:
        out += ["_All sources fetched successfully._", ""]

    if p["mode"] in ("discover_new_sources", "both"):
        cands = run.get("new_candidates", [])
        out += [f"## 🔎 New candidate source pages ({len(cands)})", "",
                "_Links found on known provider sites that look like kids' programs. Not verified and not tracked "
                "yet — to track one, add it to `config/sources.json`._", ""]
        if cands:
            out += ["| Page | Link text | Suggested categories | Found on |", "|---|---|---|---|"]
            for c in cands[:max_rows]:
                out.append(f"| {link(c['url'], c['url'])} | {cell(c.get('anchor_text'), 60)} | "
                           f"{cell(', '.join(c.get('suggested_categories', [])))} | {link('page', c['found_on'])} |")
        else:
            out.append("_No new candidates._")
        out.append("")

    return "\n".join(out).rstrip() + "\n"

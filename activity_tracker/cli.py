"""Command-line entry point: python -m activity_tracker [options]."""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_config, parse_category_filter
from .discovery import find_candidates, merge_candidates
from .extract import extract
from .fetcher import Fetcher, FixtureFetcher
from .report import build_report
from .tracker import Store, assign_ids, merge_source, normalize_url, update_source_state

log = logging.getLogger("activity_tracker")
MODES = ("refresh_known_sources", "discover_new_sources", "both")
STEP_SUMMARY_LIMIT = 1_000_000  # GitHub caps each step summary at 1 MiB


def run_discovery(config, store: Store, fetcher, params: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    now_s, today = now.strftime("%Y-%m-%dT%H:%M:%SZ"), now.date().isoformat()
    mode = params["mode"]
    refresh, discover = mode in ("refresh_known_sources", "both"), mode in ("discover_new_sources", "both")
    sources_state, courses, candidates = store.load()
    is_baseline = refresh and not courses["courses"]
    selected = set(params["categories"])

    source_results, events, new_candidates, processed = [], [], [], []
    known_urls = {normalize_url(s.url) for s in config.sources}
    known_urls |= {normalize_url(s["url"]) for s in config.discovery_seeds}
    known_urls |= {normalize_url(c.get("detail_url")) for c in courses["courses"].values()}

    for source in config.sources:
        if not source.enabled or not selected & set(source.categories):
            continue
        base = {"id": source.id, "provider": source.provider, "url": source.url,
                "categories": source.categories, "notes": source.notes}
        if source.manual_only:
            source_results.append({**base, "status": "MANUAL"})
            continue
        log.info("fetching %s (%s)", source.id, source.url)
        result = fetcher.get(source.url)
        kept = sum(1 for c in courses["courses"].values() if c["source_id"] == source.id)
        entry = {**base, "status": "OK" if result.ok else ("BLOCKED_BY_ROBOTS"
                 if result.status == "BLOCKED_BY_ROBOTS" else "FETCH_FAILED"),
                 "http_status": result.http_status, "error": result.error, "kept_records": kept}
        if refresh:
            records = []
            if result.ok:
                try:
                    records = assign_ids(extract(result.html, source, result.final_url or source.url,
                                                 config.settings.get("cities", [])))
                except Exception as e:  # a parser bug on one site must not break the run
                    log.exception("extraction failed for %s", source.id)
                    entry["error"] = f"Extraction error: {type(e).__name__}: {e}"
            status = update_source_state(sources_state, source, result, now_s, len(records))
            entry["status"] = status
            entry["error"] = entry["error"] or sources_state["sources"][source.id].get("error")
            entry["last_success_at"] = sources_state["sources"][source.id].get("last_success_at")
            entry["items_found"] = len(records)
            known_urls |= {normalize_url(r.get("detail_url")) for r in records}
            events += merge_source(courses, source.id, status == "OK", records, today, now_s)
            processed.append(source.id)
        if discover and result.ok:
            found = find_candidates(result.html, source.url, config.settings, config.categories)
            new_candidates += merge_candidates(candidates, found, source.url, known_urls, today)
        source_results.append(entry)

    if discover:
        for seed in config.discovery_seeds:
            if not selected & set(seed.get("categories", list(config.categories))):
                continue
            result = fetcher.get(seed["url"])
            entry = {"id": f"seed:{seed['url']}", "provider": seed.get("provider", seed["url"]), "url": seed["url"],
                     "categories": seed.get("categories", []), "status": "OK" if result.ok else "FETCH_FAILED",
                     "http_status": result.http_status, "error": result.error, "seed": True}
            if result.ok:
                found = find_candidates(result.html, seed["url"], config.settings, config.categories)
                new_candidates += merge_candidates(candidates, found, seed["url"], known_urls, today)
            source_results.append(entry)

    attempted = [s for s in source_results if s["status"] != "MANUAL"]
    succeeded = [s for s in attempted if s["status"] == "OK"]
    saved, reason = True, None
    if attempted and not succeeded:
        saved, reason = False, f"all {len(attempted)} fetched sources failed or returned no activities"
    if saved:
        if refresh:
            meta = courses.setdefault("meta", {})
            meta.setdefault("baseline_created_at", now_s)
            meta["last_run_at"] = now_s
            meta["run_count"] = meta.get("run_count", 0) + 1
        store.save(sources_state, courses, candidates if discover else None)

    return {"run_at": now_s, "params": params, "is_baseline": is_baseline, "saved": saved,
            "not_saved_reason": reason, "source_results": source_results, "events": events,
            "processed_source_ids": processed, "courses": courses, "new_candidates": new_candidates}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discover and track kids' activities from configured sources.")
    ap.add_argument("--min-age", type=int, default=None)
    ap.add_argument("--max-age", type=int, default=None)
    ap.add_argument("--categories", default="all", help="'all' or comma-separated category keys")
    ap.add_argument("--mode", choices=MODES, default="refresh_known_sources")
    ap.add_argument("--config-dir", type=Path, default=Path("config"))
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--report", type=Path, default=Path("reports/report.md"))
    ap.add_argument("--summary", type=Path, default=None, help="also append the report here ($GITHUB_STEP_SUMMARY)")
    ap.add_argument("--fixtures", type=Path, default=None, help="offline mode: serve pages from a fixture dir")
    args = ap.parse_args(argv)
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)

    try:
        config = load_config(args.config_dir)
        cats = parse_category_filter(args.categories, config.categories)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    min_age = args.min_age if args.min_age is not None else config.settings.get("default_age_min", 7)
    max_age = args.max_age if args.max_age is not None else config.settings.get("default_age_max", 8)
    if not (0 <= min_age <= max_age <= 21):
        print(f"Invalid age range {min_age}-{max_age}", file=sys.stderr)
        return 1

    fetcher = FixtureFetcher(args.fixtures) if args.fixtures else Fetcher(config.settings)
    params = {"min_age": min_age, "max_age": max_age, "categories": cats, "mode": args.mode}
    run = run_discovery(config, Store(args.data_dir), fetcher, params)
    report = build_report(run, config)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    slim = {k: v for k, v in run.items() if k != "courses"}
    args.report.with_name("run_summary.json").write_text(json.dumps(slim, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.summary:
        text = report
        if len(text.encode()) > STEP_SUMMARY_LIMIT:
            text = text.encode()[: STEP_SUMMARY_LIMIT - 200].decode(errors="ignore") + \
                "\n\n_Report truncated — download the full report artifact._\n"
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(text)
    log.info("report written to %s (data saved: %s)", args.report, run["saved"])
    return 0 if run["saved"] else 2

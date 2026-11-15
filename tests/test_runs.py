"""End-to-end runs against offline fixtures: baseline, second run, failures, persistence, report."""
import json

from activity_tracker.cli import main
from activity_tracker.report import build_report
from activity_tracker.tracker import FETCH_FAILED, NEW, NOT_FOUND, UNCHANGED, UPDATED
from conftest import FIXTURES, RUN1, RUN2, by_name


def test_first_run_creates_baseline(run, tmp_path):
    r = run("site_v1")
    assert r["is_baseline"] and r["saved"]
    courses = by_name(r)
    assert set(courses) == {"Junior Robot Engineer", "Space Explorer", "Teen Game Design",
                            "Kids Painting Studio", "Beginning Ballet (Ages 7-8)", "Group Piano for Kids"}
    assert {c["status"] for c in courses.values()} == {NEW}
    saved = json.loads((tmp_path / "data/courses.json").read_text())
    assert len(saved["courses"]) == 6 and saved["meta"]["baseline_created_at"] == "2026-11-15T12:00:00Z"
    src = json.loads((tmp_path / "data/sources.json").read_text())["sources"]
    assert src["fx-art"]["status"] == "OK" and src["fx-art"]["last_success_at"] == "2026-11-15T12:00:00Z"
    assert "fx-city-rec" not in src  # manual sources are never fetched


def test_second_run_detects_new_updated_unchanged_missing_and_failed(run):
    run("site_v1", RUN1)
    r = run("site_v2", RUN2)
    assert not r["is_baseline"]
    c = by_name(r)
    assert c["Ocean Explorers"]["status"] == NEW
    assert c["Junior Robot Engineer"]["status"] == UPDATED
    assert c["Junior Robot Engineer"]["history"][-1]["changes"] == [{"field": "price", "old": "$500", "new": "$550"}]
    # cosmetic HTML / whitespace / dash / timestamp / tracking-param changes are not updates
    assert c["Teen Game Design"]["status"] == UNCHANGED
    assert c["Kids Painting Studio"]["status"] == UNCHANGED
    assert c["Beginning Ballet (Ages 7-8)"]["status"] == UNCHANGED
    assert c["Space Explorer"]["status"] == NOT_FOUND and c["Space Explorer"]["last_seen"] == "2026-11-15"
    piano = c["Group Piano for Kids"]
    assert piano["status"] == FETCH_FAILED and piano["verified"] is False
    assert piano["schedule"] == "Wednesdays 4:00pm - 4:45pm"  # old data preserved
    music = next(s for s in r["source_results"] if s["id"] == "fx-music")
    assert music["status"] == "FETCH_FAILED" and music["error"] == "HTTP 403" and music["kept_records"] == 1


def test_history_persists_across_runs_on_disk(run, tmp_path):
    run("site_v1", RUN1)
    run("site_v2", RUN2)
    saved = json.loads((tmp_path / "data/courses.json").read_text())
    assert saved["meta"]["run_count"] == 2
    robot = next(c for c in saved["courses"].values() if c["name"] == "Junior Robot Engineer")
    assert robot["first_seen"] == "2026-11-15" and robot["last_changed"] == "2027-01-05"
    # a third run with identical content: everything previously seen is UNCHANGED, nothing lost
    r3 = run("site_v2", RUN2.replace(day=12))
    statuses = {c["name"]: c["status"] for c in r3["courses"]["courses"].values()}
    assert statuses["Junior Robot Engineer"] == UNCHANGED and statuses["Ocean Explorers"] == UNCHANGED
    assert statuses["Space Explorer"] == NOT_FOUND and len(statuses) == 7


def test_all_sources_failing_never_overwrites_history(run, tmp_path):
    run("site_v1", RUN1)
    before = (tmp_path / "data/courses.json").read_text(), (tmp_path / "data/sources.json").read_text()
    r = run("site_down", RUN2)
    assert r["saved"] is False and "all 4 fetched sources failed" in r["not_saved_reason"]
    after = (tmp_path / "data/courses.json").read_text(), (tmp_path / "data/sources.json").read_text()
    assert before == after


def test_empty_extraction_keeps_records_and_flags_source(run, tmp_path):
    run("site_v1", RUN1)
    site = tmp_path / "site_empty"
    site.mkdir()
    manifest = json.loads((FIXTURES / "site_v2/manifest.json").read_text())
    for entry in manifest.values():
        if "file" in entry:
            (site / entry["file"]).write_text((FIXTURES / "site_v2" / entry["file"]).read_text())
    (site / "camps.html").write_text("<html><body><main><p>Loading camps…</p></main></body></html>")
    (site / "manifest.json").write_text(json.dumps(manifest))
    r = run(str(site), RUN2)
    camps = next(s for s in r["source_results"] if s["id"] == "fx-camps")
    assert camps["status"] == "EMPTY_RESULT"
    robot = by_name(r)["Junior Robot Engineer"]
    assert robot["status"] == FETCH_FAILED and robot["price"] == "$500"  # not NOT_FOUND, not deleted


def test_category_filter_only_fetches_matching_sources(run):
    r = run("site_v1", RUN1, categories=["arts"])
    assert [s["id"] for s in r["source_results"]] == ["fx-art", "fx-city-rec"]
    assert set(by_name(r)) == {"Kids Painting Studio"}


def test_discovery_mode_suggests_candidates_without_touching_courses(run, tmp_path):
    r = run("site_v1", RUN1, mode="discover_new_sources")
    urls = {c["url"] for c in r["new_candidates"]}
    assert "https://camps.example.org/after-school-program/" in urls
    assert "https://camps.example.org/robotics-camps/" in urls
    assert not any("donate" in u or "jobs" in u or "other.example.com" in u for u in urls)
    assert "https://camps.example.org/ages-7-9/" not in urls  # already a known source
    assert r["courses"]["courses"] == {}
    assert json.loads((tmp_path / "data/candidate_sources.json").read_text())["candidates"]
    assert not (tmp_path / "data/courses.json").read_text().count("Junior")


def test_report_contents(run, config):
    run("site_v1", RUN1)
    r = run("site_v2", RUN2, mode="both")
    md = build_report(r, config)
    for heading in ["## Summary", "## 🆕 New activities (1)", "## ✏️ Updated activities (1)",
                    "## 🏕️ Camps & seasonal programs", "✅ Unchanged activities", "## ❔ Not found this run (1)",
                    "## ⚠️ Sources that failed or need manual verification", "## 🔎 New candidate source pages"]:
        assert heading in md, heading
    assert "| $500 → **$550** |" in md
    assert "[Ocean Explorers](https://camps.example.org/camps/ocean-explorers/)" in md
    assert "[Example Science Camps](https://camps.example.org/ages-7-9/)" in md
    assert "[Example Music School](https://music.example.org/piano) | `FETCH_FAILED` | HTTP 403" in md
    assert "[Example City Recreation](https://city.example.gov/recreation)" in md
    assert "_Not published_" in md
    assert "Teen Game Design" not in md.split("## ⚠️")[0]  # ages 12-15 hidden by the 7-8 filter
    assert "1 tracked activities fall outside 7–8" in md
    assert "Initial baseline" not in md


def test_baseline_report_and_cli_writes_summary(tmp_path):
    summary = tmp_path / "step_summary.md"
    code = main(["--config-dir", str(FIXTURES / "config"), "--data-dir", str(tmp_path / "data"),
                 "--report", str(tmp_path / "out/report.md"), "--summary", str(summary),
                 "--fixtures", str(FIXTURES / "site_v1"), "--min-age", "7", "--max-age", "8"])
    assert code == 0
    md = summary.read_text()
    assert "Initial baseline run" in md and md == (tmp_path / "out/report.md").read_text()
    assert json.loads((tmp_path / "out/run_summary.json").read_text())["is_baseline"] is True


def test_cli_exit_code_when_nothing_saved(tmp_path):
    code = main(["--config-dir", str(FIXTURES / "config"), "--data-dir", str(tmp_path / "data"),
                 "--report", str(tmp_path / "report.md"), "--fixtures", str(FIXTURES / "site_down")])
    assert code == 2 and not (tmp_path / "data/courses.json").exists()
    assert "Data was NOT saved" in (tmp_path / "report.md").read_text()


def test_cli_rejects_bad_inputs(tmp_path):
    base = ["--config-dir", str(FIXTURES / "config"), "--data-dir", str(tmp_path), "--fixtures",
            str(FIXTURES / "site_v1"), "--report", str(tmp_path / "r.md")]
    assert main(base + ["--categories", "stem,quidditch"]) == 1
    assert main(base + ["--min-age", "9", "--max-age", "7"]) == 1


def test_discovery_honors_base_href(config):
    from activity_tracker.discovery import find_candidates
    html = '<html><head><base href="https://camps.example.org/"></head><body><a href="camps/robot/">Robot camp</a></body></html>'
    found = find_candidates(html, "https://camps.example.org/a/b/", config.settings, config.categories)
    assert [c["url"] for c in found] == ["https://camps.example.org/camps/robot/"]

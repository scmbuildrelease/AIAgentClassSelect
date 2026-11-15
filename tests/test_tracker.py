from activity_tracker.tracker import (FETCH_FAILED, NEW, NOT_FOUND, UNCHANGED, UPDATED, HISTORY_LIMIT,
                                      assign_ids, diff_fields, make_id, merge_source)


def rec(name="Robot Camp", url="https://x.example.org/robot", **kw):
    base = {"source_id": "src", "name": name, "detail_url": url, "price": "$500", "age_text": "Ages 7-9",
            "description": "Build robots.", "sessions": ["6/14 2027 At A"]}
    return {**base, **kw}


def test_stable_id_is_deterministic_and_normalizes_urls():
    a = make_id("src", "https://www.x.example.org/robot/?utm_source=mail", "Robot  Camp")
    assert a == make_id("src", "https://x.example.org/robot", "robot camp")
    assert a != make_id("other", "https://x.example.org/robot", "Robot Camp")
    assert a != make_id("src", "https://x.example.org/space", "Robot Camp")  # name alone is not the identity
    assert a.startswith("src-")


def test_duplicate_items_on_one_page_get_distinct_ids():
    recs = assign_ids([rec(url=None), rec(url=None)])
    assert recs[0]["id"] != recs[1]["id"]
    assert assign_ids([rec(url=None), rec(url=None)])[1]["id"] == recs[1]["id"]


def test_diff_ignores_whitespace_case_and_dash_style():
    old = rec(age_text="Ages 7-9", description="Build   robots.")
    new = rec(age_text="ages 7–9", description="Build robots.")
    assert diff_fields(old, new) == []
    assert diff_fields(old, rec(price="$550")) == [{"field": "price", "old": "$500", "new": "$550"}]


def merge(store, records, ok=True, day="2026-11-15"):
    return merge_source(store, "src", ok, assign_ids(records), day, day + "T00:00:00Z")


def test_merge_lifecycle():
    store = {"courses": {}}
    assert [e["status"] for e in merge(store, [rec()])] == [NEW]
    cid = next(iter(store["courses"]))
    assert [e["status"] for e in merge(store, [rec()], day="2026-11-20")] == [UNCHANGED]
    assert store["courses"][cid]["last_changed"] == "2026-11-15"
    ev = merge(store, [rec(price="$550")], day="2026-11-25")
    assert ev[0]["status"] == UPDATED and store["courses"][cid]["last_changed"] == "2026-11-25"
    assert store["courses"][cid]["history"][-1]["changes"][0] == {"field": "price", "old": "$500", "new": "$550"}

    merge(store, [rec(name="Other", url="https://x.example.org/other")], day="2026-12-01")
    gone = store["courses"][cid]
    assert gone["status"] == NOT_FOUND and gone["missing_since"] == "2026-12-01"
    assert gone["last_seen"] == "2026-11-25"  # history preserved, not deleted

    merge(store, [], ok=False, day="2026-12-05")
    assert {c["status"] for c in store["courses"].values()} == {FETCH_FAILED}
    assert len(store["courses"]) == 2


def test_history_is_capped():
    store = {"courses": {}}
    merge(store, [rec()])
    for i in range(HISTORY_LIMIT + 5):
        merge(store, [rec(price=f"${600 + i}")])
    assert len(next(iter(store["courses"].values()))["history"]) == HISTORY_LIMIT

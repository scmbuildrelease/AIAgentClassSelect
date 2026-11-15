from activity_tracker.extract import (extract, find_dates, find_enrollment, find_price, find_schedule,
                                      parse_age, strip_site_suffix)
from conftest import FIXTURES


def source(config, sid):
    return next(s for s in config.sources if s.id == sid)


def test_parse_age_variants():
    assert parse_age("For ages 6-9 only")[1:3] == (6, 9)
    assert parse_age("Ages 7 – 8")[1:3] == (7, 8)
    assert parse_age("Ages 5+")[1:3] == (5, None)
    assert parse_age("Grades 1st – 3rd")[1:] == (6, 9, "grade")
    assert parse_age("youth ages 18 months to 9 years")[0] is None  # nonsensical range is not guessed
    assert parse_age("no ages here") == (None, None, None, None)


def test_price_skips_fees_and_discounts():
    assert find_price("Registration fee $25. Tuition: $300 per session") == "$300 per session"
    assert find_price("Save $30 off! Camp price $549") == "$549"
    assert find_price("Contact us for pricing") is None


def test_schedule_requires_a_time_not_an_age_range():
    assert find_schedule("Ages 6-9, Grades 2-4") is None
    assert find_schedule("Saturdays 10:00am - 11:30am") == "Saturdays 10:00am - 11:30am"
    assert find_schedule("Monday – Friday, 9 am – 4 pm") == "Monday – Friday, 9 am – 4 pm"


def test_dates_and_enrollment():
    assert find_dates("Winter Camp February 15 – 19, 2027") == ("2027-02-15", "2027-02-19")
    assert find_dates("Session Dates: February 21 – May 2") == ("February 21", "May 2")
    assert find_dates("6/14 2027 At A; 7/26 2027 At B") == ("2027-06-14", "2027-07-26")
    assert find_dates("nothing") == (None, None)
    assert find_enrollment("Registration is now closed!") == "Registration closed"
    assert find_enrollment("Registration opens December 4, 2026") == "Registration opens December 4, 2026"
    assert find_enrollment("Hello") is None


def test_strip_site_suffix():
    assert strip_site_suffix("Summer Camp - Western Ballet", "Western Ballet") == "Summer Camp"
    assert strip_site_suffix("Ballet - Jazz", "Western Ballet") == "Ballet - Jazz"


def test_listing_extraction(config):
    html = (FIXTURES / "site_v1/camps.html").read_text()
    recs = extract(html, source(config, "fx-camps"), "https://camps.example.org/ages-7-9/", config.settings["cities"])
    assert [r["name"] for r in recs] == ["Junior Robot Engineer", "Space Explorer", "Teen Game Design"]
    robot = recs[0]
    assert robot["extraction"] == "listing"
    assert robot["detail_url"] == "https://camps.example.org/camps/junior-robot-engineer/"
    assert (robot["age_min"], robot["age_max"], robot["price"]) == (7, 9, "$500")
    assert (robot["start_date"], robot["end_date"]) == ("2027-06-14", "2027-07-12")
    assert robot["location"] == "Example Elementary, San Jose; Example Academy, Sunnyvale"
    assert robot["season"] == "summer" and robot["program_type"] == "camp"
    assert recs[2]["enrollment_status"] == "No sessions available"


def test_page_text_extraction_leaves_missing_fields_empty(config):
    music = extract((FIXTURES / "site_v1/music.html").read_text(), source(config, "fx-music"),
                    "https://music.example.org/piano", config.settings["cities"])[0]
    assert music["extraction"] == "page_text"
    assert music["name"] == "Group Piano for Kids"
    assert music["schedule"] == "Wednesdays 4:00pm - 4:45pm"
    assert music["price"] is None and music["enrollment_status"] is None and music["start_date"] is None


def test_jsonld_extraction(config):
    recs = extract((FIXTURES / "site_v1/dance.html").read_text(), source(config, "fx-dance"),
                   "https://dance.example.org/classes", config.settings["cities"])
    assert len(recs) == 1
    r = recs[0]
    assert r["extraction"] == "json-ld"
    assert r["detail_url"] == "https://dance.example.org/classes/beginning-ballet"
    assert (r["start_date"], r["end_date"], r["price"]) == ("2027-01-11", "2027-05-24", "$240")
    assert (r["age_min"], r["age_max"]) == (7, 8)
    assert r["enrollment_status"] == "Registration open"
    assert r["description"] == "Intro ballet technique."

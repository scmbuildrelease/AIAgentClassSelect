"""Which tracked activities to recommend now: lifecycle (dates), age fit and audience.

Used by the report and the backend. Records are never deleted or rewritten here: a past or adult
activity stays in data/courses.json and is only left out of the default recommendations.
All decisions use published values only; a missing value gives an "unknown" status, never a guess.
"""
import logging
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UPCOMING, ONGOING, PAST, DATE_UNKNOWN = "UPCOMING", "ONGOING", "PAST", "DATE_UNKNOWN"
AGE_MATCH_CONFIRMED, AGE_GROUP_MATCH = "AGE_MATCH_CONFIRMED", "AGE_GROUP_MATCH"
AGE_UNKNOWN, AGE_MISMATCH = "AGE_UNKNOWN", "AGE_MISMATCH"
ADULT, CHILDREN = "adult", "children"

ISO_DATE_RE = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
MDY_DATE_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/|\s+)(20\d{2})(?!\d)")  # "6/14 2027", "6/14/2027"
# Titles that explicitly name an adult audience. "成人陪同" (adult accompaniment) and "adults & kids" are not.
ADULT_TITLE_RE = re.compile(
    r"成人(?!陪同|陪伴|监护|監護)|辣妈|辣媽|"
    r"\badults?\b(?!\s*(?:&|and|with|\+|/)\s*(?:kids?|child|children|teens?|family))", re.I)
MIXED_TITLE_RE = re.compile(r"成人|大人|家长|家長|\badults?\b|\bparents?\b", re.I)  # with kids: family class
CHILD_TITLE_RE = re.compile(r"幼儿|幼兒|儿童|兒童|少儿|少兒|小学|小學|\bkids?\b|\bchildren\b|\bchild\b|\bjunior\b",
                            re.I)


DEFAULT_TIMEZONE = "America/Los_Angeles"


def local_today(now: datetime | None = None, tz: str | None = None) -> date:
    """Today's date where the activities are (Bay Area), not in UTC: at 8 pm on Nov 15 in San Jose
    it is already Nov 16 in UTC, and today's events must not count as past."""
    now = now or datetime.now(timezone.utc)
    try:
        return now.astimezone(ZoneInfo(tz or DEFAULT_TIMEZONE)).date()
    except ZoneInfoNotFoundError:  # no tz database (e.g. minimal containers without tzdata)
        logging.getLogger(__name__).warning("time zone %s unavailable; using UTC dates", tz or DEFAULT_TIMEZONE)
        return now.astimezone(timezone.utc).date()


def _date(text: str | None) -> date | None:
    """The first explicit full date (with year) in a value; month/day without a year is not a date."""
    for regex, order in ((ISO_DATE_RE, (0, 1, 2)), (MDY_DATE_RE, (2, 0, 1))):
        m = regex.search(text or "")
        if m:
            y, mo, d = (int(m.group(i + 1)) for i in order)
            try:
                return date(y, mo, d)
            except ValueError:
                return None
    return None


def lifecycle(rec: dict, today: date) -> str:
    """UPCOMING / ONGOING / PAST / DATE_UNKNOWN from explicit dates only.

    Individual sessions decide when they carry full dates: a series with a session today, or with
    sessions both before and after today, is ONGOING; it is PAST only once its last session is over.
    Otherwise start/end dates are used. A start date in the past with no end date is DATE_UNKNOWN
    (the activity may still be running), never PAST.
    """
    sessions = sorted(d for d in (_date(s) for s in rec.get("sessions") or []) if d)
    if sessions:
        if sessions[-1] < today:
            return PAST
        if sessions[0] > today:
            return UPCOMING
        return ONGOING
    start, end = _date(rec.get("start_date")), _date(rec.get("end_date"))
    if end and end < today:
        return PAST
    if start and start > today:
        return UPCOMING
    if start and (end or start == today):
        return ONGOING
    return DATE_UNKNOWN


def age_fit(rec: dict, min_age: int, max_age: int) -> str:
    """How the published ages relate to the wanted range.

    AGE_MATCH_CONFIRMED: an explicit age/grade range on the record overlaps it.
    AGE_GROUP_MATCH:     only an aggregator's broad age group (e.g. 小学 6–12) overlaps it; the event's own
                         ages are not published or not machine-readable. This is NOT confirmation.
    AGE_MISMATCH:        an explicit range, or the aggregator's only age group (e.g. 0–5), excludes it.
    AGE_UNKNOWN:         nothing reliable is published.
    """
    lo, hi = rec.get("age_min"), rec.get("age_max")
    if lo is not None or hi is not None:
        overlaps = (lo if lo is not None else 0) <= max_age and (hi if hi is not None else 99) >= min_age
        return AGE_MATCH_CONFIRMED if overlaps else AGE_MISMATCH
    g_lo, g_hi = rec.get("age_group_min"), rec.get("age_group_max")
    if g_lo is not None and g_hi is not None:
        return AGE_GROUP_MATCH if g_lo <= max_age and g_hi >= min_age else AGE_MISMATCH
    return AGE_UNKNOWN


def audience(rec: dict) -> str | None:
    """'adult' or 'children' only when the title says so explicitly; otherwise None (unknown).
    A provider being a children's school says nothing about an individual course."""
    name = rec.get("name") or ""
    if ADULT_TITLE_RE.search(name):
        return ADULT
    if MIXED_TITLE_RE.search(name):  # "Adults & Kids", "成人陪同…": a family activity, not a kids-only one
        return None
    if CHILD_TITLE_RE.search(name):
        return CHILDREN
    return None


def not_recommended_reason(rec: dict, min_age: int, max_age: int, today: date) -> str | None:
    """None if the activity belongs in the default (current, children's) recommendations."""
    if audience(rec) == ADULT:
        return "adult course"
    if lifecycle(rec, today) == PAST:
        return "past"
    if age_fit(rec, min_age, max_age) == AGE_MISMATCH:
        return "age mismatch"
    return None


def annotate(rec: dict, today: date) -> None:
    """Store the date- and title-derived classifications on a record (not used for change detection)."""
    rec["lifecycle"] = lifecycle(rec, today)
    rec["audience"] = audience(rec)

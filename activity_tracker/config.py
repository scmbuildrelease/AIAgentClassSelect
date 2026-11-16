"""Load and validate settings and the source list from config/*.json."""
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from .i18n import TRANSLATION_METHODS
from .tracker import normalize_url

# "organization": the page is fetched to verify the source and record its profile, but
# produces no activity records (homepages, about/contact pages).
PARSERS = {"page", "listing", "poster", "sections", "name_list", "nextjs_events", "organization"}
PROGRAM_TYPES = {"weekly_class", "camp", "seasonal_program", "event", "program_info"}
SOURCE_TYPES = {"activity_provider", "education_provider", "community_education_provider",
                "community_activity_aggregator"}
AGGREGATOR = "community_activity_aggregator"
VERIFICATION_STATUSES = {"VERIFIED", "PENDING"}
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# per-page settings that may override the source's own (see Source.pages)
PAGE_FIELDS = {"url", "parser", "categories", "program_type", "season", "course_name", "listing", "sections",
               "name_list", "campus_links", "location"}


class ConfigError(ValueError):
    pass


@dataclass
class Source:
    id: str
    provider: str
    url: str
    categories: list[str]
    city: str
    parser: str = "page"
    program_type: str = "program_info"
    season: str | None = None
    enabled: bool = True
    manual_only: bool = False
    notes: str = ""
    course_name: str | None = None
    listing: dict = field(default_factory=dict)
    translations: dict = field(default_factory=dict)  # {"zh": {"name": ..., "method": "manual"}}
    source_type: str = "activity_provider"
    verification_status: str = "VERIFIED"  # PENDING sources are listed in the report but never fetched
    organization_name: str | None = None
    language: list[str] = field(default_factory=list)  # languages the source publishes in, e.g. ["zh", "en"]
    locations: list[str] = field(default_factory=list)  # campuses / cities named by the source
    geographic_scope: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)  # program areas as the source describes them
    age_groups: dict = field(default_factory=dict)  # aggregator age filters: {"primary": {"label", "min", "max"}}
    require_bay_area: bool = False  # drop records whose location is not explicitly in the Bay Area
    location: str | None = None  # fixed location for every record (None: detect from the page)
    detect_location: bool = True
    pages: list[dict] = field(default_factory=list)  # more pages of the same source, see PAGE_FIELDS
    sections: dict = field(default_factory=dict)  # "sections" parser: {"container", "heading"}
    name_list: dict = field(default_factory=dict)  # "name_list" parser: {"block", "after_heading"}
    campus_links: dict = field(default_factory=dict)  # {"pattern": regex with (?P<campus>), "addresses": {}}
    aggregator: dict = field(default_factory=dict)  # "nextjs_events" parser: regions / category_map
    role: str = "activities"  # set on page views: "organization" or "activities"
    price_label: str | None = None  # page parser: take the price after this text (e.g. "Camp Tuition")

    @property
    def org_name(self) -> str:
        return self.organization_name or self.provider

    def page_views(self) -> list["Source"]:
        """The source's own URL plus `pages`, each as a Source with that page's settings.

        Records keep the source's id, so all pages of a source are merged together.
        """
        views = [replace(self, pages=[])]
        for page in self.pages:
            views.append(replace(self, pages=[], **{k: v for k, v in page.items() if k in PAGE_FIELDS}))
        for v in views:
            v.role = "organization" if v.parser == "organization" else "activities"
        return views


@dataclass
class Config:
    settings: dict
    sources: list[Source]
    discovery_seeds: list[dict]

    @property
    def categories(self) -> dict:
        return self.settings["categories"]

    @property
    def cities(self) -> dict[str, list[str]]:
        """{canonical city: [aliases]} including Chinese names from settings.city_aliases."""
        aliases = self.settings.get("city_aliases", {})
        return {c: aliases.get(c, []) for c in self.settings.get("cities", [])}


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON ({e})") from e


def load_config(config_dir: Path) -> Config:
    settings = _load_json(config_dir / "settings.json")
    raw = _load_json(config_dir / "sources.json")
    categories = settings.get("categories") or {}
    if not categories:
        raise ConfigError("settings.json must define at least one category")

    sources: list[Source] = []
    seen: set[str] = set()
    seen_urls: dict[str, str] = {}
    for entry in raw.get("sources", []):
        try:
            src = Source(**entry)
        except TypeError as e:
            raise ConfigError(f"source {entry.get('id')!r}: {e}") from e
        if not SOURCE_ID_RE.match(src.id):
            raise ConfigError(f"source id {src.id!r} must be lowercase letters, digits, dashes and underscores")
        if src.id in seen:
            raise ConfigError(f"duplicate source id {src.id!r}")
        seen.add(src.id)
        if src.source_type not in SOURCE_TYPES:
            raise ConfigError(f"{src.id}: source_type must be one of {sorted(SOURCE_TYPES)}")
        if src.verification_status not in VERIFICATION_STATUSES:
            raise ConfigError(f"{src.id}: verification_status must be one of {sorted(VERIFICATION_STATUSES)}")
        for page in src.pages:
            extra = set(page) - PAGE_FIELDS
            if extra or not page.get("url"):
                raise ConfigError(f"{src.id}: each page needs a url; unknown page keys {sorted(extra)}")
        for view in src.page_views():
            _validate_view(src.id, view, categories)
            key = normalize_url(view.url)
            if key in seen_urls:
                raise ConfigError(f"{src.id}: url {view.url} is already configured by {seen_urls[key]}")
            seen_urls[key] = src.id
        for lang, tr in src.translations.items():
            if not isinstance(tr, dict) or not tr.get("name"):
                raise ConfigError(f"{src.id}: translations.{lang} needs a name")
            if tr.get("method", "manual") not in TRANSLATION_METHODS:
                raise ConfigError(f"{src.id}: translations.{lang}.method must be one of {sorted(TRANSLATION_METHODS)}")
        sources.append(src)
    return Config(settings=settings, sources=sources, discovery_seeds=raw.get("discovery_seeds", []))


def _validate_view(source_id: str, view: Source, categories: dict) -> None:
    if not view.url.startswith(("http://", "https://")):
        raise ConfigError(f"{source_id}: url must start with http(s)://: {view.url!r}")
    if view.parser not in PARSERS:
        raise ConfigError(f"{source_id}: parser must be one of {sorted(PARSERS)}")
    if view.program_type not in PROGRAM_TYPES:
        raise ConfigError(f"{source_id}: program_type must be one of {sorted(PROGRAM_TYPES)}")
    unknown = set(view.categories) - set(categories)
    if unknown or not view.categories:
        raise ConfigError(f"{source_id}: unknown or missing categories {sorted(unknown)}")
    if view.parser == "listing" and not view.listing.get("item"):
        raise ConfigError(f"{source_id}: listing parser needs listing.item selector")
    if view.parser == "name_list" and not view.name_list.get("block"):
        raise ConfigError(f"{source_id}: name_list parser needs name_list.block selector")
    if view.parser == "nextjs_events" and not view.aggregator.get("regions"):
        raise ConfigError(f"{source_id}: nextjs_events parser needs aggregator.regions")
    if view.campus_links and "(?P<campus>" not in view.campus_links.get("pattern", ""):
        raise ConfigError(f"{source_id}: campus_links.pattern needs a (?P<campus>...) group")


def parse_category_filter(value: str | None, categories: dict) -> list[str]:
    """'all' / '' -> every category; otherwise comma-separated keys (validated)."""
    if not value or value.strip().lower() == "all":
        return list(categories)
    wanted = [v.strip().lower() for v in value.split(",") if v.strip()]
    unknown = [w for w in wanted if w not in categories]
    if unknown:
        raise ConfigError(f"unknown categories {unknown}; valid: {', '.join(categories)}")
    return wanted

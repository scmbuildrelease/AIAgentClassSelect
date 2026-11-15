"""Load and validate settings and the source list from config/*.json."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import TRANSLATION_METHODS

PARSERS = {"page", "listing", "poster"}
PROGRAM_TYPES = {"weekly_class", "camp", "seasonal_program", "event", "program_info"}
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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

    sources, seen = [], set()
    for entry in raw.get("sources", []):
        src = Source(**entry)
        if not SOURCE_ID_RE.match(src.id):
            raise ConfigError(f"source id {src.id!r} must be lowercase letters, digits and dashes")
        if src.id in seen:
            raise ConfigError(f"duplicate source id {src.id!r}")
        seen.add(src.id)
        if not src.url.startswith(("http://", "https://")):
            raise ConfigError(f"{src.id}: url must start with http(s)://")
        if src.parser not in PARSERS:
            raise ConfigError(f"{src.id}: parser must be one of {sorted(PARSERS)}")
        if src.program_type not in PROGRAM_TYPES:
            raise ConfigError(f"{src.id}: program_type must be one of {sorted(PROGRAM_TYPES)}")
        unknown = set(src.categories) - set(categories)
        if unknown or not src.categories:
            raise ConfigError(f"{src.id}: unknown or missing categories {sorted(unknown)}")
        if src.parser == "listing" and not src.listing.get("item"):
            raise ConfigError(f"{src.id}: listing parser needs listing.item selector")
        for lang, tr in src.translations.items():
            if not isinstance(tr, dict) or not tr.get("name"):
                raise ConfigError(f"{src.id}: translations.{lang} needs a name")
            if tr.get("method", "manual") not in TRANSLATION_METHODS:
                raise ConfigError(f"{src.id}: translations.{lang}.method must be one of {sorted(TRANSLATION_METHODS)}")
        sources.append(src)
    return Config(settings=settings, sources=sources, discovery_seeds=raw.get("discovery_seeds", []))


def parse_category_filter(value: str | None, categories: dict) -> list[str]:
    """'all' / '' -> every category; otherwise comma-separated keys (validated)."""
    if not value or value.strip().lower() == "all":
        return list(categories)
    wanted = [v.strip().lower() for v in value.split(",") if v.strip()]
    unknown = [w for w in wanted if w not in categories]
    if unknown:
        raise ConfigError(f"unknown categories {unknown}; valid: {', '.join(categories)}")
    return wanted

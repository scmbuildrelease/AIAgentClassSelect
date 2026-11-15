import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from activity_tracker.cli import run_discovery  # noqa: E402
from activity_tracker.config import load_config  # noqa: E402
from activity_tracker.fetcher import FixtureFetcher  # noqa: E402
from activity_tracker.tracker import Store  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
RUN1 = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
RUN2 = datetime(2027, 1, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return load_config(FIXTURES / "config")


@pytest.fixture
def params(config):
    return {"min_age": 7, "max_age": 8, "categories": list(config.categories), "mode": "refresh_known_sources"}


@pytest.fixture
def run(config, params, tmp_path):
    """Run discovery against a fixture site into tmp_path/data. Returns a callable."""
    def _run(site: str, when=RUN1, **overrides):
        return run_discovery(config, Store(tmp_path / "data"), FixtureFetcher(FIXTURES / site),
                             {**params, **overrides}, now=when)
    return _run


def by_name(run_result):
    return {c["name"]: c for c in run_result["courses"]["courses"].values()}

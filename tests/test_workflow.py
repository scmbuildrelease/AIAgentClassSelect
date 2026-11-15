"""Guard the critical workflow requirements: manual-only trigger, no secrets, minimal permissions."""
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def load(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text())
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 parses the key `on` as True
    return data


def test_discovery_workflow_is_manual_only():
    wf = load("discover.yml")
    assert list(wf["on"]) == ["workflow_dispatch"]
    inputs = wf["on"]["workflow_dispatch"]["inputs"]
    assert inputs["min_age"]["default"] == 7 and inputs["max_age"]["default"] == 8
    assert inputs["categories"]["default"] == "all"
    assert inputs["search_mode"]["options"] == ["refresh_known_sources", "discover_new_sources", "both"]
    assert wf["permissions"] == {"contents": "write"}


def test_no_workflow_is_scheduled_and_discovery_needs_no_secrets():
    for path in WORKFLOWS.glob("*.yml"):
        assert "schedule" not in load(path.name)["on"], path.name
        assert "cron" not in path.read_text(), path.name
    text = (WORKFLOWS / "discover.yml").read_text()
    assert "secrets." not in text and "OPENAI" not in text
    for other in ("tests.yml", "docker-build.yml"):
        assert "python -m activity_tracker" not in (WORKFLOWS / other).read_text()

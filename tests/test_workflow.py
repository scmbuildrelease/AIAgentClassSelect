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


def test_docker_images_are_multi_platform():
    """Both images must publish amd64 and arm64 (Apple Silicon) variants under the same tags."""
    wf = load("docker-build.yml")
    assert set(wf["on"]) == {"push", "workflow_dispatch"}
    assert wf["permissions"] == {"contents": "read", "packages": "write"}
    steps = wf["jobs"]["build"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    qemu, buildx = uses.index("docker/setup-qemu-action@v3"), uses.index("docker/setup-buildx-action@v3")
    builds = [i for i, u in enumerate(uses) if u.startswith("docker/build-push-action@")]
    assert len(builds) == 2 and qemu < buildx < min(builds)
    for i, image in zip(builds, ("backend", "frontend")):
        with_ = steps[i]["with"]
        assert with_["platforms"] == "linux/amd64,linux/arm64"
        assert with_["push"] is True
        assert with_["tags"].strip().splitlines() == [
            f"ghcr.io/${{{{ github.repository_owner }}}}/aiagentclassselect-{image}:latest",
            f"ghcr.io/${{{{ github.repository_owner }}}}/aiagentclassselect-{image}:main-${{{{ env.SHORT_SHA }}}}"]

"""Validate manifest.json and hacs.json contain the fields HACS requires."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_manifest_has_required_hacs_fields():
    manifest = json.loads(
        (REPO_ROOT / "custom_components" / "chores" / "manifest.json").read_text()
    )
    required = {
        "domain",
        "documentation",
        "issue_tracker",
        "codeowners",
        "name",
        "version",
    }
    missing = required - manifest.keys()
    assert not missing, f"manifest.json is missing required keys: {missing}"


def test_hacs_json_has_name():
    hacs_config = json.loads((REPO_ROOT / "hacs.json").read_text())
    assert "name" in hacs_config

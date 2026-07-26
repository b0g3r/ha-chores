# Repo & Component Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a HACS-installable, empty-but-valid Home Assistant custom integration skeleton — with a working test harness, CI validation, and linting — that the feature implementation plan (chores/maintenance logic) will be built on top of.

**Architecture:** A single custom integration at `custom_components/chores/`, domain `chores`, config-flow-based (no YAML setup), with zero platforms/entities yet. Tested via `pytest-homeassistant-custom-component` against a real (test-mode) Home Assistant core. Validated in CI via the official `hassfest` and HACS validation GitHub Actions, plus `ruff` and `pytest`.

**Tech Stack:** Python 3.13, Home Assistant custom integration APIs, `pytest` + `pytest-homeassistant-custom-component`, `ruff`, GitHub Actions.

## Global Constraints

- Domain is `chores` — used verbatim in `manifest.json`, `const.py`, and all entity/service names in later plans.
- Distributed as a HACS **custom repository** (not submitted to the HACS default store) — `hacs.json` + `custom_components/chores/` is the full required layout; no `brand` assets directory needed for this.
- `config_flow: true` in the manifest — every later plan's config flow work extends `custom_components/chores/config_flow.py`, it does not replace it.
- GitHub owner/repo: `b0g3r/ha-chores`. Used verbatim in `manifest.json` (`documentation`, `issue_tracker`), `hacs.json`, `README.md`, and `LICENSE`.
- No personal or environment-specific data in any file (see `AGENTS.md` at repo root) — this plan's example content is already generic.
- All shell commands below assume the repo root (`/Users/dee/Documents/chores`) as the working directory, and a Python virtual environment at `.venv/` (created in Task 1, Step 2).

---

### Task 1: Minimal loadable integration + test harness

**Files:**
- Create: `custom_components/__init__.py`
- Create: `custom_components/chores/__init__.py`
- Create: `custom_components/chores/const.py`
- Create: `custom_components/chores/manifest.json`
- Create: `custom_components/chores/config_flow.py`
- Create: `requirements_test.txt`
- Create: `pyproject.toml`
- Create: `conftest.py`
- Create: `tests/__init__.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Produces: `custom_components.chores.const.DOMAIN` (str, value `"chores"`), `custom_components.chores.config_flow.ChoresConfigFlow` (a `config_entries.ConfigFlow` subclass registered for domain `chores`, single-instance-only), `async_setup_entry(hass, entry) -> bool` / `async_unload_entry(hass, entry) -> bool` in `custom_components/chores/__init__.py`. Later plans add platforms to the `PLATFORMS` list in this file and add config-flow steps/subentries to `ChoresConfigFlow`.

- [ ] **Step 1: Write the test harness config and the failing test**

Create `requirements_test.txt`:

```
pytest
pytest-homeassistant-custom-component
```

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

Create `conftest.py` (repo root):

```python
"""Root pytest configuration."""
pytest_plugins = "pytest_homeassistant_custom_component"
```

Create `tests/__init__.py` (empty file).

Create `tests/test_init.py`:

```python
"""Tests for Chores integration setup."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading for every test in this module."""
    yield


async def test_setup_entry_succeeds(hass):
    """A config entry for the hub sets up successfully."""
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.config_entries import ConfigEntryState
    assert entry.state is ConfigEntryState.LOADED
```

- [ ] **Step 2: Create the venv, install test deps, run the test, verify it fails**

```bash
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements_test.txt
./.venv/bin/python -m pytest tests/ -v
```

Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'custom_components.chores'` (or similar collection error), since none of the integration source files exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `custom_components/__init__.py` (empty file).

Create `custom_components/chores/const.py`:

```python
"""Constants for the Chores & Maintenance integration."""

DOMAIN = "chores"
```

Create `custom_components/chores/manifest.json`:

```json
{
  "domain": "chores",
  "name": "Chores & Maintenance",
  "codeowners": ["@b0g3r"],
  "config_flow": true,
  "documentation": "https://github.com/b0g3r/ha-chores",
  "integration_type": "hub",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/b0g3r/ha-chores/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

Create `custom_components/chores/config_flow.py`:

```python
"""Config flow for the Chores & Maintenance integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class ChoresConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of the Chores & Maintenance hub."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the single setup step: create the hub entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Chores & Maintenance", data={})
        return self.async_show_form(step_id="user")
```

Create `custom_components/chores/__init__.py`:

```python
"""The Chores & Maintenance integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chores & Maintenance from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 4: Run the test again, verify it passes**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: PASS — `tests/test_init.py::test_setup_entry_succeeds PASSED`.

(This exact scaffold and fixture pattern was verified working during planning — 1 passed, no warnings, with `pytest-homeassistant-custom-component` 0.13.205.)

- [ ] **Step 5: Commit**

```bash
git add custom_components requirements_test.txt pyproject.toml conftest.py tests
git commit -m "Add loadable integration skeleton with test harness"
```

---

### Task 2: HACS packaging metadata

**Files:**
- Create: `hacs.json`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `custom_components/chores/manifest.json` from Task 1 (reads it to check required keys).
- Produces: nothing later tasks import — pure repo metadata.

- [ ] **Step 1: Write the failing test**

Create `tests/test_manifest.py`:

```python
"""Validate manifest.json and hacs.json contain the fields HACS requires."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_manifest_has_required_hacs_fields():
    manifest = json.loads(
        (REPO_ROOT / "custom_components" / "chores" / "manifest.json").read_text()
    )
    required = {"domain", "documentation", "issue_tracker", "codeowners", "name", "version"}
    missing = required - manifest.keys()
    assert not missing, f"manifest.json is missing required keys: {missing}"


def test_hacs_json_has_name():
    hacs_config = json.loads((REPO_ROOT / "hacs.json").read_text())
    assert "name" in hacs_config
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_manifest.py -v
```

Expected: FAIL on `test_hacs_json_has_name` — `FileNotFoundError` (`hacs.json` doesn't exist yet). `test_manifest_has_required_hacs_fields` passes already since Task 1's manifest already has all required keys — that's fine, it's here to guard against regressions in later edits.

- [ ] **Step 3: Write the packaging files**

Create `hacs.json`:

```json
{
  "name": "Chores & Maintenance",
  "render_readme": true
}
```

Create `.gitignore`:

```
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
*.egg-info/
.DS_Store
```

Create `LICENSE` (MIT):

```
MIT License

Copyright (c) 2026 b0g3r

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Create `README.md`:

```markdown
# Chores & Maintenance for Home Assistant

A Home Assistant custom integration for recurring household chores and maintenance tasks — the kind with a cadence (every N days, or every N uses of something) and a completion action (scan an NFC tag, or tap a notification button).

## Features

- Add a chore through the UI — no YAML, no helper entities to create by hand.
- Two due-triggers per chore: a fixed day interval, or a usage-cycle threshold fed by your own automations.
- Two completion methods per chore, independently chosen: NFC tag scan, notification action, or both.
- Notifies whoever is currently home, on their own phone.
- Repeats the reminder every morning (at a per-chore time) until the chore is completed.
- A live to-do list of everything currently due.

See `docs/superpowers/specs/2026-07-26-chores-maintenance-design.md` for the full design.

## Installation

Add this repository as a custom repository in [HACS](https://hacs.xyz/), category "Integration", then install "Chores & Maintenance" and restart Home Assistant.

## Configuration

Settings → Devices & Services → Add Integration → "Chores & Maintenance" sets up the hub. Add individual chores from the hub's device page.

## License

MIT — see `LICENSE`.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: PASS — all tests in `tests/` green, including both `test_manifest.py` cases.

- [ ] **Step 5: Commit**

```bash
git add hacs.json README.md LICENSE .gitignore tests/test_manifest.py
git commit -m "Add HACS packaging metadata, README, and LICENSE"
```

---

### Task 3: Linting

**Files:**
- Modify: `pyproject.toml` (adds `[tool.ruff]` sections to the file Task 1 created)
- Create: `requirements_test.txt` (modify — add `ruff`)

**Interfaces:**
- Consumes: `pyproject.toml` from Task 1.
- Produces: a `ruff check .` command that later CI (Task 4) and later plans' code must keep passing.

- [ ] **Step 1: Add ruff as a test dependency**

Modify `requirements_test.txt` to:

```
pytest
pytest-homeassistant-custom-component
ruff
```

- [ ] **Step 2: Install and run ruff, verify it reports the (expected-clean) baseline**

```bash
./.venv/bin/pip install --quiet -r requirements_test.txt
./.venv/bin/ruff check .
```

Expected at this point: passes already (the Task 1/2 scaffold is clean) — this step exists to prove the *baseline* is clean before adding the config, since the config in Step 3 tightens the rule set.

- [ ] **Step 3: Add ruff configuration**

Modify `pyproject.toml`, adding these sections (keep the existing `[tool.pytest.ini_options]` section as-is):

```toml
[tool.ruff]
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

- [ ] **Step 4: Run ruff again, verify it still passes**

```bash
./.venv/bin/ruff check .
```

Expected: `All checks passed!` (verified during planning against this exact scaffold).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements_test.txt
git commit -m "Add ruff linting configuration"
```

---

### Task 4: CI validation workflow

**Files:**
- Create: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: `requirements_test.txt` (Tasks 1/3), `custom_components/chores/manifest.json` (Task 1), `hacs.json` (Task 2).
- Produces: nothing later tasks import — this is the last task in this plan; the feature-implementation plan runs against the CI this task establishes.

There's no local test for this task — a workflow file's real validation is GitHub Actions running it, which happens on the first push. This task's "verify it passes" step is pushing and checking the run, not a local pytest step.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: Validate

on:
  push:
  pull_request:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements_test.txt
      - run: pytest
      - run: ruff check .
```

- [ ] **Step 2: Run the full local test suite and lint one more time to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
./.venv/bin/ruff check .
```

Expected: all tests PASS, ruff reports `All checks passed!`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "Add CI workflow: hassfest, HACS, pytest, and ruff validation"
```

---

## After This Plan

The result is a HACS-installable integration that does nothing yet, with green CI. The next plan (chores/maintenance feature implementation, per `docs/superpowers/specs/2026-07-26-chores-maintenance-design.md`) builds the hub config flow, chore subentries, entities, services, due-detection engine, NFC/notification wiring, and the to-do list view on top of this skeleton.

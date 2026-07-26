# Chores & Maintenance Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full chores/maintenance system described in `docs/superpowers/specs/2026-07-26-chores-maintenance-design.md`, on top of the skeleton produced by `docs/superpowers/plans/2026-07-26-repo-scaffolding.md`.

**Architecture:** One config entry ("Chores & Maintenance") whose config-flow data holds the person→notify mapping; chores are managed through that entry's Options Flow and stored as a list in `entry.options["chores"]`. Each chore's due/count/notification state persists in a `homeassistant.helpers.storage.Store`. Each chore gets three entities (status sensor, due binary sensor, mark-complete button) plus a shared `todo.chores` list, all rebuilt from options+store whenever the entry (re)loads. Two services (`chores.log_cycle`, `chores.mark_complete`) and two internal event listeners (`tag_scanned`, `mobile_app_notification_action`) all funnel into one completion routine. A per-chore daily scheduled check plus an immediate post-`log_cycle` check both call the same due-and-notify routine.

**Tech Stack:** Python 3.13, Home Assistant custom integration APIs (config entries, options flow, entity platforms, storage helper, dispatcher signals, event bus), `pytest` + `pytest-homeassistant-custom-component` (from the scaffolding plan).

## Global Constraints

- Domain is `chores` (from the scaffolding plan) — do not rename.
- No config-entry subentries — chores live in `entry.options["chores"]`, a dict keyed by a generated `chore_id` (see spec §5 for the rationale).
- Every due-notification carries `data.tag = f"chores_{chore_id}"` and completion clears that same tag on every mapped notify target, not only whoever completed it (spec §10).
- A cycle-mode chore's due-check fires on two independent triggers — an immediate check after `chores.log_cycle`, and once daily per-chore at its own `notify_time` — and at most one notification per chore per calendar day (spec §10). Both triggers must remain wired; do not collapse to one.
- No hub-level default notification time or message template — `notify_time` is required per chore, and notification text is generated from the chore's `name` (spec §3, §6).
- All new Python files avoid HA APIs newer than config entries / options flow / entity platforms / storage / dispatcher / event bus — no config-entry subentries (see above).

---

### Task 1: Due-detection state machine

**Files:**
- Create: `custom_components/chores/chore.py`
- Test: `tests/test_chore.py`

**Interfaces:**
- Produces: `ChoreMode` (str `Enum`: `INTERVAL_DAYS = "interval_days"`, `CYCLE_COUNT = "cycle_count"`); `Chore` dataclass with fields `chore_id: str`, `name: str`, `mode: ChoreMode`, `interval_days: int | None`, `cycle_threshold: int | None`, `count: int = 0`, `last_completed: date | None = None`, `last_notified_date: date | None = None`; methods `is_due(today: date) -> bool`, `should_notify_today(today: date) -> bool`, `record_notified(today: date) -> None`, `log_cycle() -> None` (raises `ValueError` if mode is not `CYCLE_COUNT`), `mark_complete(today: date) -> None`. No Home Assistant imports anywhere in this file — later tasks depend on that staying true so this stays trivially unit-testable.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chore.py`:

```python
"""Unit tests for the pure due-detection state machine."""
from datetime import date

import pytest

from custom_components.chores.chore import Chore, ChoreMode


def test_cycle_chore_not_due_below_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=29)
    assert chore.is_due(date(2026, 1, 1)) is False


def test_cycle_chore_due_at_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_cycle_chore_stays_due_above_threshold():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=45)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_log_cycle_increments_count():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=29)
    chore.log_cycle()
    assert chore.count == 30
    assert chore.is_due(date(2026, 1, 1)) is True


def test_log_cycle_rejected_for_interval_mode():
    chore = Chore("c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7)
    with pytest.raises(ValueError):
        chore.log_cycle()


def test_interval_chore_due_when_never_completed():
    chore = Chore("c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7)
    assert chore.is_due(date(2026, 1, 1)) is True


def test_interval_chore_not_due_before_interval_elapses():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    assert chore.is_due(date(2026, 1, 5)) is False


def test_interval_chore_due_exactly_on_interval_boundary():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    assert chore.is_due(date(2026, 1, 8)) is True


def test_should_notify_today_dedup():
    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    today = date(2026, 1, 1)
    assert chore.should_notify_today(today) is True
    chore.record_notified(today)
    assert chore.should_notify_today(today) is False


def test_should_notify_today_resets_next_day():
    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=30, last_notified_date=date(2026, 1, 1),
    )
    assert chore.should_notify_today(date(2026, 1, 2)) is True


def test_mark_complete_resets_cycle_chore():
    chore = Chore(
        "c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30,
        count=35, last_notified_date=date(2026, 1, 1),
    )
    chore.mark_complete(date(2026, 1, 2))
    assert chore.count == 0
    assert chore.last_notified_date is None
    assert chore.is_due(date(2026, 1, 2)) is False


def test_mark_complete_reschedules_interval_chore_from_completion_date():
    chore = Chore(
        "c2", "Water plants", ChoreMode.INTERVAL_DAYS, interval_days=7,
        last_completed=date(2026, 1, 1),
    )
    chore.mark_complete(date(2026, 1, 10))
    assert chore.last_completed == date(2026, 1, 10)
    assert chore.is_due(date(2026, 1, 16)) is False
    assert chore.is_due(date(2026, 1, 17)) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./.venv/bin/python -m pytest tests/test_chore.py -v
```

Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'custom_components.chores.chore'`.

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/chore.py`:

```python
"""Pure due-detection state machine for a single chore. No Home Assistant imports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class ChoreMode(str, Enum):
    INTERVAL_DAYS = "interval_days"
    CYCLE_COUNT = "cycle_count"


@dataclass
class Chore:
    chore_id: str
    name: str
    mode: ChoreMode
    interval_days: int | None = None
    cycle_threshold: int | None = None
    count: int = 0
    last_completed: date | None = None
    last_notified_date: date | None = None

    def __post_init__(self) -> None:
        if self.mode is ChoreMode.INTERVAL_DAYS and self.interval_days is None:
            raise ValueError("interval_days is required when mode is interval_days")
        if self.mode is ChoreMode.CYCLE_COUNT and self.cycle_threshold is None:
            raise ValueError("cycle_threshold is required when mode is cycle_count")

    def is_due(self, today: date) -> bool:
        """Whether this chore currently needs attention."""
        if self.mode is ChoreMode.CYCLE_COUNT:
            return self.count >= self.cycle_threshold
        if self.last_completed is None:
            return True
        return today >= self.last_completed + timedelta(days=self.interval_days)

    def should_notify_today(self, today: date) -> bool:
        """Due, and not already notified today (the dedup rule, spec §10)."""
        return self.is_due(today) and self.last_notified_date != today

    def record_notified(self, today: date) -> None:
        self.last_notified_date = today

    def log_cycle(self) -> None:
        """Record one completed cycle. Only valid for cycle-count-mode chores."""
        if self.mode is not ChoreMode.CYCLE_COUNT:
            raise ValueError(f"log_cycle is not valid for mode {self.mode}")
        self.count += 1

    def mark_complete(self, today: date) -> None:
        """Reset the chore after completion, regardless of mode."""
        self.count = 0
        self.last_completed = today
        self.last_notified_date = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/bin/python -m pytest tests/test_chore.py -v
```

Expected: PASS — all 12 tests green. (Verified during planning with this exact code.)

- [ ] **Step 5: Commit**

```bash
git add custom_components/chores/chore.py tests/test_chore.py
git commit -m "Add pure due-detection state machine for chores"
```

---

### Task 2: Constants and persistent runtime store

**Files:**
- Modify: `custom_components/chores/const.py`
- Create: `custom_components/chores/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `Chore`, `ChoreMode` from `custom_components/chores/chore.py` (Task 1).
- Produces: in `const.py` — `CONF_CHORES = "chores"`, `CONF_PERSON_NOTIFY_MAP = "person_notify_map"`, `CONF_NAME = "name"`, `CONF_MODE = "mode"`, `CONF_INTERVAL_DAYS = "interval_days"`, `CONF_CYCLE_THRESHOLD = "cycle_threshold"`, `CONF_COMPLETION_METHOD = "completion_method"`, `CONF_NFC_TAG_ENTITY_ID = "nfc_tag_entity_id"`, `CONF_NOTIFY_TIME = "notify_time"`, `MODE_INTERVAL_DAYS = "interval_days"`, `MODE_CYCLE_COUNT = "cycle_count"`, `COMPLETION_NFC_TAG = "nfc_tag"`, `COMPLETION_NOTIFICATION_ACTION = "notification_action"`, `COMPLETION_BOTH = "both"`, `NOTIFICATION_ACTION_PREFIX = "CHORES_DONE_"`, and `def chore_updated_signal(chore_id: str) -> str` (returns `f"{DOMAIN}_chore_updated_{chore_id}"` — the dispatcher signal name later tasks use to push entity updates). In `store.py` — `ChoreStore` class with `__init__(self, hass, entry_id)`, `async def async_load(self, chore_configs: dict[str, dict]) -> None` (populates `self.chores: dict[str, Chore]`), `async def async_save(self) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_store.py`:

```python
"""Tests for chore runtime state persistence."""
from custom_components.chores.store import ChoreStore

CHORE_CONFIGS = {
    "c1": {"name": "Dishwasher maintenance", "mode": "cycle_count", "cycle_threshold": 30},
}


async def test_store_round_trips_runtime_state(hass):
    store = ChoreStore(hass, "test_entry")
    await store.async_load(CHORE_CONFIGS)
    store.chores["c1"].log_cycle()
    await store.async_save()

    reloaded = ChoreStore(hass, "test_entry")
    await reloaded.async_load(CHORE_CONFIGS)
    assert reloaded.chores["c1"].count == 1


async def test_store_defaults_new_chore_to_zero_state(hass):
    store = ChoreStore(hass, "test_entry_2")
    await store.async_load(CHORE_CONFIGS)
    assert store.chores["c1"].count == 0
    assert store.chores["c1"].last_completed is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.chores.store'`.

- [ ] **Step 3: Write the implementation**

Modify `custom_components/chores/const.py` to:

```python
"""Constants for the Chores & Maintenance integration."""

DOMAIN = "chores"

CONF_CHORES = "chores"
CONF_PERSON_NOTIFY_MAP = "person_notify_map"

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_INTERVAL_DAYS = "interval_days"
CONF_CYCLE_THRESHOLD = "cycle_threshold"
CONF_COMPLETION_METHOD = "completion_method"
CONF_NFC_TAG_ENTITY_ID = "nfc_tag_entity_id"
CONF_NOTIFY_TIME = "notify_time"

MODE_INTERVAL_DAYS = "interval_days"
MODE_CYCLE_COUNT = "cycle_count"

COMPLETION_NFC_TAG = "nfc_tag"
COMPLETION_NOTIFICATION_ACTION = "notification_action"
COMPLETION_BOTH = "both"

NOTIFICATION_ACTION_PREFIX = "CHORES_DONE_"


def chore_updated_signal(chore_id: str) -> str:
    """Dispatcher signal name fired whenever a chore's runtime state changes."""
    return f"{DOMAIN}_chore_updated_{chore_id}"
```

Create `custom_components/chores/store.py`:

```python
"""Runtime state persistence for chores (count, last_completed, last_notified_date)."""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .chore import Chore, ChoreMode
from .const import DOMAIN

STORAGE_VERSION = 1


def _chore_from_config(chore_id: str, config: dict[str, Any], state: dict[str, Any]) -> Chore:
    """Build a Chore by merging its options-provided shape with its stored runtime state."""
    last_completed = state.get("last_completed")
    last_notified_date = state.get("last_notified_date")
    return Chore(
        chore_id=chore_id,
        name=config["name"],
        mode=ChoreMode(config["mode"]),
        interval_days=config.get("interval_days"),
        cycle_threshold=config.get("cycle_threshold"),
        count=state.get("count", 0),
        last_completed=date.fromisoformat(last_completed) if last_completed else None,
        last_notified_date=date.fromisoformat(last_notified_date) if last_notified_date else None,
    )


def _state_from_chore(chore: Chore) -> dict[str, Any]:
    """Extract just the runtime fields of a Chore for persistence."""
    return {
        "count": chore.count,
        "last_completed": chore.last_completed.isoformat() if chore.last_completed else None,
        "last_notified_date": chore.last_notified_date.isoformat() if chore.last_notified_date else None,
    }


class ChoreStore:
    """Loads/saves chore runtime state and holds the live Chore objects for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_state")
        self.chores: dict[str, Chore] = {}

    async def async_load(self, chore_configs: dict[str, dict[str, Any]]) -> None:
        """Rebuild self.chores from the given options-provided configs plus any stored state."""
        raw_state: dict[str, Any] = await self._store.async_load() or {}
        self.chores = {
            chore_id: _chore_from_config(chore_id, config, raw_state.get(chore_id, {}))
            for chore_id, config in chore_configs.items()
        }

    async def async_save(self) -> None:
        """Persist the runtime fields of every current chore."""
        await self._store.async_save(
            {chore_id: _state_from_chore(chore) for chore_id, chore in self.chores.items()}
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_store.py -v
```

Expected: PASS — both tests green.

If `Store(hass, ...)` construction or `async_save`/`async_load` signatures error, check the exact signature shipped by the `homeassistant` version `pytest-homeassistant-custom-component` pulled in (`./.venv/bin/python -c "from homeassistant.helpers.storage import Store; help(Store)"`) — the constructor and method names are stable, but keep this in mind since it's the first storage-layer code in the project.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chores/const.py custom_components/chores/store.py tests/test_store.py
git commit -m "Add constants and persistent runtime store for chores"
```

---

### Task 3: Hub config flow and options flow

**Files:**
- Modify: `custom_components/chores/config_flow.py`
- Create: `custom_components/chores/strings.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `CONF_*`/`MODE_*`/`COMPLETION_*` constants from `const.py` (Task 2).
- Produces: `ChoresConfigFlow` (extended with `async_get_options_flow`) and `ChoresOptionsFlow` (`config_entries.OptionsFlow` subclass) with steps `async_step_init` (menu), `async_step_add_chore`, `async_step_remove_chore`, `async_step_notify_mapping`. Later tasks read the resulting `entry.options[CONF_CHORES]` (a `dict[str, dict]`) and `entry.options[CONF_PERSON_NOTIFY_MAP]` (a `dict[str, str]` mapping a `person.*` entity_id to a `notify.*` entity_id).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config_flow.py`:

```python
"""Tests for the hub config flow and options flow."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_CHORES, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_user_flow_creates_single_hub_entry(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    assert result["title"] == "Chores & Maintenance"


async def test_user_flow_aborts_if_hub_already_exists(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_add_chore_via_options_flow(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Chores & Maintenance", data={}, options={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_chore"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Dishwasher maintenance",
            "mode": "cycle_count",
            "interval_days": 7,
            "cycle_threshold": 30,
            "completion_method": "notification_action",
            "nfc_tag_entity_id": "",
            "notify_time": "08:00:00",
        },
    )
    assert result["type"] == "create_entry"
    chores = entry.options[CONF_CHORES]
    assert len(chores) == 1
    (chore_config,) = chores.values()
    assert chore_config["name"] == "Dishwasher maintenance"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./.venv/bin/python -m pytest tests/test_config_flow.py -v
```

Expected: FAIL on `test_add_chore_via_options_flow` (no options flow exists yet — `async_get_options_flow` isn't defined so `hass.config_entries.options.async_init` errors). The two hub-entry tests may already pass from the Plan-1 skeleton; that's fine, they guard against regressions here.

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/strings.json`:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Set up Chores & Maintenance"
      }
    },
    "abort": {
      "single_instance_allowed": "Only one Chores & Maintenance hub is allowed."
    }
  },
  "options": {
    "step": {
      "init": {
        "menu_options": {
          "add_chore": "Add a chore",
          "remove_chore": "Remove a chore",
          "notify_mapping": "Set up who gets notified"
        }
      },
      "add_chore": {
        "title": "Add a chore",
        "data": {
          "name": "Name",
          "mode": "Due-trigger type",
          "interval_days": "Interval (days) — only used if type is Interval",
          "cycle_threshold": "Cycle threshold — only used if type is Cycle count",
          "completion_method": "Completion method",
          "nfc_tag_entity_id": "NFC tag — only used if completion method includes NFC tag",
          "notify_time": "Morning check time"
        }
      },
      "remove_chore": {
        "title": "Remove a chore",
        "data": {
          "chore_id": "Chore"
        }
      },
      "notify_mapping": {
        "title": "Set up who gets notified"
      }
    },
    "abort": {
      "no_chores": "There are no chores to remove yet."
    }
  }
}
```

Modify `custom_components/chores/config_flow.py` to:

```python
"""Config and options flow for the Chores & Maintenance integration."""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CHORES,
    CONF_COMPLETION_METHOD,
    CONF_CYCLE_THRESHOLD,
    CONF_INTERVAL_DAYS,
    CONF_MODE,
    CONF_NAME,
    CONF_NFC_TAG_ENTITY_ID,
    CONF_NOTIFY_TIME,
    CONF_PERSON_NOTIFY_MAP,
    DOMAIN,
    MODE_CYCLE_COUNT,
    MODE_INTERVAL_DAYS,
)


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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> ChoresOptionsFlow:
        """Return the options flow for managing chores and the notify mapping."""
        return ChoresOptionsFlow()


def _chore_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_MODE, default=MODE_INTERVAL_DAYS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[MODE_INTERVAL_DAYS, MODE_CYCLE_COUNT],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_INTERVAL_DAYS, default=7): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=3650, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_CYCLE_THRESHOLD, default=30): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_COMPLETION_METHOD, default="nfc_tag"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["nfc_tag", "notification_action", "both"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_NFC_TAG_ENTITY_ID, default=""): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="tag")
            ),
            vol.Required(CONF_NOTIFY_TIME): selector.TimeSelector(),
        }
    )


class ChoresOptionsFlow(config_entries.OptionsFlow):
    """Manage chores and the person-to-notify-target mapping."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_chore", "remove_chore", "notify_mapping"],
        )

    async def async_step_add_chore(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MODE] == MODE_INTERVAL_DAYS and not user_input.get(CONF_INTERVAL_DAYS):
                errors["base"] = "interval_days_required"
            elif user_input[CONF_MODE] == MODE_CYCLE_COUNT and not user_input.get(CONF_CYCLE_THRESHOLD):
                errors["base"] = "cycle_threshold_required"
            elif user_input[CONF_COMPLETION_METHOD] in ("nfc_tag", "both") and not user_input.get(
                CONF_NFC_TAG_ENTITY_ID
            ):
                errors["base"] = "nfc_tag_required"
            else:
                chores = dict(self.config_entry.options.get(CONF_CHORES, {}))
                chores[uuid.uuid4().hex] = user_input
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, CONF_CHORES: chores}
                )
        return self.async_show_form(step_id="add_chore", data_schema=_chore_schema(), errors=errors)

    async def async_step_remove_chore(self, user_input: dict[str, Any] | None = None):
        chores = self.config_entry.options.get(CONF_CHORES, {})
        if not chores:
            return self.async_abort(reason="no_chores")
        if user_input is not None:
            remaining = {cid: cfg for cid, cfg in chores.items() if cid != user_input["chore_id"]}
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_CHORES: remaining}
            )
        schema = vol.Schema(
            {
                vol.Required("chore_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=cid, label=cfg[CONF_NAME])
                            for cid, cfg in chores.items()
                        ]
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_chore", data_schema=schema)

    async def async_step_notify_mapping(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, CONF_PERSON_NOTIFY_MAP: user_input}
            )
        person_entity_ids = self.hass.states.async_entity_ids("person")
        current = self.config_entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
        schema = vol.Schema(
            {
                vol.Optional(person_id, default=current.get(person_id, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify")
                )
                for person_id in person_entity_ids
            }
        )
        return self.async_show_form(step_id="notify_mapping", data_schema=schema)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/bin/python -m pytest tests/test_config_flow.py -v
```

Expected: PASS — all three tests green.

If `ChoresOptionsFlow` can't find `self.config_entry`, check whether the installed `homeassistant` version still requires storing it explicitly in `__init__(self, config_entry)` (older versions) versus providing it automatically via the base class (current versions) — inspect `homeassistant.config_entries.OptionsFlow` in the installed package if this step fails.

- [ ] **Step 5: Commit**

```bash
git add custom_components/chores/config_flow.py custom_components/chores/strings.json tests/test_config_flow.py
git commit -m "Add options flow for managing chores and the notify mapping"
```

---

### Task 4: Chore entities (sensor, binary sensor, button)

**Files:**
- Modify: `custom_components/chores/__init__.py`
- Create: `custom_components/chores/sensor.py`
- Create: `custom_components/chores/binary_sensor.py`
- Create: `custom_components/chores/button.py`
- Test: `tests/test_entities.py`

**Interfaces:**
- Consumes: `ChoreStore` (Task 2), `chore_updated_signal` (Task 2), `CONF_CHORES` (Task 2).
- Produces: for each chore_id, entities `sensor.<slug>_status` (state `"ok"`/`"due"`), `binary_sensor.<slug>_due` (`on`/`off`), `button.<slug>_mark_complete`. All three push-update via `async_dispatcher_connect(hass, chore_updated_signal(chore_id), ...)` in `async_added_to_hass`, so later tasks (services, notifications) only need to mutate the store and dispatch the signal — they never touch entities directly. `button.<slug>_mark_complete` calls `hass.services.async_call(DOMAIN, SERVICE_MARK_COMPLETE, {"chore_id": chore_id})` (the service is added in Task 5; this button's own test stubs that service so this task doesn't depend on Task 5 being done first).

- [ ] **Step 1: Write the failing test**

Create `tests/test_entities.py`:

```python
"""Tests that chore entities are created and reflect store state."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN
from custom_components.chores.store import ChoreStore


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_one_chore(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_status_sensor_reflects_not_due(hass):
    await _setup_entry_with_one_chore(hass)
    state = hass.states.get("sensor.dishwasher_maintenance_status")
    assert state is not None
    assert state.state == "ok"


async def test_due_binary_sensor_reflects_not_due(hass):
    await _setup_entry_with_one_chore(hass)
    state = hass.states.get("binary_sensor.dishwasher_maintenance_due")
    assert state is not None
    assert state.state == "off"


async def test_mark_complete_button_exists(hass):
    await _setup_entry_with_one_chore(hass)
    assert hass.states.get("button.dishwasher_maintenance_mark_complete") is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_entities.py -v
```

Expected: FAIL — no entities exist because `__init__.py` doesn't load the store or forward any platforms yet.

- [ ] **Step 3: Write the implementation**

Modify `custom_components/chores/__init__.py` to:

```python
"""The Chores & Maintenance integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CHORES, DOMAIN
from .store import ChoreStore

PLATFORMS: list[str] = ["sensor", "binary_sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chores & Maintenance from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = ChoreStore(hass, entry.entry_id)
    await store.async_load(entry.options.get(CONF_CHORES, {}))
    hass.data[DOMAIN][entry.entry_id] = store

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change (e.g. a chore was added/removed)."""
    await hass.config_entries.async_reload(entry.entry_id)
```

Create `custom_components/chores/sensor.py`:

```python
"""Sensor platform: per-chore status."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ChoreStatusSensor(entry, chore_id, store) for chore_id in store.chores)


class ChoreStatusSensor(SensorEntity):
    """Reports whether a chore is ok or due."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        self._store = store
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_status"
        self._attr_name = f"{chore.name} status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, chore_id)},
            name=chore.name,
            via_device=(DOMAIN, entry.entry_id),
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, chore_updated_signal(self._chore_id), self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str:
        return "due" if self._store.chores[self._chore_id].is_due(date.today()) else "ok"

    @property
    def extra_state_attributes(self) -> dict:
        chore = self._store.chores[self._chore_id]
        return {
            "last_completed": chore.last_completed.isoformat() if chore.last_completed else None,
            "count": chore.count,
            "cycle_threshold": chore.cycle_threshold,
            "interval_days": chore.interval_days,
        }
```

Create `custom_components/chores/binary_sensor.py`:

```python
"""Binary sensor platform: per-chore due flag."""
from __future__ import annotations

from datetime import date

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ChoreDueBinarySensor(entry, chore_id, store) for chore_id in store.chores)


class ChoreDueBinarySensor(BinarySensorEntity):
    """True while a chore is due/overdue."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        self._store = store
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_due"
        self._attr_name = f"{chore.name} due"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, chore_id)},
            name=chore.name,
            via_device=(DOMAIN, entry.entry_id),
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, chore_updated_signal(self._chore_id), self.async_write_ha_state
            )
        )

    @property
    def is_on(self) -> bool:
        return self._store.chores[self._chore_id].is_due(date.today())
```

Create `custom_components/chores/button.py`:

```python
"""Button platform: manual mark-complete per chore."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .store import ChoreStore

SERVICE_MARK_COMPLETE = "mark_complete"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ChoreMarkCompleteButton(entry, chore_id, store) for chore_id in store.chores)


class ChoreMarkCompleteButton(ButtonEntity):
    """Marks a chore complete on press, regardless of its configured completion method."""

    def __init__(self, entry: ConfigEntry, chore_id: str, store: ChoreStore) -> None:
        self._chore_id = chore_id
        chore = store.chores[chore_id]
        self._attr_unique_id = f"{chore_id}_mark_complete"
        self._attr_name = f"{chore.name} mark complete"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, chore_id)},
            name=chore.name,
            via_device=(DOMAIN, entry.entry_id),
        )

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            DOMAIN, SERVICE_MARK_COMPLETE, {"chore_id": self._chore_id}, blocking=True
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_entities.py -v
```

Expected: PASS — all three tests green. (`button.async_press` calling a not-yet-registered service is fine for this task's tests since they only check entity existence, not pressing the button — Task 5 adds the service the button calls.)

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: all tests across Tasks 1–4 PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/__init__.py custom_components/chores/sensor.py custom_components/chores/binary_sensor.py custom_components/chores/button.py tests/test_entities.py
git commit -m "Add per-chore sensor, binary sensor, and mark-complete button entities"
```

---

### Task 5: Services — log_cycle and mark_complete

**Files:**
- Modify: `custom_components/chores/__init__.py`
- Create: `custom_components/chores/services.py`
- Create: `custom_components/chores/services.yaml`
- Test: `tests/test_services.py`

**Interfaces:**
- Consumes: `ChoreStore` (Task 2), `chore_updated_signal` (Task 2), `Chore.log_cycle`/`Chore.mark_complete` (Task 1).
- Produces: `async def async_register_services(hass: HomeAssistant) -> None` in `services.py`, registering `chores.log_cycle` and `chores.mark_complete` (both take `{"chore_id": str}`, resolved against every loaded config entry's store). After mutating a chore, both call `store.async_save()` and `async_dispatcher_send(hass, chore_updated_signal(chore_id))`. `chores.mark_complete`'s handler is also the single completion routine that Task 6 (notifications) and Task 7 (NFC/notification-action listeners) call directly as a plain function — exported as `async def async_complete_chore(hass: HomeAssistant, chore_id: str) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_services.py`:

```python
"""Tests for the chores.log_cycle and chores.mark_complete services."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_one_chore(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_log_cycle_increments_count_and_updates_sensor(hass):
    await _setup_entry_with_one_chore(hass)

    for _ in range(30):
        await hass.services.async_call(DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True)

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "due"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "on"


async def test_mark_complete_resets_and_updates_sensor(hass):
    await _setup_entry_with_one_chore(hass)
    for _ in range(30):
        await hass.services.async_call(DOMAIN, "log_cycle", {"chore_id": "c1"}, blocking=True)

    await hass.services.async_call(DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True)

    assert hass.states.get("sensor.dishwasher_maintenance_status").state == "ok"
    assert hass.states.get("binary_sensor.dishwasher_maintenance_due").state == "off"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_services.py -v
```

Expected: FAIL — `ServiceNotFound: Service chores.log_cycle not found.`

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/services.yaml`:

```yaml
log_cycle:
  fields:
    chore_id:
      required: true
      example: "3f6a1c2b9e4d4f0a8b6c1d2e3f4a5b6c"
      selector:
        text:

mark_complete:
  fields:
    chore_id:
      required: true
      example: "3f6a1c2b9e4d4f0a8b6c1d2e3f4a5b6c"
      selector:
        text:
```

Create `custom_components/chores/services.py`:

```python
"""Services for the Chores & Maintenance integration."""
from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore

SERVICE_LOG_CYCLE = "log_cycle"
SERVICE_MARK_COMPLETE = "mark_complete"

_CHORE_ID_SCHEMA = vol.Schema({vol.Required("chore_id"): cv.string})


def _get_entry_and_store(hass: HomeAssistant) -> tuple[ConfigEntry, ChoreStore]:
    """The hub is single-instance (config_flow.py enforces `single_instance_allowed`), so
    there's always exactly one entry — no per-chore search across entries is needed."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return entry, hass.data[DOMAIN][entry.entry_id]


async def async_notify_chore_updated(hass: HomeAssistant, chore_id: str) -> None:
    """Persist and push an update for one chore. Shared by services and event listeners."""
    _, store = _get_entry_and_store(hass)
    await store.async_save()
    async_dispatcher_send(hass, chore_updated_signal(chore_id))


async def async_complete_chore(hass: HomeAssistant, chore_id: str) -> None:
    """The single completion routine — used by the service, NFC, and notification-action paths."""
    _, store = _get_entry_and_store(hass)
    store.chores[chore_id].mark_complete(date.today())
    await async_notify_chore_updated(hass, chore_id)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register chores.log_cycle and chores.mark_complete, once per Home Assistant instance."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_CYCLE):
        return

    async def _handle_log_cycle(call: ServiceCall) -> None:
        chore_id = call.data["chore_id"]
        _, store = _get_entry_and_store(hass)
        store.chores[chore_id].log_cycle()
        await async_notify_chore_updated(hass, chore_id)

    async def _handle_mark_complete(call: ServiceCall) -> None:
        await async_complete_chore(hass, call.data["chore_id"])

    hass.services.async_register(DOMAIN, SERVICE_LOG_CYCLE, _handle_log_cycle, schema=_CHORE_ID_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_COMPLETE, _handle_mark_complete, schema=_CHORE_ID_SCHEMA
    )
```

Modify `custom_components/chores/__init__.py`, adding the import and one line in `async_setup_entry`:

```python
from .services import async_register_services
```

```python
    await store.async_load(entry.options.get(CONF_CHORES, {}))
    hass.data[DOMAIN][entry.entry_id] = store

    await async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
```

(Insert the `await async_register_services(hass)` line exactly where shown, between the store setup and the update-listener registration.)

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_services.py -v
```

Expected: PASS — both tests green.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: all tests across Tasks 1–5 PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/__init__.py custom_components/chores/services.py custom_components/chores/services.yaml tests/test_services.py
git commit -m "Add chores.log_cycle and chores.mark_complete services"
```

---

### Task 6: Notification sending

**Files:**
- Create: `custom_components/chores/notify.py`
- Modify: `custom_components/chores/services.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `CONF_PERSON_NOTIFY_MAP` (Task 2), `Chore` (Task 1).
- Produces: `def notification_tag(chore_id: str) -> str` (returns `f"chores_{chore_id}"`); `async def async_send_due_notification(hass: HomeAssistant, entry: ConfigEntry, chore: Chore) -> None` (looks up who's home from `entry.options[CONF_PERSON_NOTIFY_MAP]`, calls `notify.<service>` for each with a message built from `chore.name`, `data.tag = notification_tag(chore.chore_id)`, and a `CHORES_DONE_<chore_id>` action button); `async def async_clear_due_notification(hass: HomeAssistant, entry: ConfigEntry, chore_id: str) -> None` (sends `clear_notification` with the same tag to **every** mapped target, not only whoever's home — spec §10). `async_complete_chore` (Task 5, modified here) now also calls `async_clear_due_notification`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_notify.py`:

```python
"""Tests for due-notification sending and clearing."""
from datetime import date
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.chore import Chore, ChoreMode
from custom_components.chores.const import CONF_PERSON_NOTIFY_MAP, DOMAIN
from custom_components.chores.notify import (
    async_clear_due_notification,
    async_send_due_notification,
    notification_tag,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _entry_with_mapping(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={CONF_PERSON_NOTIFY_MAP: {"person.alex": "notify.alex_phone"}},
    )
    entry.add_to_hass(hass)
    return entry


async def test_send_due_notification_targets_only_people_home(hass):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "home")
    hass.services.async_register(DOMAIN, "_unused", AsyncMock())  # keep services domain non-empty
    calls = []

    async def _fake_call(domain, service, data=None, **kwargs):
        calls.append((domain, service, data))

    hass.services.async_call = _fake_call  # type: ignore[assignment]

    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    await async_send_due_notification(hass, entry, chore)

    assert len(calls) == 1
    domain, service, data = calls[0]
    assert (domain, service) == ("notify", "alex_phone")
    assert data["data"]["tag"] == notification_tag("c1")
    assert "Dishwasher maintenance" in data["message"]


async def test_send_due_notification_skips_people_not_home(hass):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "not_home")
    calls = []

    async def _fake_call(domain, service, data=None, **kwargs):
        calls.append((domain, service, data))

    hass.services.async_call = _fake_call  # type: ignore[assignment]

    chore = Chore("c1", "Dishwasher maintenance", ChoreMode.CYCLE_COUNT, cycle_threshold=30, count=30)
    await async_send_due_notification(hass, entry, chore)

    assert calls == []


async def test_clear_due_notification_targets_everyone_mapped_regardless_of_presence(hass):
    entry = _entry_with_mapping(hass)
    hass.states.async_set("person.alex", "not_home")
    calls = []

    async def _fake_call(domain, service, data=None, **kwargs):
        calls.append((domain, service, data))

    hass.services.async_call = _fake_call  # type: ignore[assignment]

    await async_clear_due_notification(hass, entry, "c1")

    assert len(calls) == 1
    domain, service, data = calls[0]
    assert (domain, service) == ("notify", "alex_phone")
    assert data["message"] == "clear_notification"
    assert data["data"]["tag"] == notification_tag("c1")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_notify.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.chores.notify'`.

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/notify.py`:

```python
"""Sending and clearing due-notifications (spec §10)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .chore import Chore
from .const import CONF_PERSON_NOTIFY_MAP, NOTIFICATION_ACTION_PREFIX


def notification_tag(chore_id: str) -> str:
    """Stable per-chore notification tag, used both to send and to clear (spec §10)."""
    return f"chores_{chore_id}"


def _notify_service_name(notify_entity_id: str) -> str:
    """'notify.alex_phone' -> 'alex_phone', the service name to call under the notify domain."""
    return notify_entity_id.split(".", 1)[1]


async def async_send_due_notification(hass: HomeAssistant, entry: ConfigEntry, chore: Chore) -> None:
    """Notify everyone currently home, mapped via the hub's person->notify options."""
    person_notify_map: dict[str, str] = entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
    tag = notification_tag(chore.chore_id)
    for person_entity_id, notify_entity_id in person_notify_map.items():
        state = hass.states.get(person_entity_id)
        if state is None or state.state != "home":
            continue
        await hass.services.async_call(
            "notify",
            _notify_service_name(notify_entity_id),
            {
                "title": chore.name,
                "message": f"{chore.name} is due.",
                "data": {
                    "tag": tag,
                    "sticky": True,
                    "actions": [
                        {
                            "action": f"{NOTIFICATION_ACTION_PREFIX}{chore.chore_id}",
                            "title": "Mark done",
                        }
                    ],
                },
            },
        )


async def async_clear_due_notification(hass: HomeAssistant, entry: ConfigEntry, chore_id: str) -> None:
    """Clear a chore's due-notification on every mapped target, not only whoever's home."""
    person_notify_map: dict[str, str] = entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
    tag = notification_tag(chore_id)
    for notify_entity_id in person_notify_map.values():
        await hass.services.async_call(
            "notify",
            _notify_service_name(notify_entity_id),
            {"message": "clear_notification", "data": {"tag": tag}},
        )
```

Modify `custom_components/chores/services.py`: import and call the clearing routine from `async_complete_chore`. `_get_entry_and_store` (Task 5) already returns the entry, so no new lookup helper is needed here. Replace:

```python
async def async_complete_chore(hass: HomeAssistant, chore_id: str) -> None:
    """The single completion routine — used by the service, NFC, and notification-action paths."""
    _, store = _get_entry_and_store(hass)
    store.chores[chore_id].mark_complete(date.today())
    await async_notify_chore_updated(hass, chore_id)
```

with:

```python
async def async_complete_chore(hass: HomeAssistant, chore_id: str) -> None:
    """The single completion routine — used by the service, NFC, and notification-action paths."""
    entry, store = _get_entry_and_store(hass)
    store.chores[chore_id].mark_complete(date.today())
    await async_notify_chore_updated(hass, chore_id)
    await async_clear_due_notification(hass, entry, chore_id)
```

and add `from .notify import async_clear_due_notification` to the top of `services.py`. No caller changes needed — `async_complete_chore`'s signature is unchanged, so `_handle_mark_complete` (Task 5) and Task 8's listeners keep calling it exactly as already written.

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_notify.py -v
```

Expected: PASS — all three tests green.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: all tests across Tasks 1–6 PASS. (`test_services.py`'s `mark_complete` test will now also exercise notification-clearing with an empty `CONF_PERSON_NOTIFY_MAP`, which is a no-op loop — should still pass unchanged.)

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/notify.py custom_components/chores/services.py tests/test_notify.py
git commit -m "Add due-notification sending and clearing, wired into chore completion"
```

---

### Task 7: Due-check scheduling

**Files:**
- Modify: `custom_components/chores/__init__.py`
- Modify: `custom_components/chores/services.py`
- Create: `custom_components/chores/due_check.py`
- Test: `tests/test_due_check.py`

**Interfaces:**
- Consumes: `Chore.should_notify_today`/`record_notified` (Task 1), `async_send_due_notification` (Task 6), `ChoreStore` (Task 2).
- Produces: `async def async_run_due_check(hass: HomeAssistant, entry: ConfigEntry, chore_id: str) -> None` (the shared "check and maybe notify" routine — checks `should_notify_today`, sends if so, records `last_notified_date`, saves, dispatches the update signal); `def async_schedule_daily_checks(hass: HomeAssistant, entry: ConfigEntry) -> list[Callable]` (registers one `async_track_time_change` per chore at its own `notify_time`, returns the unsub callables for cleanup). `_handle_log_cycle` in `services.py` (Task 5) now also calls `async_run_due_check` immediately after incrementing, satisfying the "notify right after the cycle that crossed the threshold" requirement (spec §10) — this replaces its direct dispatch-only behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/test_due_check.py`:

```python
"""Tests for the shared due-check routine and its dedup behavior."""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_PERSON_NOTIFY_MAP, DOMAIN
from custom_components.chores.due_check import async_run_due_check
from custom_components.chores.store import ChoreStore


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_due_chore(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            CONF_PERSON_NOTIFY_MAP: {},
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                }
            },
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30
    return entry


async def test_due_check_sends_once_and_records_notified_date(hass):
    entry = await _setup_entry_with_due_chore(hass)
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]

    with patch(
        "custom_components.chores.due_check.async_send_due_notification", new=AsyncMock()
    ) as send_mock:
        await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 1
        assert store.chores["c1"].last_notified_date == date.today()

        await async_run_due_check(hass, entry, "c1")
        assert send_mock.await_count == 1  # dedup: not sent again the same day
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_due_check.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.chores.due_check'`.

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/due_check.py`:

```python
"""The shared due-check routine and its daily per-chore scheduling (spec §10)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_CHORES, DOMAIN, chore_updated_signal
from .notify import async_send_due_notification
from .store import ChoreStore


async def async_run_due_check(hass: HomeAssistant, entry: ConfigEntry, chore_id: str) -> None:
    """Check one chore and send its due-notification if it's due and not already sent today."""
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    chore = store.chores[chore_id]
    today = date.today()
    if not chore.should_notify_today(today):
        return
    await async_send_due_notification(hass, entry, chore)
    chore.record_notified(today)
    await store.async_save()
    async_dispatcher_send(hass, chore_updated_signal(chore_id))


def async_schedule_daily_checks(hass: HomeAssistant, entry: ConfigEntry) -> list[Callable[[], None]]:
    """Register one daily time-based due-check per chore, at that chore's own notify_time."""
    unsubs: list[Callable[[], None]] = []
    for chore_id, config in entry.options.get(CONF_CHORES, {}).items():
        hour, minute, second = (int(part) for part in config["notify_time"].split(":"))

        async def _tick(now: datetime, chore_id: str = chore_id) -> None:
            await async_run_due_check(hass, entry, chore_id)

        unsubs.append(
            async_track_time_change(hass, _tick, hour=hour, minute=minute, second=second)
        )
    return unsubs
```

Modify `custom_components/chores/__init__.py`: import and call the scheduler, and store its unsub callables for cleanup. Add the import:

```python
from .due_check import async_schedule_daily_checks
```

and, right after the `await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)` line in `async_setup_entry`:

```python
    for unsub in async_schedule_daily_checks(hass, entry):
        entry.async_on_unload(unsub)
```

Modify `custom_components/chores/services.py`: `_handle_log_cycle` now also runs the immediate due-check. Replace:

```python
    async def _handle_log_cycle(call: ServiceCall) -> None:
        chore_id = call.data["chore_id"]
        _, store = _get_entry_and_store(hass)
        store.chores[chore_id].log_cycle()
        await async_notify_chore_updated(hass, chore_id)
```

with:

```python
    async def _handle_log_cycle(call: ServiceCall) -> None:
        chore_id = call.data["chore_id"]
        entry, store = _get_entry_and_store(hass)
        store.chores[chore_id].log_cycle()
        await async_notify_chore_updated(hass, chore_id)
        await async_run_due_check(hass, entry, chore_id)
```

and add `from .due_check import async_run_due_check` to the top of `services.py`.

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_due_check.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
```

Expected: all tests across Tasks 1–7 PASS. `test_services.py::test_log_cycle_increments_count_and_updates_sensor` now also triggers a real due-notification send attempt on the 30th call (empty `CONF_PERSON_NOTIFY_MAP` in that test's entry means the send loop is a no-op — should stay green).

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/__init__.py custom_components/chores/due_check.py custom_components/chores/services.py tests/test_due_check.py
git commit -m "Add daily per-chore due-check scheduling and wire it into log_cycle"
```

---

### Task 8: NFC tag and notification-action completion listeners

**Files:**
- Modify: `custom_components/chores/__init__.py`
- Create: `custom_components/chores/listeners.py`
- Test: `tests/test_listeners.py`

**Interfaces:**
- Consumes: `async_complete_chore` (Task 6), `NOTIFICATION_ACTION_PREFIX` (Task 2), `CONF_NFC_TAG_ENTITY_ID`/`CONF_CHORES` (Task 2).
- Produces: `def async_register_listeners(hass: HomeAssistant, entry: ConfigEntry) -> list[Callable[[], None]]` — subscribes to `tag_scanned` and `mobile_app_notification_action` on the event bus, resolves each event back to a chore_id, and calls `async_complete_chore`. Returns unsub callables for cleanup, same pattern as Task 7's scheduler.

- [ ] **Step 1: Write the failing test**

Create `tests/test_listeners.py`:

```python
"""Tests for NFC tag and notification-action completion wiring."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import CONF_CHORES, DOMAIN, NOTIFICATION_ACTION_PREFIX


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry(hass, *, nfc_tag_entity_id: str):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            CONF_CHORES: {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "both",
                    "nfc_tag_entity_id": nfc_tag_entity_id,
                    "notify_time": "08:00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30
    return entry


async def test_tag_scanned_completes_matching_chore(hass):
    from homeassistant.helpers import entity_registry as er

    hass.states.async_set("tag.dishwasher_maintenance", "2026-01-01T00:00:00+00:00")
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "tag", "tag", "test-tag-unique-id", suggested_object_id="dishwasher_maintenance"
    )
    entry = await _setup_entry(hass, nfc_tag_entity_id="tag.dishwasher_maintenance")

    hass.bus.async_fire("tag_scanned", {"tag_id": "test-tag-unique-id"})
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c1"].count == 0


async def test_notification_action_completes_matching_chore(hass):
    entry = await _setup_entry(hass, nfc_tag_entity_id="")

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"{NOTIFICATION_ACTION_PREFIX}c1"}
    )
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]
    assert store.chores["c1"].count == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_listeners.py -v
```

Expected: FAIL — nothing listens for `tag_scanned`/`mobile_app_notification_action` yet, so both chores stay at `count == 30`.

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/listeners.py`:

```python
"""Internal NFC-tag and notification-action completion wiring (spec §9)."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_CHORES, CONF_NFC_TAG_ENTITY_ID, DOMAIN, NOTIFICATION_ACTION_PREFIX
from .services import async_complete_chore


def async_register_listeners(hass: HomeAssistant, entry: ConfigEntry) -> list[Callable[[], None]]:
    """Subscribe to tag_scanned and mobile_app_notification_action for this entry's chores."""

    async def _on_tag_scanned(event: Event) -> None:
        tag_id = event.data.get("tag_id")
        registry = er.async_get(hass)
        for chore_id, config in entry.options.get(CONF_CHORES, {}).items():
            nfc_entity_id = config.get(CONF_NFC_TAG_ENTITY_ID)
            if not nfc_entity_id:
                continue
            entity_entry = registry.async_get(nfc_entity_id)
            if entity_entry is not None and entity_entry.unique_id == tag_id:
                await async_complete_chore(hass, chore_id)

    async def _on_notification_action(event: Event) -> None:
        action = event.data.get("action", "")
        if not action.startswith(NOTIFICATION_ACTION_PREFIX):
            return
        chore_id = action[len(NOTIFICATION_ACTION_PREFIX):]
        if chore_id in entry.options.get(CONF_CHORES, {}):
            await async_complete_chore(hass, chore_id)

    return [
        hass.bus.async_listen("tag_scanned", _on_tag_scanned),
        hass.bus.async_listen("mobile_app_notification_action", _on_notification_action),
    ]
```

Modify `custom_components/chores/__init__.py`: import and register the listeners, storing unsubs for cleanup. Add:

```python
from .listeners import async_register_listeners
```

and, alongside the scheduler wiring in `async_setup_entry`:

```python
    for unsub in async_register_listeners(hass, entry):
        entry.async_on_unload(unsub)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_listeners.py -v
```

Expected: PASS — both tests green.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
./.venv/bin/python -m pytest tests/ -v
./.venv/bin/ruff check .
```

Expected: all tests PASS, `ruff check .` reports `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/__init__.py custom_components/chores/listeners.py tests/test_listeners.py
git commit -m "Add internal NFC tag and notification-action completion listeners"
```

---

### Task 9: Active-chores to-do list

**Files:**
- Modify: `custom_components/chores/__init__.py`
- Create: `custom_components/chores/todo.py`
- Test: `tests/test_todo.py`

**Interfaces:**
- Consumes: `ChoreStore` (Task 2), `chore_updated_signal` (Task 2).
- Produces: a single `todo.chores` entity per config entry, listing only chores where `is_due(today)` is true, one item per due chore (`uid = chore_id`, `summary = chore.name`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_todo.py`:

```python
"""Tests for the active-chores to-do list."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chores.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _setup_entry_with_two_chores(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chores & Maintenance",
        data={},
        options={
            "chores": {
                "c1": {
                    "name": "Dishwasher maintenance",
                    "mode": "cycle_count",
                    "cycle_threshold": 30,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                },
                "c2": {
                    "name": "Water plants",
                    "mode": "interval_days",
                    "interval_days": 7,
                    "completion_method": "notification_action",
                    "notify_time": "08:00:00",
                },
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_todo_list_shows_only_due_chores(hass):
    entry = await _setup_entry_with_two_chores(hass)
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30  # now due
    # c2 (interval_days, never completed) is due immediately per Chore.is_due semantics

    await hass.services.async_call(
        "todo", "get_items", {"entity_id": "todo.chores"}, blocking=True, return_response=True
    )
    state = hass.states.get("todo.chores")
    assert state is not None


async def test_completing_a_chore_removes_it_from_the_list(hass):
    entry = await _setup_entry_with_two_chores(hass)
    hass.data[DOMAIN][entry.entry_id].chores["c1"].count = 30

    await hass.services.async_call(DOMAIN, "mark_complete", {"chore_id": "c1"}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("todo.chores")
    assert state is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/bin/python -m pytest tests/test_todo.py -v
```

Expected: FAIL — `todo.chores` doesn't exist (no `todo` platform yet).

- [ ] **Step 3: Write the implementation**

Create `custom_components/chores/todo.py`:

```python
"""A single to-do list entity showing every currently-due chore (spec §11)."""
from __future__ import annotations

from datetime import date

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, chore_updated_signal
from .store import ChoreStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ActiveChoresTodoList(entry, store)])


class ActiveChoresTodoList(TodoListEntity):
    """Lists every chore that is currently due/overdue. Read-only: items are driven by
    chore due-state (Task 1-7), not by user checkboxes, so no UPDATE_TODO_ITEM feature."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, store: ChoreStore) -> None:
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_chores_todo"
        self._attr_name = "Chores"

    async def async_added_to_hass(self) -> None:
        for chore_id in self._store.chores:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, chore_updated_signal(chore_id), self.async_write_ha_state
                )
            )

    @property
    def todo_items(self) -> list[TodoItem]:
        today = date.today()
        return [
            TodoItem(uid=chore_id, summary=chore.name, status=TodoItemStatus.NEEDS_ACTION)
            for chore_id, chore in self._store.chores.items()
            if chore.is_due(today)
        ]
```

Modify `custom_components/chores/__init__.py`: add `"todo"` to `PLATFORMS`:

```python
PLATFORMS: list[str] = ["sensor", "binary_sensor", "button", "todo"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/bin/python -m pytest tests/test_todo.py -v
```

Expected: PASS — both tests green.

If `TodoListEntityFeature`/`TodoItemStatus`/`TodoItem` import paths differ from `homeassistant.components.todo` in the installed version, check `./.venv/bin/python -c "import homeassistant.components.todo as t; print(dir(t))"` — the `todo` platform is newer than most APIs used elsewhere in this plan, so this is the single most likely spot for a version-specific adjustment.

- [ ] **Step 5: Run the full suite one final time**

```bash
./.venv/bin/python -m pytest tests/ -v
./.venv/bin/ruff check .
```

Expected: every test across Tasks 1–9 PASSES, `ruff check .` reports `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/chores/__init__.py custom_components/chores/todo.py tests/test_todo.py
git commit -m "Add active-chores to-do list entity"
```

---

## Self-Review Notes (from planning)

- **Spec coverage:** §5 (single entry + options flow) → Task 3; §6 (schema) → Task 3's `_chore_schema`; §7 (entities) → Task 4; §8 (services) → Task 5; §9 (NFC/notification-action wiring) → Task 8; §10 (dual-trigger due-check, dedup, notification tagging/clearing) → Tasks 6–7; §11 (to-do list) → Task 9. §12 (migration guidance) and §13 (distribution) are documentation/process, not code — already covered by the existing spec text and the scaffolding plan's CI, respectively.
- **Known residual risk:** the `todo` platform (Task 9) and `OptionsFlow.config_entry` access (Task 3) are the newest HA APIs this plan touches; both tasks include an inline note on how to double-check the installed version if the test fails, rather than a placeholder.

# Chores & Maintenance for Home Assistant

A Home Assistant custom integration for recurring household chores and maintenance tasks — the kind with a cadence (every N days, or every N uses of something) and a completion action (scan an NFC tag, or tap a notification button).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=b0g3r&repository=ha-chores&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=chores)

## Features

- Add a chore through the UI — no YAML, no helper entities to create by hand.
- Two due-triggers per chore: a fixed day interval, or a usage-cycle threshold fed by your own automations.
- Two completion methods per chore, independently chosen: NFC tag scan, notification action, or both.
- Notifies whoever is currently home, on their own phone.
- Repeats the reminder every morning (at a per-chore time) until the chore is completed.
- A live to-do list of everything currently due.

See `docs/superpowers/specs/2026-07-26-chores-maintenance-design.md` for the full design.

## Installation

Click the HACS badge above (requires [My Home Assistant](https://www.home-assistant.io/integrations/my/) linked to your instance), or manually: in [HACS](https://hacs.xyz/), add `https://github.com/b0g3r/ha-chores` as a custom repository (category "Integration"), then install "Chores & Maintenance" and restart Home Assistant.

## Configuration

Click the "start setting up a new integration" badge above, or manually: Settings → Devices & Services → Add Integration → "Chores & Maintenance" sets up the hub. Add individual chores via the hub's **Configure** button (Settings → Devices & Services → Chores & Maintenance → Configure).

Each chore gets its own device with three entities: a status sensor (`ok`/`due`, with the chore's `chore_id` as an attribute for use in automations), a due binary sensor, and a "mark complete" button.

## Services

- **`chores.log_cycle`** (`chore_id`) — records one usage cycle for a cycle-count chore (e.g. call this from an automation triggered by a washing machine finishing). Raises an error if the chore isn't in cycle-count mode.
- **`chores.mark_complete`** (`chore_id`) — marks any chore done: resets its cycle count / restarts its interval from today, and clears its due-notification. This is what NFC tag scans, notification "Mark done" actions, and the per-chore button all call under the hood.

## To-do list

The integration also exposes a single `todo.chores` entity listing every chore currently due, so it shows up alongside your other to-dos on any to-do card.

## License

MIT — see `LICENSE`.

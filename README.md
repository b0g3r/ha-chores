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

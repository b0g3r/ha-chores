# Chores & Maintenance for Home Assistant — Design Spec

**Date:** 2026-07-26
**Status:** Approved for planning

## 1. Problem

Households accumulate recurring chores/maintenance tasks with different due-triggers (fixed calendar interval, usage-cycle threshold, or both) and different completion mechanisms (NFC tag scan, or a mobile notification action). The common DIY solution — power-sensor cycle-detection blueprints paired with hand-rolled helper counters and per-device NFC-tag automations — has real structural gaps (§3) and doesn't generalize to chores with no appliance/power-sensor behind them (e.g. watering a plant, a seasonal filter change). There is also no unified place to add a new chore or see what's currently due.

## 2. Goals

- Add a new chore (name, cadence, completion method) through a UI form — no YAML editing, no new helper entities per chore.
- Support two due-triggers per chore: fixed interval in days, or a cycle-count threshold fed by an external event.
- Support two completion methods per chore, chosen independently per chore: NFC tag scan, and/or a mobile notification action button.
- Notify only people currently home, on their own phone.
- For cycle-count chores: notify immediately when a completed cycle crosses the threshold, **and** keep re-notifying every morning (at a per-chore configurable time) until completed — both channels fire; this is not either/or.
- For interval chores: notify every morning from the due date until completed, then reschedule from the completion date.
- Provide a view of all currently-active (due/overdue) chores.

## 3. Non-Goals

- Detecting appliance cycles (power-sensor thresholds, start/end timing). That's a separate, already-well-served problem (community blueprints exist for it); this component only consumes a "cycle completed" signal via a service call — it does not produce one.
- Any "appliance finished, come unload it" style reminder — a different concern from maintenance cadence, out of scope.
- Configurable notification wording/templates, or a configurable default check time — deliberately cut; per-chore `notify_time` and a message auto-generated from the chore name are enough.
- A rich Lovelace dashboard — the v1 list view is the native HA to-do list (§10); a custom card is an explicit future option, not part of this build.

## 4. The Gap in the Common DIY Pattern

A common existing pattern looks like this: a power-sensor automation detects when an appliance cycle starts/ends, increments a `counter` helper on each completion, and — once the counter crosses a threshold — sends a notification and waits for an NFC tag scan (or a second automation on tag-scan) to reset the counter and clear the notification.

This pattern has two structural gaps that motivate this component:

1. **No repeat reminder.** The notification fires once, tied to the cycle-completion event. If it's dismissed or missed, nothing brings it back the next day — there's no independent "still not done" check.
2. **No generalization.** The counter/tag/notification wiring is duplicated by hand for every appliance, and doesn't extend at all to chores with no cycle signal (a weekly or quarterly task with nothing to count).

## 5. Architecture

A custom integration (`custom_components/chores/`, domain `chores`), distributed as a HACS custom repository. One integration, using HA's config-entry **subentries**:

- **Hub config entry** ("Chores & Maintenance", set up once): holds only the person → notify-target mapping. Nothing else global — no default check time, no default message template.
- **Chore subentries** (one per chore, added via "+ Add chore" under the hub, entirely through config-flow forms): each becomes its own HA device and owns its own schema (§6).

This gives every chore a device automatically (visible under Settings → Devices), and keeps "add a new chore" a UI action, not a code change.

## 6. Chore Schema

Each chore subentry stores:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Used to derive entity names and notification text. |
| `mode` | `interval_days` \| `cycle_count` | The due-trigger type. |
| `interval_days` | int | Required if `mode = interval_days`. |
| `cycle_threshold` | int | Required if `mode = cycle_count`. |
| `completion_method` | `nfc_tag` \| `notification_action` \| `both` | Independent per chore. |
| `nfc_tag_id` | tag selector | Required if `completion_method` includes `nfc_tag`. Dropdown of tags already registered in HA (Settings → Tags). |
| `notify_time` | time | Per-chore morning check time. No global default — set explicitly for every chore. |

State kept internally per chore (not user-configured): `count` (for cycle mode), `last_completed` (for interval mode), `last_notified_date` (dedup guard, see §9).

## 7. Entities per Chore

- `sensor.<chore>_status` — state `ok` / `due`; attributes: last completed date, next due date (interval mode) or current count/threshold (cycle mode).
- `binary_sensor.<chore>_due` — boolean form of the same, for templating/filtering.
- `button.<chore>_mark_complete` — manual completion, usable from any dashboard regardless of the chore's configured `completion_method`.

## 8. Services

Integration-wide, callable by any automation:

- `chores.log_cycle` (target: a chore subentry) — increments that chore's internal cycle count and immediately runs its due-check. No-op / logs a warning if called on an `interval_days` chore.
- `chores.mark_complete` (target: a chore subentry) — resets the chore (count → 0, or `last_completed` → now), computes the next due point, clears the due state, and clears any outstanding due-notification (§9).

Both are the single completion path used internally by §9 below.

## 9. NFC and Notification-Action Wiring

Both completion paths live inside the component — adding a chore never requires hand-writing an automation:

- **NFC:** the component subscribes to HA's `tag_scanned` event bus internally and matches `tag_id` against each chore's configured `nfc_tag_id`, then calls the same internal completion routine as `chores.mark_complete`.
- **Notification action:** each due-notification's "Mark done" action carries an ID encoding the chore's subentry (e.g. `CHORES_DONE_<subentry_id>`). The component listens for `mobile_app_notification_action` events, resolves the ID back to the chore, and calls the identical completion routine.

Because both funnel through one internal method, there is exactly one place that decides "what happens when a chore is completed."

## 10. Due-Detection and Notification Logic

A chore's due-check runs on two independent triggers, and **both fire when applicable — this is not either/or**:

1. **Cycle event** (cycle-mode chores only): immediately after `chores.log_cycle` increments the count, if `count >= cycle_threshold`, send the due-notification right away.
2. **Daily morning check** (all chores): at the chore's own `notify_time`, if the chore is currently due (cycle threshold still crossed, or `today >= last_completed + interval_days`) and not yet completed, send the due-notification again. This is what makes the reminder repeat every morning until scanned/acknowledged, independent of whether another cycle happens.

Both checks share one dedup rule: at most one notification per chore per calendar day (`last_notified_date`), so a cycle-event notification and the same day's morning check don't double-send — but the *next* morning always re-sends if still due, and a *new* cycle-completion later the same day would not re-send (already notified that day). On completion, the due state clears and both triggers go quiet until the chore becomes due again.

Notification recipients: every `person.*` in the hub's mapping whose state is currently `home`, sent to their mapped `notify.*` target (starting simple: everyone home gets notified; a per-chore override is a documented future extension, not built now).

**Notification tagging and clearing.** Every due-notification for a chore is sent with a stable, chore-specific `tag` (e.g. `chores_<subentry_id>`) — the Android/iOS mechanism for replacing an existing notification rather than stacking a new one. When a chore is completed (via NFC, notification action, or the manual button — all three funnel through the same completion routine, §9), that routine sends a `clear_notification` call using the chore's tag to **every** notify target in the hub's mapping, not only the ones currently home. This matters because the person who completes the chore isn't necessarily the only person who received the notification — e.g. one household member scans a tag while another's phone is still showing the sticky reminder; both must clear.

## 11. Active-Chores List View

The integration exposes a `todo.chores` entity. A chore's corresponding to-do item appears only while that chore is due/overdue, and is removed automatically on completion — so the list literally shows "active chores," using HA's native Tasks view / voice assistant / companion-app widget, with no custom dashboard work required.

(A richer custom Lovelace view showing *all* chores, including ones not yet due, with next-due countdowns, was considered and rejected for v1 as unnecessary — it's a clean fast-follow if the to-do list feels too thin once lived with.)

## 12. Adopting This Component Over an Existing Ad Hoc Setup

If you're migrating from the hand-rolled counter/tag pattern described in §4, the general recipe is:

- Create a chore subentry with `mode: cycle_count`, the appropriate `cycle_threshold`, `completion_method: nfc_tag`, and the existing tag reused as `nfc_tag_id` (no new physical tag needed).
- In whatever automation currently does `counter.increment` + a threshold check + a notify call on cycle completion, replace that block with a single call to `chores.log_cycle` targeting the new chore.
- Delete the old "tag scanned → reset counter, clear notification" automation — the integration's internal `tag_scanned` listener now owns that tag.
- Retire the old counter helper once the chore's internal count is confirmed working.

For a chore with no existing cycle-detection at all (a plain interval chore, e.g. a weekly or quarterly task), no migration is needed — just add a chore subentry with `mode: interval_days` and the appropriate `completion_method`.

## 13. Distribution & Testing

- Ships as a HACS custom repository: `custom_components/chores/manifest.json`, `config_flow: true`, `iot_class: local_push`.
- Unit tests around the due-detection state machine (interval math, cycle-threshold crossing, dedup-by-day) are the highest-value tests, independent of a running HA instance.
- Config-flow tests for hub setup and chore-subentry add/edit.
- Manual verification against a live instance for: tag-scan completion, notification-action completion, and the to-do list reflecting due/overdue state correctly.

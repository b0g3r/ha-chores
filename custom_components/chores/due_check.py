"""The shared due-check routine and its daily per-chore scheduling (spec §10)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHORES,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TIME,
    CONF_WEEKENDS_ONLY,
    DOMAIN,
    chore_updated_signal,
)
from .notify import async_send_due_notification
from .store import ChoreStore


async def async_run_due_check(
    hass: HomeAssistant, entry: ConfigEntry, chore_id: str
) -> None:
    """Send this chore's due-notification if it's due and not already sent today."""
    store: ChoreStore = hass.data[DOMAIN][entry.entry_id]
    chore = store.chores[chore_id]
    today = dt_util.now().date()
    if not chore.should_notify_today(today):
        return
    config = entry.options.get(CONF_CHORES, {}).get(chore_id, {})
    if config.get(CONF_WEEKENDS_ONLY) and today.weekday() < 5:
        return
    await async_send_due_notification(hass, entry, chore)
    chore.record_notified(today)
    await store.async_save()
    async_dispatcher_send(hass, chore_updated_signal(chore_id))


def async_schedule_daily_checks(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[Callable[[], None]]:
    """Register one daily due-check per chore that has reminders enabled, at that
    chore's own notify_time. Chores with reminders off get no scheduled check and
    send no push notifications; they still show up in the to-do list and sensors."""
    unsubs: list[Callable[[], None]] = []
    for chore_id, config in entry.options.get(CONF_CHORES, {}).items():
        if not config.get(CONF_NOTIFY_ENABLED) or not config.get(CONF_NOTIFY_TIME):
            continue
        hour, minute, second = (
            int(part) for part in config[CONF_NOTIFY_TIME].split(":")
        )

        async def _tick(now: datetime, chore_id: str = chore_id) -> None:
            await async_run_due_check(hass, entry, chore_id)

        unsubs.append(
            async_track_time_change(
                hass, _tick, hour=hour, minute=minute, second=second
            )
        )
    return unsubs

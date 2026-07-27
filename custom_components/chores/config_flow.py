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
    CONF_CYCLE_THRESHOLD,
    CONF_INTERVAL_DAYS,
    CONF_MESSAGE,
    CONF_MODE,
    CONF_NAME,
    CONF_NFC_ENABLED,
    CONF_NFC_TAG_ENTITY_ID,
    CONF_NOTIFICATION_ENABLED,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TIME,
    CONF_PERSON_NOTIFY_MAP,
    CONF_WEEKENDS_ONLY,
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
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ChoresOptionsFlow:
        """Return the options flow for managing chores and the notify mapping."""
        return ChoresOptionsFlow()


def _chore_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(
                CONF_MODE, default=MODE_INTERVAL_DAYS
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=MODE_INTERVAL_DAYS, label="Repeat every N days"
                        ),
                        selector.SelectOptionDict(
                            value=MODE_CYCLE_COUNT, label="Repeat every N uses"
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_INTERVAL_DAYS, default=7): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=3650, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(CONF_CYCLE_THRESHOLD, default=30): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10000, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_NFC_ENABLED, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_NFC_TAG_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="tag")
            ),
            vol.Required(
                CONF_NOTIFICATION_ENABLED, default=False
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ENABLED, default=False
            ): selector.BooleanSelector(),
            vol.Optional(CONF_NOTIFY_TIME): selector.TimeSelector(),
            vol.Required(
                CONF_WEEKENDS_ONLY, default=False
            ): selector.BooleanSelector(),
            vol.Optional(CONF_MESSAGE): str,
        }
    )


class ChoresOptionsFlow(config_entries.OptionsFlow):
    """Manage chores and the person-to-notify-target mapping."""

    _edit_chore_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_chore", "edit_chore", "remove_chore", "notify_mapping"],
        )

    async def async_step_add_chore(self, user_input: dict[str, Any] | None = None):
        """Add a new chore, or -- when async_step_edit_chore set _edit_chore_id --
        update that existing chore in place instead, keeping its chore_id (and thus
        its stored progress) rather than replacing it with a fresh one."""
        errors: dict[str, str] = {}
        chores = dict(self.config_entry.options.get(CONF_CHORES, {}))
        current = chores.get(self._edit_chore_id, {}) if self._edit_chore_id else {}
        if user_input is not None:
            if user_input[CONF_MODE] == MODE_INTERVAL_DAYS and not user_input.get(
                CONF_INTERVAL_DAYS
            ):
                errors["base"] = "interval_days_required"
            elif user_input[CONF_MODE] == MODE_CYCLE_COUNT and not user_input.get(
                CONF_CYCLE_THRESHOLD
            ):
                errors["base"] = "cycle_threshold_required"
            elif not user_input.get(CONF_NFC_ENABLED) and not user_input.get(
                CONF_NOTIFICATION_ENABLED
            ):
                errors["base"] = "completion_method_required"
            elif user_input.get(CONF_NFC_ENABLED) and not user_input.get(
                CONF_NFC_TAG_ENTITY_ID
            ):
                errors["base"] = "nfc_tag_required"
            elif user_input.get(CONF_NOTIFY_ENABLED) and not user_input.get(
                CONF_NOTIFY_TIME
            ):
                errors["base"] = "notify_time_required"
            else:
                chores[self._edit_chore_id or uuid.uuid4().hex] = user_input
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, CONF_CHORES: chores}
                )
        schema = _chore_schema()
        if current:
            schema = self.add_suggested_values_to_schema(schema, current)
        return self.async_show_form(
            step_id="add_chore",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "editing_note": f'Editing "{current[CONF_NAME]}".' if current else ""
            },
        )

    async def async_step_edit_chore(self, user_input: dict[str, Any] | None = None):
        chores = self.config_entry.options.get(CONF_CHORES, {})
        if not chores:
            return self.async_abort(reason="no_chores")
        if user_input is not None:
            self._edit_chore_id = user_input["chore_id"]
            return await self.async_step_add_chore()
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
        return self.async_show_form(step_id="edit_chore", data_schema=schema)

    async def async_step_remove_chore(self, user_input: dict[str, Any] | None = None):
        chores = self.config_entry.options.get(CONF_CHORES, {})
        if not chores:
            return self.async_abort(reason="no_chores")
        if user_input is not None:
            remaining = {
                cid: cfg for cid, cfg in chores.items() if cid != user_input["chore_id"]
            }
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
                title="",
                data={**self.config_entry.options, CONF_PERSON_NOTIFY_MAP: user_input},
            )
        person_entity_ids = self.hass.states.async_entity_ids("person")
        current = self.config_entry.options.get(CONF_PERSON_NOTIFY_MAP, {})
        schema = vol.Schema(
            {
                vol.Optional(person_id): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify")
                )
                for person_id in person_entity_ids
            }
        )
        return self.async_show_form(
            step_id="notify_mapping",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

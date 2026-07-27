"""Constants for the Chores & Maintenance integration."""

DOMAIN = "chores"

CONF_CHORES = "chores"
CONF_PERSON_NOTIFY_MAP = "person_notify_map"

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_INTERVAL_DAYS = "interval_days"
CONF_CYCLE_THRESHOLD = "cycle_threshold"
CONF_NFC_ENABLED = "nfc_enabled"
CONF_NFC_TAG_ENTITY_ID = "nfc_tag_entity_id"
CONF_NOTIFICATION_ENABLED = "notification_enabled"
CONF_NOTIFY_ENABLED = "notify_enabled"
CONF_NOTIFY_TIME = "notify_time"
CONF_WEEKENDS_ONLY = "weekends_only"
CONF_MESSAGE = "message"

MODE_INTERVAL_DAYS = "interval_days"
MODE_CYCLE_COUNT = "cycle_count"

NOTIFICATION_ACTION_PREFIX = "CHORES_DONE_"

SERVICE_LOG_CYCLE = "log_cycle"
SERVICE_MARK_COMPLETE = "mark_complete"


def chore_updated_signal(chore_id: str) -> str:
    """Dispatcher signal name fired whenever a chore's runtime state changes."""
    return f"{DOMAIN}_chore_updated_{chore_id}"

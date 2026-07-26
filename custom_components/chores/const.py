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

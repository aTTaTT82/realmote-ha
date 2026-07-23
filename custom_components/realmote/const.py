"""Konstanten fuer die RealMote-Integration."""

DOMAIN = "realmote"

CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_BASE_TOPIC = "base_topic"
CONF_IP = "ip"
CONF_FW = "fw"

DEFAULT_BASE_TOPIC = "realmote"
NUM_BUTTONS = 6

# Pro Taste konfigurierbare Felder
CONF_ENTITY = "entity"
CONF_ACTION = "action"
CONF_BRIGHTNESS = "brightness"
CONF_POSITION = "position"

# Aktionen (Werte werden auf HA-Services abgebildet, siehe __init__.run_button)
ACTIONS = ["toggle", "on", "off", "open", "close", "position"]

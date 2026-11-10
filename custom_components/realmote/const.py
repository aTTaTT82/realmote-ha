"""Konstanten fuer die RealMote-Integration."""

DOMAIN = "realmote"

CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_BASE_TOPIC = "base_topic"
CONF_IP = "ip"
CONF_FW = "fw"
CONF_ACTS = "acts"          # Activity-Namen aus dem Hub-Announce (Firmware >= 4.11.0)
CONF_BUILD = "build"        # Build-Nummer aus dem Announce (Firmware >= 4.19.1)
CONF_EIGEN = "eigen"        # eigene Tasten je Geraet aus realmote/<id>/tasten (Firmware >= 4.81.60)
CONF_GERAETE = "geraete"    # eingerichtete Geraete mit Namen aus realmote/<id>/geraete (Firmware >= 4.81.64)

# Optionen "Zustand aus Home Assistant" (v0.14.0): options[CONF_ZUSTAND][<geraet>] = {entity, nachfassen, schwelle}
CONF_ZUSTAND = "zustand"
CONF_NACHFASSEN = "nachfassen"
CONF_SCHWELLE = "schwelle"
DEFAULT_SCHWELLE = 15      # W -- darueber gilt ein Leistungs-Sensor als "an" (Fernseher im Standby: < 1 W)

# Signal, wenn ein neuer Announce eintrifft (Update-Entity haengt sich dran)
SIGNAL_ANNOUNCE = f"{DOMAIN}_announce"
LANG_HUB_DATA = f"{DOMAIN}_lang_hub"   # 0.14.3: je Eintrag die Tasten, die der Hub selbst lang belegt hat
KURZ_HUB_DATA = f"{DOMAIN}_kurz_hub"   # 0.14.4: dito kurz (Hub ab 4.81.80) -- nur fuer die Anzeige

DEFAULT_BASE_TOPIC = "realmote"
NUM_BUTTONS = 6
NUM_ACTIVITIES = 3

PLATFORMS = ["button", "event", "update", "select", "sensor"]

# Pro Taste konfigurierbare Felder
CONF_ENTITY = "entity"
CONF_ACTION = "action"
CONF_BRIGHTNESS = "brightness"
CONF_POSITION = "position"

# Aktionen (Werte werden auf HA-Services abgebildet, siehe __init__.run_button)
ACTIONS = ["toggle", "on", "off", "open", "close", "position"]

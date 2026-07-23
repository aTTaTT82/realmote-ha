"""Config- und Options-Flow fuer RealMote."""
from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ACTIONS,
    CONF_ACTION,
    CONF_BASE_TOPIC,
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_ENTITY,
    CONF_FW,
    CONF_IP,
    CONF_NAME,
    CONF_POSITION,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    NUM_BUTTONS,
)

# Nur fuer die Uebersicht/Anzeige (die echte Ausfuehrung mappt __init__.py)
ACTION_LABELS = {
    "toggle": "Umschalten",
    "on": "An",
    "off": "Aus",
    "open": "Öffnen",
    "close": "Schließen",
    "position": "Position",
}

# Emoji je Geraetetyp – macht die Uebersicht lebendiger
DOMAIN_EMOJI = {
    "light": "💡",
    "switch": "🔌",
    "cover": "🪟",
    "media_player": "🔊",
    "fan": "🌀",
    "scene": "🎬",
    "script": "▶️",
    "climate": "🌡️",
    "lock": "🔒",
    "vacuum": "🧹",
    "button": "🔘",
    "input_boolean": "🔀",
}


class RealMoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Hub hinzufuegen – automatisch per MQTT-Announce oder manuell."""

    VERSION = 1

    def __init__(self) -> None:
        self._disc: dict[str, Any] = {}

    async def async_step_mqtt(
        self, discovery_info: mqtt.MqttServiceInfo
    ) -> ConfigFlowResult:
        """Auto-Discovery: der Hub hat sein retained Announce gesendet."""
        try:
            data = json.loads(discovery_info.payload)
        except (ValueError, TypeError):
            return self.async_abort(reason="invalid_discovery")

        device_id = data.get("id")
        if not device_id:
            return self.async_abort(reason="invalid_discovery")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        self._disc = {
            CONF_DEVICE_ID: device_id,
            CONF_NAME: data.get("name", device_id),
            CONF_BASE_TOPIC: data.get("base", DEFAULT_BASE_TOPIC),
            CONF_IP: data.get("ip"),
            CONF_FW: data.get("fw"),
        }
        self.context["title_placeholders"] = {"name": self._disc[CONF_NAME]}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Gefundenen Hub bestaetigen."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._disc[CONF_NAME], data=self._disc
            )
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._disc[CONF_NAME],
                "id": self._disc[CONF_DEVICE_ID],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manuell hinzufuegen (Fallback, falls Auto-Discovery nicht greift)."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or device_id,
                data={
                    CONF_DEVICE_ID: device_id,
                    CONF_NAME: user_input.get(CONF_NAME) or device_id,
                    CONF_BASE_TOPIC: user_input.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
                },
            )
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): str,
                vol.Optional(CONF_NAME): str,
                vol.Optional(CONF_BASE_TOPIC, default=DEFAULT_BASE_TOPIC): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RealMoteOptionsFlow(config_entry)


class RealMoteOptionsFlow(OptionsFlow):
    """Tastenbelegung – pro Taste Geraet + Aktion (+ Helligkeit/Position)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)

    def _overview(self) -> str:
        """Kompakte Uebersicht aller 6 Tasten fuer die Menue-Beschreibung."""
        lines: list[str] = []
        for i in range(1, NUM_BUTTONS + 1):
            cfg = self._options.get(str(i))
            if cfg and cfg.get(CONF_ENTITY):
                ent = cfg[CONF_ENTITY]
                state = self.hass.states.get(ent)
                friendly = state.name if state else ent
                emoji = DOMAIN_EMOJI.get(ent.split(".")[0], "▫️")
                act = ACTION_LABELS.get(cfg.get(CONF_ACTION, "toggle"), cfg.get(CONF_ACTION))
                extra = ""
                if cfg.get(CONF_BRIGHTNESS) is not None:
                    extra = f" · {int(cfg[CONF_BRIGHTNESS])} %"
                elif cfg.get(CONF_POSITION) is not None:
                    extra = f" · {int(cfg[CONF_POSITION])} %"
                lines.append(f"{emoji}  **Taste {i}** — {friendly} → _{act}{extra}_")
            else:
                lines.append(f"⚪  **Taste {i}** — _frei_")
        return "\n".join(lines)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menue: welche Taste belegen? (oder Fertig). Zeigt die aktuelle Belegung."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[f"button_{i}" for i in range(1, NUM_BUTTONS + 1)] + ["finish"],
            description_placeholders={"overview": self._overview()},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._options)

    def __getattr__(self, name: str):
        """async_step_button_1 .. _6 auf einen gemeinsamen Handler routen."""
        if name.startswith("async_step_button_"):
            number = int(name.rsplit("_", 1)[1])

            async def _step(user_input: dict[str, Any] | None = None):
                return await self._configure_button(number, user_input)

            return _step
        raise AttributeError(name)

    async def _configure_button(
        self, number: int, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        if user_input is not None:
            cfg: dict[str, Any] = {}
            if user_input.get(CONF_ENTITY):
                cfg[CONF_ENTITY] = user_input[CONF_ENTITY]
            cfg[CONF_ACTION] = user_input.get(CONF_ACTION, "toggle")
            if user_input.get(CONF_BRIGHTNESS) is not None:
                cfg[CONF_BRIGHTNESS] = user_input[CONF_BRIGHTNESS]
            if user_input.get(CONF_POSITION) is not None:
                cfg[CONF_POSITION] = user_input[CONF_POSITION]
            if cfg.get(CONF_ENTITY):
                self._options[str(number)] = cfg
            else:
                self._options.pop(str(number), None)  # leeres Feld = Taste loeschen
            return await self.async_step_init()

        cur = self._options.get(str(number), {})
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENTITY,
                    description={"suggested_value": cur.get(CONF_ENTITY)},
                ): selector.EntitySelector(),
                vol.Optional(
                    CONF_ACTION,
                    description={"suggested_value": cur.get(CONF_ACTION, "toggle")},
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ACTIONS,
                        translation_key="action",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_BRIGHTNESS,
                    description={"suggested_value": cur.get(CONF_BRIGHTNESS)},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=100, step=1, unit_of_measurement="%"
                    )
                ),
                vol.Optional(
                    CONF_POSITION,
                    description={"suggested_value": cur.get(CONF_POSITION)},
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=100, step=1, unit_of_measurement="%"
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id=f"button_{number}",
            data_schema=schema,
            description_placeholders={"button": str(number)},
        )

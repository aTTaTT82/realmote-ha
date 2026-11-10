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
    LANG_HUB_DATA,
    ACTIONS,
    CONF_ACTION,
    CONF_BASE_TOPIC,
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_ENTITY,
    CONF_FW,
    CONF_GERAETE,
    CONF_IP,
    CONF_NACHFASSEN,
    CONF_NAME,
    CONF_POSITION,
    CONF_SCHWELLE,
    CONF_ZUSTAND,
    DEFAULT_BASE_TOPIC,
    DEFAULT_SCHWELLE,
    DOMAIN,
    NUM_BUTTONS,
)

# Fuer "Zustand aus Home Assistant", falls der Hub (Firmware < 4.81.64) seine Geraeteliste nicht meldet
GERAETE_VORGABE = [
    {"g": "tv", "n": "Fernseher"},
    {"g": "soundbar", "n": "Soundbar / AV-Receiver"},
    {"g": "receiver", "n": "Sat/Kabel-Receiver"},
    {"g": "android", "n": "Android TV"},
]
# Entitaeten, die einen Ein/Aus-Zustand haben (sensor: Leistung in W mit Schwelle)
ZUSTAND_DOMAINS = ["media_player", "switch", "binary_sensor", "input_boolean", "light", "fan", "remote", "sensor"]

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
    """Tastenbelegung – je Taste eine KURZ- und eine LANG-Aktion (12 Slots)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)
        self._pending: tuple[int, bool] = (1, False)  # (Tastennummer, lang?)
        self._zg: str = "tv"                            # Geraet fuer "Zustand aus Home Assistant"

    def _fmt(self, key: str, num: int) -> str:
        """Eine Uebersichtszeile fuer einen Slot (kurz: "1", lang: "1h")."""
        cfg = self._options.get(key)
        if cfg and cfg.get(CONF_ENTITY):
            ent = cfg[CONF_ENTITY]
            state = self.hass.states.get(ent)
            friendly = state.name if state else ent
            ent_domain = ent.split(".")[0]
            emoji = DOMAIN_EMOJI.get(ent_domain, "▫️")
            if ent_domain in ("scene", "script", "button"):
                # Diese Typen haben genau eine Aktion (siehe _run_button)
                act = "Aktivieren"
            else:
                act = ACTION_LABELS.get(cfg.get(CONF_ACTION, "toggle"), cfg.get(CONF_ACTION))
            extra = ""
            if cfg.get(CONF_BRIGHTNESS) is not None:
                extra = f" {int(cfg[CONF_BRIGHTNESS])} %"
            elif cfg.get(CONF_POSITION) is not None:
                extra = f" {int(cfg[CONF_POSITION])} %"
            return f"{emoji} **{num}** {friendly} → _{act}{extra}_"
        # 0.14.2/0.14.3: ein freies "lang halten" wirkt wie kurz tippen (_run_button) -- aber nur, wenn der Hub gemeldet
        # hat, dass er dafuer selbst kein Lang-Topic hat. Die Uebersicht sagt, was wirklich passiert.
        if key.endswith("h"):
            lang_hub = self.hass.data.get(LANG_HUB_DATA, {}).get(self._entry.entry_id)
            if lang_hub is not None and num in lang_hub:
                return f"🏠 **{num}** _im Hub belegt_"
            kurz = self._options.get(str(num))
            if lang_hub is not None and kurz and kurz.get(CONF_ENTITY):
                return f"↩️ **{num}** _wie kurz tippen_"
        return f"⚪ **{num}** _frei_"

    def _overview(self) -> str:
        short = "\n".join(self._fmt(str(i), i) for i in range(1, NUM_BUTTONS + 1))
        long = "\n".join(self._fmt(f"{i}h", i) for i in range(1, NUM_BUTTONS + 1))
        text = f"**Kurz tippen:**\n{short}\n\n**Lang halten:**\n{long}"
        zustand = self._options.get(CONF_ZUSTAND) or {}
        if zustand:
            namen = {d["g"]: d["n"] for d in self._geraete()}
            zeilen = []
            for g, cfg in zustand.items():
                state = self.hass.states.get(cfg.get(CONF_ENTITY, ""))
                friendly = state.name if state else cfg.get(CONF_ENTITY)
                extra = " · nachfassen" if cfg.get(CONF_NACHFASSEN) else ""
                zeilen.append(f"🔌 **{namen.get(g, g)}** ← {friendly}{extra}")
            text += "\n\n**Zustand aus Home Assistant:**\n" + "\n".join(zeilen)
        return text

    def _geraete(self) -> list[dict]:
        """Die Geraete des Hubs (aus seiner Meldung), sonst die vier festen."""
        roh = self._entry.data.get(CONF_GERAETE)
        if isinstance(roh, list):
            liste = [d for d in roh if isinstance(d, dict) and isinstance(d.get("g"), str) and d["g"]]
            if liste:
                return [{"g": d["g"], "n": str(d.get("n") or d["g"])} for d in liste]
        return GERAETE_VORGABE

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menue: welchen Slot belegen? (kurz 1-6, lang 1-6, oder Fertig)."""
        return self.async_show_menu(
            step_id="init",
            menu_options=(
                [f"button_{i}" for i in range(1, NUM_BUTTONS + 1)]
                + [f"hold_{i}" for i in range(1, NUM_BUTTONS + 1)]
                + ["zustand", "finish"]
            ),
            description_placeholders={"overview": self._overview()},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._options)

    async def async_step_zustand(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zustand aus Home Assistant: erst das Geraet des Hubs waehlen (v0.14.0)."""
        if user_input is not None:
            self._zg = user_input["geraet"]
            return await self.async_step_zustand_assign()
        zustand = self._options.get(CONF_ZUSTAND) or {}
        optionen = []
        for d in self._geraete():
            cfg = zustand.get(d["g"])
            label = d["n"] + (f"  ←  {cfg[CONF_ENTITY]}" if cfg and cfg.get(CONF_ENTITY) else "")
            optionen.append(selector.SelectOptionDict(value=d["g"], label=label))
        schema = vol.Schema(
            {
                vol.Required("geraet", default=optionen[0]["value"]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=optionen, mode=selector.SelectSelectorMode.LIST)
                )
            }
        )
        return self.async_show_form(step_id="zustand", data_schema=schema)

    async def async_step_zustand_assign(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entitaet mit dem echten Zustand fuer das gewaehlte Geraet; leer = Zuordnung loeschen."""
        g = self._zg
        zustand = dict(self._options.get(CONF_ZUSTAND) or {})
        if user_input is not None:
            if user_input.get(CONF_ENTITY):
                zustand[g] = {
                    CONF_ENTITY: user_input[CONF_ENTITY],
                    CONF_NACHFASSEN: bool(user_input.get(CONF_NACHFASSEN, False)),
                    CONF_SCHWELLE: float(user_input.get(CONF_SCHWELLE, DEFAULT_SCHWELLE)),
                }
            else:
                zustand.pop(g, None)
            if zustand:
                self._options[CONF_ZUSTAND] = zustand
            else:
                self._options.pop(CONF_ZUSTAND, None)
            return await self.async_step_init()

        cur = zustand.get(g, {})
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENTITY, description={"suggested_value": cur.get(CONF_ENTITY)}
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain=ZUSTAND_DOMAINS)),
                vol.Optional(
                    CONF_NACHFASSEN, default=bool(cur.get(CONF_NACHFASSEN, False))
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SCHWELLE, default=cur.get(CONF_SCHWELLE, DEFAULT_SCHWELLE)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=500, step=1, unit_of_measurement="W")
                ),
            }
        )
        name = next((d["n"] for d in self._geraete() if d["g"] == g), g)
        return self.async_show_form(
            step_id="zustand_assign", data_schema=schema, description_placeholders={"geraet": name}
        )

    def __getattr__(self, name: str):
        """Menue-Eintraege button_1..6 (kurz) + hold_1..6 (lang) auf ein Formular routen."""
        for prefix, is_hold in (("async_step_button_", False), ("async_step_hold_", True)):
            if name.startswith(prefix):
                number = int(name.rsplit("_", 1)[1])

                async def _step(user_input: dict[str, Any] | None = None,
                                _n: int = number, _h: bool = is_hold):
                    self._pending = (_n, _h)
                    return await self.async_step_assign()

                return _step
        raise AttributeError(name)

    async def async_step_assign(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Gemeinsames Formular fuer den gewaehlten Slot (self._pending)."""
        number, hold = self._pending
        key = f"{number}h" if hold else str(number)

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
                self._options[key] = cfg
            else:
                self._options.pop(key, None)  # leeres Feld = Slot loeschen
            return await self.async_step_init()

        cur = self._options.get(key, {})
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
        label = f"Taste {number} " + ("(lang halten)" if hold else "(kurz tippen)")
        return self.async_show_form(
            step_id="assign",
            data_schema=schema,
            description_placeholders={"label": label},
        )

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
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    KURZ_HUB_DATA,
    LANG_HUB_DATA,
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

# Die Tasten heissen wie auf der Fernbedienung (I-VI)
ROEMISCH = ["I", "II", "III", "IV", "V", "VI"]

# Diese Typen haben genau eine Aktion, die Wahl der Aktion entfaellt (so fuehrt sie __init__._run_button aus)
EINE_AKTION = {"scene": "scene", "script": "script", "button": "button"}

# 0.15.0: nur die Aktionen, die zum Typ passen (Werte wie bisher, __init__._run_button bildet sie ab)
AKTIONEN_JE_TYP = {
    "light": ["toggle", "on", "off"],
    "cover": ["toggle", "open", "close", "position"],
}
AKTIONEN_SONST = ["toggle", "on", "off"]

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

# Was der Dialog in Platzhalter einsetzt (der feste Text steht in translations/*.json)
VERBEN = {
    "de": {"toggle": "umschalten", "on": "an", "on_p": "an mit {p} %", "off": "aus",
           "open": "öffnen", "close": "schließen", "position": "auf {p} %"},
    "en": {"toggle": "toggle", "on": "on", "on_p": "on at {p} %", "off": "off",
           "open": "open", "close": "close", "position": "to {p} %"},
}
TEXTE = {
    "de": {
        "frei": "frei",
        "noch_frei": "noch frei",
        "wie_kurz": "wie kurz",
        "im_hub": "🏠 im Hub belegt",
        "auch_hub": "⚠️ auch im Hub belegt",
        "kurz": "kurz",
        "lang": "lang",
        "beide": "kurz und lang",
        "zustand_leer": "noch nichts zugeordnet",
        "was_kurz": "kurz tippen",
        "was_lang": "lang halten",
        "und": " und ",
        "hub_hinweis": "\n\n🏠 **Im Hub belegt: {was}** (Konfiguration → Smart-Home-Tasten). "
                       "Belegst du das hier auch, laufen beide.",
        "leer_nicht": "Leer = nicht belegt",
        "leer_hub": "Leer = nur die Belegung im Hub",
        "leer_wie_kurz": "Leer = macht dasselbe wie kurz tippen",
        "scene": "{e} **{n}** ({wo}) ist eine Szene, die wird immer aktiviert.",
        "script": "{e} **{n}** ({wo}) ist ein Skript, das wird immer ausgeführt.",
        "button": "{e} **{n}** ({wo}) ist ein Knopf, der wird immer gedrückt.",
    },
    "en": {
        "frei": "free",
        "noch_frei": "not assigned yet",
        "wie_kurz": "same as tap",
        "im_hub": "🏠 set in the hub",
        "auch_hub": "⚠️ also set in the hub",
        "kurz": "tap",
        "lang": "hold",
        "beide": "tap and hold",
        "zustand_leer": "nothing assigned yet",
        "was_kurz": "tap",
        "was_lang": "hold",
        "und": " and ",
        "hub_hinweis": "\n\n🏠 **Set in the hub: {was}** (Configuration → Smart home keys). "
                       "If you assign it here as well, both run.",
        "leer_nicht": "Empty = not assigned",
        "leer_hub": "Empty = only the hub's assignment",
        "leer_wie_kurz": "Empty = same as tapping",
        "scene": "{e} **{n}** ({wo}) is a scene, it is always activated.",
        "script": "{e} **{n}** ({wo}) is a script, it always runs.",
        "button": "{e} **{n}** ({wo}) is a button, it is always pressed.",
    },
}


def _typ(entity_id: str) -> str:
    return entity_id.split(".")[0]


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
    """Tastenbelegung – je Taste eine KURZ- und eine LANG-Aktion (Optionen "1".."6" und "1h".."6h").

    0.15.0 (Anwender 10.11.: "Das sieht echt müllig aus"): Startseite mit den sechs Tasten I-VI und ihrer Belegung,
    je Taste ein Formular fuer kurz und lang, danach nur die Aktionen, die zum Typ passen. Die gespeicherten
    Optionen haben dasselbe Format wie vorher -- alte Belegungen gelten weiter.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)
        self._taste: int = 1                              # die Taste, die gerade bearbeitet wird
        self._entwurf: dict[str, dict | None] = {}        # Slot -> neue Belegung (None = loeschen), bis "Uebernehmen"
        self._zg: str = "tv"                              # Geraet fuer "Zustand aus Home Assistant"

    # ---------- Hilfen ----------

    @property
    def _sprache(self) -> str:
        return "de" if str(self.hass.config.language or "").startswith("de") else "en"

    @property
    def _t(self) -> dict[str, str]:
        return TEXTE[self._sprache]

    def _hub(self, ablage: str) -> set | None:
        """Was der Hub selbst belegt hat (aus .../lang_hub bzw. .../kurz_hub), None = er meldet es nicht (aelter)."""
        return self.hass.data.get(ablage, {}).get(self._entry.entry_id)

    def _im_hub(self, num: int, lang: bool) -> bool:
        hub = self._hub(LANG_HUB_DATA if lang else KURZ_HUB_DATA)
        return hub is not None and num in hub

    def _name(self, entity_id: str) -> str:
        """Emoji und Name einer Entitaet, z. B. "💡 Stehlampe"."""
        state = self.hass.states.get(entity_id)
        friendly = state.name if state else entity_id
        return f"{DOMAIN_EMOJI.get(_typ(entity_id), '▫️')} {friendly}"

    def _beschreibung(self, cfg: dict) -> str:
        """Eine Belegung in Worten, z. B. "💡 Stehlampe umschalten" (Szene, Skript, Knopf: nur der Name)."""
        ent = cfg[CONF_ENTITY]
        typ = _typ(ent)
        if typ in EINE_AKTION:
            return self._name(ent)
        verben = VERBEN[self._sprache]
        act = cfg.get(CONF_ACTION, "toggle")
        if act == "on" and typ == "light" and cfg.get(CONF_BRIGHTNESS) is not None:
            verb = verben["on_p"].format(p=int(cfg[CONF_BRIGHTNESS]))
        elif act == "position":
            verb = verben["position"].format(p=int(cfg.get(CONF_POSITION, 0)))
        else:
            verb = verben.get(act, act)
        return f"{self._name(ent)} {verb}"

    def _slot_text(self, num: int, lang: bool) -> str:
        """Was auf einem Slot liegt: Belegung hier, im Hub, "wie kurz" oder frei."""
        t = self._t
        cfg = self._options.get(f"{num}h" if lang else str(num)) or {}
        im_hub = self._im_hub(num, lang)
        if cfg.get(CONF_ENTITY):
            # 0.14.4 (Anwender 10.11.: Taste 1 war kurz hier UND im Hub belegt, ein Druck schaltete zwei Lampen)
            text = self._beschreibung(cfg)
            return f"{text} {t['auch_hub']}" if im_hub else text
        if im_hub:
            return t["im_hub"]
        # 0.14.2/0.14.3: ein freies "lang halten" wirkt wie kurz tippen -- wenn die Taste kurz belegt ist (hier oder im
        # Hub) und nirgends lang. Das sagt der Dialog nur, wenn der Hub seine Belegung meldet (sonst ist es offen).
        if lang and self._hub(LANG_HUB_DATA) is not None:
            kurz = self._options.get(str(num)) or {}
            if kurz.get(CONF_ENTITY) or self._im_hub(num, False):
                return t["wie_kurz"]
        return t["frei"]

    def _zeile(self, num: int) -> str:
        """Zweite Zeile einer Taste auf der Startseite (reiner Text, kein Markdown)."""
        t = self._t
        kurz, lang = self._slot_text(num, False), self._slot_text(num, True)
        if kurz == t["frei"] and lang == t["frei"]:
            return t["noch_frei"]
        if kurz == lang:
            return f"{t['beide']}: {kurz}"
        return f"{t['kurz']}: {kurz} · {t['lang']}: {lang}"

    def _zustand_zeile(self) -> str:
        zustand = self._options.get(CONF_ZUSTAND) or {}
        if not zustand:
            return self._t["zustand_leer"]
        namen = {d["g"]: d["n"] for d in self._geraete()}
        teile = []
        for g, cfg in zustand.items():
            state = self.hass.states.get(cfg.get(CONF_ENTITY, ""))
            friendly = state.name if state else cfg.get(CONF_ENTITY)
            teile.append(f"{namen.get(g, g)} ← {friendly}")
        return " · ".join(teile)

    def _geraete(self) -> list[dict]:
        """Die Geraete des Hubs (aus seiner Meldung), sonst die vier festen."""
        roh = self._entry.data.get(CONF_GERAETE)
        if isinstance(roh, list):
            liste = [d for d in roh if isinstance(d, dict) and isinstance(d.get("g"), str) and d["g"]]
            if liste:
                return [{"g": d["g"], "n": str(d.get("n") or d["g"])} for d in liste]
        return GERAETE_VORGABE

    def _slots(self) -> tuple[tuple[str, str, bool], ...]:
        """Die beiden Slots der bearbeiteten Taste: (Optionsschluessel, Feld/Abschnitt, lang?)."""
        n = self._taste
        return ((str(n), "kurz", False), (f"{n}h", "lang", True))

    def _entwurf_uebernehmen(self) -> None:
        for slot, cfg in self._entwurf.items():
            if cfg:
                self._options[slot] = cfg
            else:
                self._options.pop(slot, None)  # leeres Feld = Slot loeschen
        self._entwurf = {}

    # ---------- Startseite ----------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Startseite: die sechs Tasten mit ihrer Belegung, Zustand der Geraete, Speichern."""
        platzhalter = {f"t{n}": self._zeile(n) for n in range(1, NUM_BUTTONS + 1)}
        platzhalter["zustand"] = self._zustand_zeile()
        return self.async_show_menu(
            step_id="init",
            menu_options=[f"taste_{n}" for n in range(1, NUM_BUTTONS + 1)] + ["zustand", "finish"],
            description_placeholders=platzhalter,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._options)

    def __getattr__(self, name: str):
        """Menue-Eintraege taste_1..taste_6 auf das Formular der Taste routen."""
        prefix = "async_step_taste_"
        if name.startswith(prefix):
            rest = name[len(prefix):]
            if rest.isdigit() and 1 <= int(rest) <= NUM_BUTTONS:
                async def _step(user_input: dict[str, Any] | None = None, _n: int = int(rest)):
                    self._taste = _n
                    return await self.async_step_taste()

                return _step
        raise AttributeError(name)

    # ---------- Eine Taste: kurz und lang ----------

    async def async_step_taste(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Was die Taste schaltet, kurz und lang in einem Formular."""
        t = self._t
        n = self._taste
        if user_input is not None:
            self._entwurf = {}
            for slot, feld, _lang in self._slots():
                ent = user_input.get(feld)
                if not ent:
                    self._entwurf[slot] = None
                    continue
                alt = self._options.get(slot) or {}
                # Dieselbe Entitaet: ihre Aktion bleibt die Vorgabe; eine neue beginnt mit "Umschalten"
                self._entwurf[slot] = dict(alt) if alt.get(CONF_ENTITY) == ent else {
                    CONF_ENTITY: ent, CONF_ACTION: "toggle"}
            if any(cfg and _typ(cfg[CONF_ENTITY]) not in EINE_AKTION for cfg in self._entwurf.values()):
                return await self.async_step_aktion()
            self._entwurf_uebernehmen()
            return await self.async_step_init()

        was = [t["was_lang" if lang else "was_kurz"] for _s, _f, lang in self._slots() if self._im_hub(n, lang)]
        hinweis = t["hub_hinweis"].format(was=t["und"].join(was)) if was else ""
        if self._im_hub(n, True):
            lang_leer = t["leer_hub"]
        elif self._hub(LANG_HUB_DATA) is not None:
            lang_leer = t["leer_wie_kurz"]
        else:
            lang_leer = t["leer_nicht"]
        schema = vol.Schema(
            {
                vol.Optional(
                    feld, description={"suggested_value": (self._options.get(slot) or {}).get(CONF_ENTITY)}
                ): selector.EntitySelector()
                for slot, feld, _lang in self._slots()
            }
        )
        return self.async_show_form(
            step_id="taste",
            data_schema=schema,
            last_step=False,
            description_placeholders={
                "nr": ROEMISCH[n - 1],
                "hinweis": hinweis,
                "kurz_leer": t["leer_hub"] if self._im_hub(n, False) else t["leer_nicht"],
                "lang_leer": lang_leer,
            },
        )

    async def async_step_aktion(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nur die Aktionen, die zum Typ passen; Helligkeit nur bei Lampen, Position nur bei Rollos."""
        t = self._t
        teile = [(slot, feld, lang, cfg) for slot, feld, lang in self._slots()
                 if (cfg := self._entwurf.get(slot)) and _typ(cfg[CONF_ENTITY]) not in EINE_AKTION]
        errors: dict[str, str] = {}
        werte: dict[str, dict] = {feld: cfg for _s, feld, _l, cfg in teile}

        if user_input is not None:
            neu: dict[str, dict] = {}
            for slot, feld, _lang, cfg in teile:
                eingabe = user_input.get(feld) or {}
                ent = cfg[CONF_ENTITY]
                typ = _typ(ent)
                act = eingabe.get(CONF_ACTION) or "toggle"
                belegung: dict[str, Any] = {CONF_ENTITY: ent, CONF_ACTION: act}
                # Helligkeit wirkt nur bei "An", Position nur bei "Auf Position fahren" (__init__._run_button)
                if typ == "light" and act == "on" and eingabe.get(CONF_BRIGHTNESS) is not None:
                    belegung[CONF_BRIGHTNESS] = int(eingabe[CONF_BRIGHTNESS])
                if act == "position":
                    if eingabe.get(CONF_POSITION) is None:
                        errors["base"] = "position_fehlt"
                    else:
                        belegung[CONF_POSITION] = int(eingabe[CONF_POSITION])
                neu[slot] = belegung
                werte[feld] = {**eingabe, CONF_ENTITY: ent}
            if not errors:
                self._entwurf.update(neu)
                self._entwurf_uebernehmen()
                return await self.async_step_init()

        felder: dict[Any, Any] = {}
        for _slot, feld, _lang, cfg in teile:
            typ = _typ(cfg[CONF_ENTITY])
            wahl = AKTIONEN_JE_TYP.get(typ, AKTIONEN_SONST)
            w = werte[feld]
            innen: dict[Any, Any] = {
                vol.Required(
                    CONF_ACTION, default=w.get(CONF_ACTION) if w.get(CONF_ACTION) in wahl else "toggle"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=wahl, translation_key="action", mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
            if typ == "light":
                innen[vol.Optional(CONF_BRIGHTNESS, description={"suggested_value": w.get(CONF_BRIGHTNESS)})] = (
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=1, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)))
            if typ == "cover":
                innen[vol.Optional(CONF_POSITION, description={"suggested_value": w.get(CONF_POSITION)})] = (
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=0, max=100, step=1, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER)))
            felder[vol.Required(feld)] = section(vol.Schema(innen), {"collapsed": False})

        zeilen = []
        for _slot, feld, lang in self._slots():
            cfg = self._entwurf.get(_slot)
            if cfg and (typ := _typ(cfg[CONF_ENTITY])) in EINE_AKTION:
                state = self.hass.states.get(cfg[CONF_ENTITY])
                zeilen.append(t[EINE_AKTION[typ]].format(
                    e=DOMAIN_EMOJI.get(typ, "▫️"), n=state.name if state else cfg[CONF_ENTITY],
                    wo=t["lang" if lang else "kurz"]))
        namen = {feld: self._name(cfg[CONF_ENTITY]) for _s, feld, _l, cfg in teile}
        return self.async_show_form(
            step_id="aktion",
            data_schema=vol.Schema(felder),
            errors=errors,
            description_placeholders={
                "nr": ROEMISCH[self._taste - 1],
                "hinweis": "\n".join(zeilen),
                "kurz_name": namen.get("kurz", ""),
                "lang_name": namen.get("lang", ""),
            },
        )

    # ---------- Zustand der Geraete (v0.14.0) ----------

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
        return self.async_show_form(step_id="zustand", data_schema=schema, last_step=False)

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

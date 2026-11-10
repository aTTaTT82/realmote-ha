"""RealMote – Tasten einer Funk-Fernbedienung auf HA-Geraete legen (per MQTT)."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .zustand import ZustandMelder

from .const import (
    CONF_ACTION,
    CONF_ACTS,
    CONF_BASE_TOPIC,
    CONF_BRIGHTNESS,
    CONF_DEVICE_ID,
    CONF_EIGEN,
    CONF_ENTITY,
    CONF_GERAETE,
    CONF_FW,
    CONF_IP,
    CONF_NAME,
    CONF_POSITION,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    LANG_HUB_DATA,
    NUM_BUTTONS,
    PLATFORMS,
    SIGNAL_ANNOUNCE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen RealMote-Hub einrichten: MQTT-Taster-Event + Announce abonnieren."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT ist nicht verfuegbar – RealMote braucht die MQTT-Integration")
        return False

    device_id: str = entry.data[CONF_DEVICE_ID]
    base: str = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
    name: str = entry.data.get(CONF_NAME, device_id)
    ip: str | None = entry.data.get(CONF_IP)
    fw: str | None = entry.data.get(CONF_FW)

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="RealMote",
        name=name,
        model="Universal Remote Hub",
        sw_version=fw,
        configuration_url=f"http://{ip}/" if ip else None,
    )

    # Neu laden, wenn sich Daten/Optionen aendern -- VOR dem ersten Abo (v0.13.0): die retained Nachrichten
    # (Activity-Namen, eigene Tasten) koennen noch waehrend der Einrichtung eintreffen. Stand der Listener erst
    # danach, wurden sie zwar gespeichert, aber nichts neu geladen -- die Knoepfe stimmten erst nach dem
    # naechsten HA-Neustart. Ein Neuladen mitten in der Einrichtung wartet auf deren Ende (setup_lock).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Taster-Events -> Aktion ausfuehren. Kurz = .../button, Lang halten = .../hold.
    button_topic = f"{base}/{device_id}/button"
    hold_topic = f"{base}/{device_id}/hold"

    @callback
    def _on_button(msg: mqtt.ReceiveMessage) -> None:
        try:
            button = int(str(msg.payload).strip())
        except (ValueError, TypeError):
            return
        hass.async_create_task(_run_button(hass, entry, button, hold=False))

    @callback
    def _on_hold(msg: mqtt.ReceiveMessage) -> None:
        try:
            button = int(str(msg.payload).strip())
        except (ValueError, TypeError):
            return
        hass.async_create_task(_run_button(hass, entry, button, hold=True))

    entry.async_on_unload(await mqtt.async_subscribe(hass, button_topic, _on_button))
    entry.async_on_unload(await mqtt.async_subscribe(hass, hold_topic, _on_hold))

    # 0.14.3: "lang halten" ist an ZWEI Stellen belegbar -- hier und als Lang-Topic im Hub. Beide melden einander, wo
    # lang belegt ist (retained "[1,6]"): der Hub .../lang_hub (ab 4.81.79), wir .../lang_ha. Regel fuer beide: ist eine
    # Taste irgendwo lang belegt, kommt bei langem Druck nur lang; sonst wirkt lang wie kurz -- nie beides
    # (Anwender 10.11.2026: "Wenn lang ausgeloest wird, darf kurz nicht auch noch kommen! Andersrum genauso.").
    lang_hub_daten: dict = hass.data.setdefault(LANG_HUB_DATA, {})

    def _vergiss_lang_hub() -> None:
        # 🔴 KEIN lambda mit pop(): HA haelt einen Rueckgabewert von on_unload fuer eine Aufgabe und bricht das Entladen
        # ab (im Test-HA 10.11.2026: "Error unloading entry" -> kein Neuladen nach dem Belegen, Abos blieben stehen)
        lang_hub_daten.pop(entry.entry_id, None)

    entry.async_on_unload(_vergiss_lang_hub)

    @callback
    def _on_lang_hub(msg: mqtt.ReceiveMessage) -> None:
        try:
            liste = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if isinstance(liste, list):
            lang_hub_daten[entry.entry_id] = {n for n in liste if isinstance(n, int) and not isinstance(n, bool)}

    entry.async_on_unload(
        await mqtt.async_subscribe(hass, f"{base}/{device_id}/lang_hub", _on_lang_hub)
    )
    try:
        belegt = sorted(n for n in range(1, NUM_BUTTONS + 1)
                        if (entry.options.get(f"{n}h") or {}).get(CONF_ENTITY))
        await mqtt.async_publish(hass, f"{base}/{device_id}/lang_ha", json.dumps(belegt), qos=0, retain=True)
    except Exception:  # noqa: BLE001 -- ein Fehler hier darf die Einrichtung samt Tasten nicht scheitern lassen
        _LOGGER.exception("RealMote: Lang-Belegungen lassen sich dem Hub nicht melden")

    # Announce -> IP/Firmware live halten (DHCP-Wechsel, Firmware-Update)
    announce_topic = f"{base}/{device_id}/announce"

    @callback
    def _on_announce(msg: mqtt.ReceiveMessage) -> None:
        try:
            data = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        # Letzten Announce merken + Entities benachrichtigen. Die Update-Entity
        # zieht daraus die laufende Version/Build und die IP des Hubs.
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
        async_dispatcher_send(hass, f"{SIGNAL_ANNOUNCE}_{entry.entry_id}", data)
        updates: dict = {}
        if data.get("ip"):
            updates["configuration_url"] = f"http://{data['ip']}/"
        if data.get("fw"):
            updates["sw_version"] = data["fw"]
        if updates:
            device = dev_reg.async_get_device(identifiers={(DOMAIN, device_id)})
            if device:
                dev_reg.async_update_device(device.id, **updates)
        # Activity-Namen (Firmware >= 4.11.0) -> Knopf-Entities benennen sich danach.
        # Nur bei Aenderung speichern; der Update-Listener laedt den Eintrag dann neu.
        acts = data.get(CONF_ACTS)
        if isinstance(acts, list) and acts and acts != entry.data.get(CONF_ACTS):
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_ACTS: acts}
            )

    entry.async_on_unload(await mqtt.async_subscribe(hass, announce_topic, _on_announce))

    # Eigene Tasten je Geraet (Firmware >= 4.81.60, retained): [{"g":"tv","n":"Fernseher","e":[[1,"Netflix"],...]},...]
    # -> Knoepfe "Fernseher: Netflix senden". Wie bei den Activity-Namen nur bei Aenderung speichern; der
    # Update-Listener laedt den Eintrag dann neu. Eine leere Liste ist gueltig (alle eigenen Tasten geloescht).
    @callback
    def _on_tasten(msg: mqtt.ReceiveMessage) -> None:
        try:
            eigen = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if isinstance(eigen, list) and eigen != entry.data.get(CONF_EIGEN, []):
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_EIGEN: eigen}
            )

    entry.async_on_unload(
        await mqtt.async_subscribe(hass, f"{base}/{device_id}/tasten", _on_tasten)
    )

    # Eingerichtete Geraete mit Namen (Firmware >= 4.81.64, retained): [{"g":"tv","n":"Fernseher"},...] -- fuer die
    # Auswahl in den Optionen "Zustand aus Home Assistant". Wie oben nur bei Aenderung speichern.
    @callback
    def _on_geraete(msg: mqtt.ReceiveMessage) -> None:
        try:
            geraete = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if isinstance(geraete, list) and geraete != entry.data.get(CONF_GERAETE, []):
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_GERAETE: geraete}
            )

    entry.async_on_unload(
        await mqtt.async_subscribe(hass, f"{base}/{device_id}/geraete", _on_geraete)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Zustand der Geraete aus Home Assistant an den Hub (v0.14.0) -- nur mit Zuordnung in den Optionen. Ein Fehler hier
    # darf die Einrichtung nicht scheitern lassen: sonst waeren auch die Smart-Home-Tasten tot
    try:
        await ZustandMelder(hass, entry).async_start()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("RealMote: Zustand aus Home Assistant laesst sich nicht starten")

    _LOGGER.info("RealMote %s: hoere auf %s", device_id, button_topic)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Eintrag neu laden, wenn sich Daten/Optionen aendern (z. B. neue Activity-Namen)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _run_button(
    hass: HomeAssistant, entry: ConfigEntry, button: int, hold: bool = False
) -> None:
    """Die fuer diese Taste (kurz/lang) hinterlegte Aktion ausfuehren."""
    key = f"{button}h" if hold else str(button)  # kurz: "1".."6", lang: "1h".."6h"
    cfg = entry.options.get(key)
    if hold and (not cfg or not cfg.get(CONF_ENTITY)):
        # 0.14.2 (Anwender 10.11.2026): ist "lang halten" frei, wirkt langes Halten wie kurz tippen. 0.14.3: aber nur,
        # wenn der Hub gemeldet hat, dass er fuer diese Taste selbst kein Lang-Topic hat (.../lang_hub, ab 4.81.79) --
        # sonst kaeme sein Lang-Topic UND unser Kurz-Befehl. Meldet er nichts (aelterer Hub), bleibt es wie bis 0.14.1.
        lang_hub = hass.data.get(LANG_HUB_DATA, {}).get(entry.entry_id)
        if lang_hub is None or button in lang_hub:
            _LOGGER.debug("RealMote: Taste %s lang ist hier frei, %s", button,
                          "der Hub meldet seine Belegung nicht" if lang_hub is None else "der Hub hat dafuer ein Lang-Topic")
            return
        cfg = entry.options.get(str(button))
    if not cfg or not cfg.get(CONF_ENTITY):
        _LOGGER.debug("RealMote: Taste %s (%s) ist nicht belegt", button, "lang" if hold else "kurz")
        return

    entity_id: str = cfg[CONF_ENTITY]
    action: str = cfg.get(CONF_ACTION, "toggle")
    domain = entity_id.split(".")[0]
    _LOGGER.debug("RealMote: Taste %s -> %s auf %s", button, action, entity_id)

    try:
        # Szenen, Skripte und Button-Entities haben genau EINE sinnvolle Aktion –
        # die gewaehlte Aktion wird ignoriert, damit es fuer Laien immer "einfach geht".
        if domain == "scene":
            await hass.services.async_call(
                "scene", "turn_on", {"entity_id": entity_id}, blocking=False
            )
            return
        if domain == "script":
            await hass.services.async_call(
                "script", "turn_on", {"entity_id": entity_id}, blocking=False
            )
            return
        if domain == "button":
            await hass.services.async_call(
                "button", "press", {"entity_id": entity_id}, blocking=False
            )
            return

        if action == "toggle":
            await hass.services.async_call(
                "homeassistant", "toggle", {"entity_id": entity_id}, blocking=False
            )
        elif action == "on":
            brightness = cfg.get(CONF_BRIGHTNESS)
            if brightness is not None and domain == "light":
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": entity_id, "brightness_pct": int(brightness)},
                    blocking=False,
                )
            else:
                await hass.services.async_call(
                    "homeassistant", "turn_on", {"entity_id": entity_id}, blocking=False
                )
        elif action == "off":
            await hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": entity_id}, blocking=False
            )
        elif action == "open":
            await hass.services.async_call(
                "cover", "open_cover", {"entity_id": entity_id}, blocking=False
            )
        elif action == "close":
            await hass.services.async_call(
                "cover", "close_cover", {"entity_id": entity_id}, blocking=False
            )
        elif action == "position":
            await hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": entity_id, "position": int(cfg.get(CONF_POSITION, 0))},
                blocking=False,
            )
    except Exception:  # noqa: BLE001 – Service-Fehler nie den Callback killen lassen
        _LOGGER.exception("RealMote: Taste %s Aktion fehlgeschlagen", button)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Abmelden (unsubscribe passiert ueber entry.async_on_unload)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """0.14.3: Eintrag geloescht -- die retained Lang-Belegungen beim Broker loeschen, sonst haelt der Hub sie fuer gueltig."""
    base = entry.data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
    try:
        await mqtt.async_publish(hass, f"{base}/{entry.data[CONF_DEVICE_ID]}/lang_ha", "", qos=0, retain=True)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("RealMote: Lang-Belegungen beim Broker nicht geloescht", exc_info=True)

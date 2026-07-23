<p align="center">
  <img src="https://raw.githubusercontent.com/aTTaTT82/realmote-ha/main/images/remote.png" alt="RealMote" width="240">
</p>

<h1 align="center">RealMote – Home Assistant Integration</h1>

Macht aus dem **RealMote Hub** (6-Tasten-Funk-Fernbedienung + ESP32-Hub) ein echtes
Home-Assistant-Gerät: Du legst jede Taste direkt im Geräte-Menü auf ein beliebiges HA-Gerät
und eine Aktion – **inklusive Helligkeit für Lampen und Position für Rollos**. Keine
Automationen, keine Topics, kein YAML.

Der Hub meldet per MQTT nur „Taste N gedrückt" – *was* passiert, entscheidet diese Integration.

## Voraussetzungen
- Home Assistant mit eingerichteter **MQTT-Integration** (z. B. Mosquitto-Broker-App).
- Ein RealMote Hub mit Firmware **≥ 4.6.0**, verbunden mit demselben MQTT-Broker
  (im Hub unter `http://<hub-ip>/mqtt` konfiguriert).

## Installation (über HACS)
1. HACS → oben rechts ⋮ → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/aTTaTT82/realmote-ha`, Kategorie **Integration** → Hinzufügen.
3. „RealMote" installieren, dann **Home Assistant neu starten**.

## Einrichten
1. Wenn der Hub online ist, taucht er **automatisch** unter *Einstellungen → Geräte & Dienste*
   auf („Entdeckt"). Auf **Konfigurieren** → bestätigen.
   (Falls nicht: *Integration hinzufügen → RealMote* und die Geräte-ID von der `/health`-Seite eintragen.)
2. Beim Gerät auf **Konfigurieren** → Taste wählen → **Gerät** aus der Liste, **Aktion**
   (Umschalten/An/Aus/Öffnen/Schließen/Position), optional **Helligkeit %** oder **Position %**.
3. Fertig. Tastendruck auf der Fernbedienung führt die Aktion aus.

## Aktionen
| Aktion | Wirkt auf | Extra-Feld |
|---|---|---|
| Umschalten | Licht, Schalter, … | – |
| An / Aus | Licht, Schalter, … | Helligkeit % (Licht) |
| Öffnen / Schließen | Rollo/Cover | – |
| Position setzen | Rollo/Cover | Position % |

## Hub-Einstellungen
Auf der **Geräteseite** in HA gibt es einen Link **„Gerät besuchen"** direkt zur
Weboberfläche des Hubs (Broker, WLAN, Firmware-Update). Die Firmware-Version wird ebenfalls
angezeigt und bei jedem Announce aktuell gehalten.

## Status
v0.3. Transport = MQTT. Firmware-Announce: `realmote/<id>/announce` (enthält `ip`, `fw`),
Taster-Event: `realmote/<id>/button` = Tastennummer. Braucht Hub-Firmware **≥ 4.6.1**
für den Geräte-Link. Icon & Logo werden ab HA 2026.3 lokal aus dem `brand/`-Ordner geladen
(kein `home-assistant/brands`-Eintrag nötig).

### Änderungen
- **0.3.1** – Kleinigkeiten & Doku.
- **0.3.0** – Eigenes Marken-Icon + Logo (`brand/`-Ordner).
- **0.2.3** – Tasten-Übersicht mit Gerätetyp-Emojis.
- **0.2.2** – README-Bild als PNG.
- **0.2.1** – Geräte-Link zur Hub-Weboberfläche, Remote-Grafik (3×2).

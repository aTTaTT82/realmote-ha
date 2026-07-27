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

## 🎬 Ganze Szenen auf eine Taste legen
Im Feld **„Gerät / Szene / Skript"** kannst du auch eine **Szene** oder ein **Skript**
auswählen — so legst du eine ganze Stimmung (mehrere Lampen, Rollos, Mediaplayer, …)
auf eine einzige Taste:

1. Szene in HA zusammenstellen: **Einstellungen → Automatisierungen & Szenen → Szenen → Szene hinzufügen**
   (Geräte reinziehen, gewünschte Zustände einstellen, speichern).
2. In RealMote den Tasten-Slot öffnen und die Szene als Ziel wählen.

Die „Aktion" ist dabei egal — Szenen werden **immer aktiviert**, Skripte **immer gestartet**,
Button-Entities **immer gedrückt** (die Integration erkennt den Typ selbst, es kann nichts
falsch eingestellt werden). Tipp: kurz tippen = Szene „Film", lang halten = Szene „Alles hell".

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
- **0.5.0** – 🎬 **Szenen, Skripte & Button-Entities auf Tasten legen** — Typ wird automatisch
  erkannt (Szene → aktivieren, Skript → starten, Button → drücken), Aktions-Auswahl kann
  nichts mehr falsch machen; Hinweis-Texte im Zuweisen-Dialog.
- **0.4.0** – Tippen **und** Halten pro Taste → 12 Aktionen (Hub-Firmware ≥ 4.7.0).
- **0.3.1** – Kleinigkeiten & Doku.
- **0.3.0** – Eigenes Marken-Icon + Logo (`brand/`-Ordner).
- **0.2.3** – Tasten-Übersicht mit Gerätetyp-Emojis.
- **0.2.2** – README-Bild als PNG.
- **0.2.1** – Geräte-Link zur Hub-Weboberfläche, Remote-Grafik (3×2).

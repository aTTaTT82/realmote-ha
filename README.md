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

## 🗣️ Tasten aus HA ausführen (z. B. „Alexa, Pause")
Ab v0.8.0 (+ Hub-Firmware ≥ 4.13.0) gibt es am Gerät **drückbare Knöpfe für die
einzelnen Tasten**: „Pause senden", „Play senden", „Lautstärke + senden", … Ein
Druck wirkt **Activity-bewusst** wie ein Druck auf der Fernbedienung — „Pause"
pausiert also genau das Gerät, das gerade die Wiedergabe macht.

Standardmäßig sind die Medien-/Lautstärke-/Kanal-Tasten aktiv; selten gebrauchte
(Farben, Navigation, HDMI, …) sind als Entity vorhanden, aber deaktiviert —
einfach in HA bei Bedarf aktivieren.

Für Sprachsteuerung: den gewünschten Knopf (z. B. „Pause senden") wie gewohnt an
Alexa/Google durchreichen und eine Routine mit eigenem Sprachbefehl darauf legen.

## 🎛️ Jede Taste als HA-Ereignis (Automationen auf ALLE Tasten)
Ab v0.7.0 (+ Hub-Firmware ≥ 4.12.0) taucht **jede Taste der Fernbedienung** als
**Ereignis-Entity** am RealMote-Gerät auf (z. B. „Taste Rot", „Taste Play",
„Taste Kanal +", auch Activity- und Power-Tasten). Die Taste macht weiterhin ganz
normal ihre Fernbedienungs-Funktion — das Ereignis kommt **zusätzlich**.

Damit lassen sich beliebige Automationen bauen: *„Wenn Taste Blau gedrückt →
Staubsauger starten"*, *„Wenn Taste Aus gedrückt → auch alle Lichter aus"*, usw.
Trigger in HA: Automation → Auslöser → Entität → die gewünschte „Taste …"-Entity.
(Die Smart-Home-Tasten 1–6 behalten ihre eigenen 12 Aktions-Slots.)

## ▶️ Hub-Activities aus HA starten (z. B. „Android TV")
Ab v0.6.0 (+ Hub-Firmware ≥ 4.11.0) legt die Integration **Knopf-Entities** am
RealMote-Gerät an: je Activity ein Knopf (Namen kommen vom Hub, z. B. „TV gucken",
„Android TV", „Musik") plus **„Alles aus"**. Ein Druck startet die komplette
Activity auf dem Hub (TV an, HDMI-Eingang, Soundbar, Android-Wake, …).

Damit lässt sich der Gerätestart in Szenen-Abläufe einbauen — als **Skript**:

1. *Einstellungen → Automatisierungen & Szenen → Skripte → Skript hinzufügen*,
   z. B. „Filmabend": Aktion 1 = Szene „Licht Filmabend" aktivieren,
   Aktion 2 = Knopf „Android TV" drücken.
2. Das Skript in RealMote auf eine Taste legen (Skripte sind direkt wählbar).

Die Knöpfe funktionieren natürlich auch im Dashboard, in Automationen und per
Sprachassistent.

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

## ⬆️ Firmware-Update aus Home Assistant (v0.9.0)
Der Hub erscheint jetzt unter **Einstellungen → Geräte & Dienste → Updates** wie jedes
andere Gerät: Version, Änderungsprotokoll, ein Knopf **Installieren**.

**Warum das nicht einfach der Hub selbst macht:** Beim Aufbau einer gesicherten Verbindung
bleiben dem ESP32 nur rund **23 KB** freier Arbeitsspeicher. Das reicht heute — aber jede
neue Funktion knabbert daran, und wenn es einmal nicht mehr reicht, könnte der Hub genau die
Reparatur nicht mehr laden, die das beheben würde. Deshalb übernimmt Home Assistant den
Internet-Teil: HA lädt Manifest und Firmware und **schiebt** die Datei über das lokale Netz
an den Hub.

**Sicher bleibt es trotzdem** — der Hub glaubt auch Home Assistant nicht:
1. Die Manifest-Angaben werden gegen die eingebettete Signatur geprüft (ECDSA gegen den fest
   in der Firmware verdrahteten Schlüssel).
2. Die Build-Nummer muss größer sein als die laufende (keine Rückstufung auf alte Versionen).
3. Das Abbild selbst wird gegen seine Signatur geprüft.

Ein manipuliertes Manifest beantwortet der Hub mit einer Ablehnung. Braucht Hub-Firmware
**≥ 4.19.1** (erst die meldet die Build-Nummer im Announce — ohne sie ließe sich innerhalb
einer Version nicht erkennen, dass ein Update bereitliegt).

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
- **0.9.1** – Fix: Beim Start meldete die Firmware-Entität immer „Aktuell". Ursache: Sie
  fragte ab, bevor der MQTT-Announce mit der Hub-IP da war, und meldete dann die installierte
  Version als neueste. Jetzt wird die Abfrage nachgeholt, sobald der Announce eintrifft.
- **0.9.0** – ⬆️ **Firmware-Update direkt aus HA**: Update-Entity mit Installieren-Knopf.
  HA lädt die Firmware und schiebt sie an den Hub, weil dem Hub für den Download selbst
  nur ~23 KB Reserve bleiben. Signaturprüfung und Rückstufungs-Sperre bleiben beim Hub.
  Braucht Hub-Firmware ≥ 4.19.1.
- **0.8.0** – 🗣️ **Drückbare Tasten-Knöpfe** („Pause senden", …, Activity-bewusst) —
  für Alexa-/Google-Routinen, Dashboards, Skripte. Braucht Hub-Firmware ≥ 4.13.0
  (MQTT-Befehl `key:<NAME>`).
- **0.7.0** – 🎛️ **Jede Taste als Ereignis-Entity** (Farb-, Medien-, Navigations-,
  Activity- und Power-Tasten) für freie Automationen. Braucht Hub-Firmware ≥ 4.12.0.
- **0.6.0** – ▶️ **Activity-Knöpfe**: je Hub-Activity eine Button-Entity („TV gucken",
  „Android TV", „Musik", Namen live vom Hub) + „Alles aus" — für Skripte, Automationen,
  Dashboards. Braucht Hub-Firmware ≥ 4.11.0 (MQTT-Befehl `activity:N`).
- **0.5.0** – 🎬 **Szenen, Skripte & Button-Entities auf Tasten legen** — Typ wird automatisch
  erkannt (Szene → aktivieren, Skript → starten, Button → drücken), Aktions-Auswahl kann
  nichts mehr falsch machen; Hinweis-Texte im Zuweisen-Dialog.
- **0.4.0** – Tippen **und** Halten pro Taste → 12 Aktionen (Hub-Firmware ≥ 4.7.0).
- **0.3.1** – Kleinigkeiten & Doku.
- **0.3.0** – Eigenes Marken-Icon + Logo (`brand/`-Ordner).
- **0.2.3** – Tasten-Übersicht mit Gerätetyp-Emojis.
- **0.2.2** – README-Bild als PNG.
- **0.2.1** – Geräte-Link zur Hub-Weboberfläche, Remote-Grafik (3×2).

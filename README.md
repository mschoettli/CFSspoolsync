# CFSspoolsync

Web-App zum Live-Tracking des Creality CFS (Creality Filament System) am K2 Combo. Zeigt Kammer-Temperatur und -Feuchtigkeit, die vier Slots mit eingelegten Spulen, einen Spulenlager-Bestand und den Filament-Verbrauch live während des Drucks.

- **FastAPI-Backend** mit SQLite-Persistenz, WebSocket-Live-Updates und Moonraker-Bridge
- **React-Frontend** mit Tailwind, Recharts-History und DE/EN-Umschaltung
- **Docker-Compose-Stack** mit Watchtower für Zero-Touch-Updates nach `git push`
- **GitHub Actions** baut bei jedem Push nach `main` Multi-Arch-Images (amd64/arm64) und pusht sie nach GHCR

## Features

- 4 Slot-Panels mit Live-Gewicht, Flow-Rate während des Drucks und Low-Filament-Warnung
- Spulen-Verwaltung (Hersteller, Material, Farbe, Durchmesser, Temperaturen, Brutto-/Tara-/Nettogewicht)
- Tara-Tabelle mit 20 vorgepflegten Community-Referenzwerten (Bambu Lab, Creality, eSun, Polymaker, Prusament usw.), inline editierbar
- Dashboard-KPIs: Kammer-Klima, Gesamt-Filament, aktive Slots
- Verbrauchsverlauf als Chart (24 h / 7 Tage / 30 Tage)
- WebSocket-Broadcast aktualisiert alle Clients gleichzeitig
- Simulator-Modus für Demo/Entwicklung ohne echten Drucker

## Quick Start

```bash
git clone https://github.com/<DEIN-USER>/CFSspoolsync.git
cd CFSspoolsync
cp .env.example .env
# .env anpassen (siehe unten)
docker compose up -d
```

Dann auf `http://<dein-host>:8088` öffnen.

Beim ersten Start legt das Backend automatisch 4 leere Slots, die Default-Tara-Tabelle und eine CFS-State-Row an. Die SQLite-Datenbank wird im Docker-Volume `cfs-data` persistiert.

## Konfiguration

Alle Werte in `.env`:

| Variable | Default | Beschreibung |
|---|---|---|
| `REGISTRY` | `ghcr.io/mschoettli` | GHCR-Namespace für die Images |
| `TAG` | `latest` | Image-Tag |
| `HTTP_PORT` | `8088` | Port für die Web-UI |
| `CFS_MOONRAKER_HOST` | *(leer)* | IP/Hostname des K2 — leer = Simulator-Mode |
| `CFS_MOONRAKER_PORT` | `80` | Moonraker-Port |
| `TZ` | `Europe/Zurich` | Zeitzone |

### Simulator vs. Live-Mode

**Simulator (default):** `CFS_MOONRAKER_HOST` leer lassen → das Backend erzeugt realistisch wobbelnde Temperatur- und Feuchtigkeitswerte und simuliert Druckverbrauch auf Slots, die auf „Druckt" geschaltet sind. Ideal für Demo und UI-Entwicklung.

**Live-Mode:** `CFS_MOONRAKER_HOST=192.168.x.x` setzen → das Backend pollt alle 2 s `http://<host>:<port>/printer/objects/query?box&extruder&cfs` und zieht Temperatur/Feuchtigkeit aus dem `box`- oder `cfs`-Objekt.

> **Hinweis zur K2-Combo-Firmware:** Die stock OpenWrt-basierte Moonraker-Version des K2 Combo unterstützt je nach Firmware-Version unterschiedliche Objekt-Namen. Der Parser in `backend/app/services/cfs_bridge.py` deckt die zwei gängigsten Varianten ab (`box` und `cfs`). Falls deine Firmware andere Felder liefert, passe das Mapping in `_poll_moonraker()` an.

## Auto-Update

Der Stack enthält drei Services:

1. **backend** — FastAPI + SQLite (Volume `cfs-data`)
2. **frontend** — nginx serviert das React-Build, proxied `/api` und `/ws` zum Backend
3. **watchtower** — überwacht alle 5 min die Registry und zieht neue Images automatisch

### Auto-Update-Kette

```
 ┌──────────┐    git push main    ┌──────────────┐
 │  Laptop  │────────────────────▶│    GitHub    │
 └──────────┘                     └──────┬───────┘
                                         │ trigger
                                         ▼
                                  ┌──────────────┐
                                  │ GH Actions   │
                                  │ build & push │
                                  └──────┬───────┘
                                         │ push :latest
                                         ▼
                                  ┌──────────────┐
                                  │ ghcr.io      │
                                  └──────┬───────┘
                                         │ poll (5 min)
                                         ▼
 ┌──────────────────────────────────────────────┐
 │  Proxmox-Host                                │
 │   ┌──────────┐   ┌──────────┐   ┌─────────┐  │
 │   │ backend  │   │ frontend │   │watchtower│ │
 │   └──────────┘   └──────────┘   └─────────┘  │
 └──────────────────────────────────────────────┘
```

Nach `git push` auf `main`:
1. GitHub Actions baut beide Images (amd64 + arm64) und pusht nach `ghcr.io/<user>/cfsspoolsync-{backend,frontend}:latest`
2. Watchtower erkennt den neuen `latest`-Digest spätestens nach 5 min
3. Watchtower zieht die neuen Images, stoppt die alten Container und startet neue — SQLite-Volume bleibt bestehen

### Manuelles Update

Falls du Watchtower nicht willst oder sofort updaten möchtest:

```bash
./update.sh
```

Macht `git pull`, `docker compose pull`, `docker compose up -d`, und räumt alte Images auf.

### Einrichtung der Registry

Für öffentliche Repos funktioniert GHCR ohne zusätzliche Secrets — der `GITHUB_TOKEN` im Workflow reicht. Für private Images:

1. In deinen GitHub-Settings ein Personal Access Token mit `write:packages`-Scope erzeugen
2. Auf dem Host:
   ```bash
   echo $GHCR_PAT | docker login ghcr.io -u <github-user> --password-stdin
   ```
3. Danach liest auch Watchtower die Credentials aus `~/.docker/config.json`

## Lokales Bauen (ohne Registry)

Wenn du komplett ohne GitHub und GHCR laufen willst, nutze das Build-Override:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

Watchtower ignoriert lokal gebaute Images (Label-Opt-Out), aktualisiert also nichts automatisch. Für ein Update nach Code-Änderung:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

## Entwicklung

### Backend lokal

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend läuft dann auf `http://localhost:8000`, OpenAPI-Docs unter `/docs`.

### Frontend lokal

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft auf `http://localhost:5173`. Requests an `/api` und `/ws` werden per Vite-Proxy an `http://localhost:8000` weitergeleitet (siehe `vite.config.js`). Wenn das Backend auf einem anderen Host läuft:

```bash
VITE_BACKEND_URL=http://192.168.1.10:8000 npm run dev
```

## API-Übersicht

Alle Endpunkte unter `/api/`:

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/spools` | Alle Spulen |
| `POST` | `/spools` | Neue Spule (optional `assign_to_slot`) |
| `PATCH` | `/spools/{id}` | Spule bearbeiten |
| `DELETE` | `/spools/{id}` | Spule löschen |
| `GET` | `/tares` | Tara-Tabelle |
| `POST/PATCH/DELETE` | `/tares[/{id}]` | Tara-CRUD |
| `GET` | `/slots` | Alle 4 Slots |
| `POST` | `/slots/{id}/assign` | Spule in Slot einlegen |
| `POST` | `/slots/{id}/unassign` | Slot leeren |
| `POST` | `/slots/{id}/print` | Druck starten/stoppen |
| `GET` | `/cfs` | Aktueller CFS-State |
| `GET` | `/history?days=7&slot_id=1` | Verbrauchsverlauf |
| `GET` | `/health` | Healthcheck |

**WebSocket:** `ws://<host>/ws` broadcastet bei jedem Backend-Tick (1 s) ein JSON mit aktuellem CFS-State und allen Slots:

```json
{
  "type": "live",
  "data": {
    "cfs": {"temperature": 28.4, "humidity": 17.8, "connected": true, "last_sync": "..."},
    "slots": [{"id": 1, "spool_id": 5, "current_weight": 894.2, "is_printing": true, "flow": 4.12, "spool": {...}}, ...]
  }
}
```

## Datenmodell

```
spools                    tares
─────────                 ────────
id                        id
manufacturer              manufacturer
material                  material
color, color_hex          weight
diameter                  updated_at
nozzle_temp, bed_temp
gross_weight              slots
tare_weight               ─────
name                      id (1..4)
created_at, updated_at    spool_id  ──→  spools.id
                          current_weight
history                   is_printing
────────                  flow
id                        updated_at
timestamp
slot_id                   cfs_state
spool_id                  ─────────
net_weight                id (=1)
consumed                  temperature, humidity
temperature, humidity     connected, last_sync
```

## Lizenz

MIT — siehe [LICENSE](LICENSE).

## Tara-Referenzwerte

Die 20 vorgeladenen Leerspulen-Gewichte basieren auf der [stlDenise3D-Community-Datenbank](https://stldenise3d.com/how-much-do-empty-spools-weigh/) und dem [Printables Empty Spool Catalog](https://www.printables.com/model/464663-empty-spool-weight-catalog). Korrekturen und Ergänzungen einfach über das Tara-Modal im UI.

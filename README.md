# CFSspoolsync

Filament management for the Creality K2 Plus / K2 Combo with CFS (Creality Filament System).

![License](https://img.shields.io/badge/license-GPL%20v3-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)

## Features

- Live CFS slot view (4 slots) with color, material, weight and temperatures
- Automatic consumption tracking via Moonraker polling (every 10 seconds)
- Storage management for all spools
- Print job history with per-slot consumption
- SSH-based live sync from K2 CFS JSON
- Dark UI with teal accent

## Requirements

- Docker + Docker Compose
- Creality K2 Plus or K2 Combo with CFS
- Moonraker running on the printer (`http://<printer-ip>:7125`)
- SSH access from the Docker host to the printer

## Quick Start

### 1. Clone

```bash
git clone https://github.com/your-username/cfsspoolsync.git
cd cfsspoolsync
```

### 2. SSH Key

Create an SSH key on the Docker host and copy it to the printer:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_k2 -N ""
ssh-copy-id -i /root/.ssh/id_k2 root@<printer-ip>
```

Test the connection:

```bash
ssh -i /root/.ssh/id_k2 root@<printer-ip> "echo OK"
```

### 3. Configure

```bash
cp .env.example .env
nano .env
```

Set your printer IP and paths in `.env`.

### 4. Start

```bash
docker compose up -d --build
```

Open the web UI: `http://<docker-host-ip>:8080`

---

## Configuration

All settings via `.env`:

| Variable | Default | Description |
|---|---|---|
| `K2_HOST` | `192.168.0.0` | Printer IP address |
| `K2_SSH_USER` | `root` | SSH user on printer |
| `K2_SSH_KEY` | `/root/.ssh/id_k2` | Path to SSH private key on host |
| `MOONRAKER_URL` | `http://192.168.0.0:7125` | Moonraker API URL |
| `CFS_JSON_PATH` | `/mnt/UDISK/...` | CFS JSON path on printer |
| `PORT` | `8080` | Web UI port |

---

## Usage

### Add a new spool

1. Go to **Lager** → **+ Neue Spule**
2. Select a CFS slot (T1A–T1D) → **Von K2 lesen** to auto-fill data
3. Enter the initial weight manually
4. Save

### Load spool into CFS slot

- From the **Spulen** tab: click an empty slot → **+ Spule einlegen**
- Or from **Lager**: click **Einlegen** on any stored spool

### Sync weights from K2

Click **⟳ Sync mit K2** on the Spulen tab to pull current `remainLen` values from the printer and update all active spools.

### Consumption tracking

Moonraker is polled every 10 seconds. On print start a snapshot is taken; on print end the consumed grams are calculated and deducted automatically.

**Formula:**
```
grams = π × (diameter_mm / 20)² × (meters × 100) × density_g_cm³
```

---

## Tech Stack

- **Backend**: Python 3.12 / FastAPI
- **Database**: SQLite (WAL mode)
- **Frontend**: Vanilla HTML / CSS / JS (Single Page App)
- **Deployment**: Docker Compose

---

## License

GNU General Public License v3.0 – see [LICENSE](LICENSE)

Copyright (C) 2026 mschoettli

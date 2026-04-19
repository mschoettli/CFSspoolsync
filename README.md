# CFSspoolsync

CFSspoolsync is a web app for tracking Creality K2 Combo CFS slots, spool inventory, and filament consumption with live updates.

## Current Feature Set

- Live CFS environment data: temperature, humidity, connection status
- Four slot panels with:
  - Assigned spool details
  - Remaining weight derived from live CFS data
  - Automatic print-state display (Moonraker-driven, no manual print button)
- Inventory management:
  - Create, edit, delete spools
  - Assign/unassign to slots
  - Color name and HEX synchronization (`color` or `color_hex`)
- Tare management modal:
  - Community defaults + custom entries
  - Inline editing and dedicated add-entry modal
- History modal (24h / 7d / 30d) based on backend history records
- Settings modal:
  - Language toggle (DE/EN)
  - Theme toggle (dark/light)
  - Quick access to tare management
- OCR spool label scan:
  - Tesseract-based extraction
  - Optional OpenAI/Anthropic post-processing fallback (server-side only)

<!-- screenshot: dashboard-overview -->
<!-- screenshot: settings-and-history -->
<!-- screenshot: tare-management-modal -->
<!-- screenshot: add-spool-ocr-modal -->

## Installation

```bash
git clone https://github.com/<your-user>/CFSspoolsync.git
cd CFSspoolsync
cp .env.example .env
# Edit .env (required)
docker compose up -d
```

Open:
- `http://<host>:8088` (or your configured `HTTP_PORT`)

## Technical Documentation

All technical details were moved to:
- [Technical Reference](docs/technical-reference.md)

## License

GNU GPL v3.0. See [LICENSE](LICENSE).

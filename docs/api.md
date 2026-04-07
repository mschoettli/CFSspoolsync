# Public API

Base URL: `http://<host>:<port>`

## Conventions

- JSON request/response for all non-upload routes.
- Error payload follows FastAPI default shape (`{"detail": "..."}`).
- Existing endpoint paths are backward compatible.

## Spools

### `GET /api/spools`
List spools. Optional query: `status=lager|aktiv|leer`.

### `POST /api/spools`
Create spool.

Example request:
```json
{
  "material": "PLA",
  "color": "#FFFFFF",
  "initial_weight": 1000
}
```

### `GET /api/spools/{spool_id}`
Read one spool.

### `PUT /api/spools/{spool_id}`
Update spool fields (partial).

### `DELETE /api/spools/{spool_id}`
Delete spool (fails for active slot assignments).

## CFS

### `GET /api/cfs`
Returns 4-slot DB mapping.

Example response:
```json
{
  "slots": [
    {"slot": 1, "key": "Slot 1", "spool": null},
    {"slot": 2, "key": "Slot 2", "spool": null},
    {"slot": 3, "key": "Slot 3", "spool": null},
    {"slot": 4, "key": "Slot 4", "spool": null}
  ]
}
```

### `GET /api/cfs/live`
Reads live slot values from K2 via SSH.

### `POST /api/cfs/sync`
Updates active spool weights from live remain-length values.

### `GET /api/cfs/slot/{slot_num}/read`
Reads one live slot from K2 (`slot_num` in `1..4`).

### `POST /api/cfs/slot/{slot_num}/assign/{spool_id}`
Assigns storage spool to a slot.

### `POST /api/cfs/slot/{slot_num}/remove`
Removes active spool from slot back to storage.

## Printer

### `GET /api/printer/status`
Moonraker telemetry summary.

Response keys:
- `reachable`
- `state`
- `filename`
- `progress`
- `extruder_temp`
- `extruder_target`
- `bed_temp`
- `bed_target`

## Jobs

### `GET /api/jobs?limit=30`
Returns recent jobs with per-slot before/after values and total consumed grams.

## OCR

### `POST /api/scan-label`
Multipart upload (`file`) for label OCR.

Returns parsed fields like:
- `brand`, `material`, `color`
- `nozzle_min`, `nozzle_max`, `bed_min`, `bed_max`
- `diameter`, `weight_g`, `raw_text`

# Public API

Base URL: `http://<host>:<port>`

## Conventions

- JSON request/response for all non-upload routes.
- Error payload follows FastAPI default shape (`{"detail": "..."}`).

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

### `POST /api/spools/{spool_id}/calibrate-weight`
Calibrate one spool from a scale measurement.

Example request:
```json
{
  "gross_weight_g": 338.0,
  "tare_weight_g": 175.0
}
```

If `tare_weight_g` is omitted, the API uses this order:
1. stored `spool.tare_weight_g`
2. known brand default tare
3. `0.0`

### `POST /api/spools/defaults/apply-brand`
Apply editable brand default tare weights to all spools with missing `tare_weight_g`.

Example response:
```json
{
  "updated": 3,
  "entries": [
    {"spool_id": 2, "brand": "Creality", "material": "PLA", "tare_weight_g": 175.0}
  ]
}
```

### `DELETE /api/spools/{spool_id}`
Delete spool (fails for active slot assignments).

## Tare Defaults

### `GET /api/tare-defaults`
List all manufacturer tare defaults.

### `POST /api/tare-defaults`
Create one manufacturer tare default.

Example request:
```json
{
  "brand_label": "Polymaker",
  "tare_weight_g": 210.0
}
```

### `PUT /api/tare-defaults/{brand_key}`
Update one existing tare default.

### `DELETE /api/tare-defaults/{brand_key}`
Delete one non-system tare default.

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
Response includes:
- `synced` and `updates` for weight updates
- `removed_count` and `removed` for active slots automatically moved back to storage when K2 reports `loaded=false`
- `updates[*].raw_remain_len`, `updates[*].normalized_remain_len`
- `updates[*].raw_k2_g`, `updates[*].effective_g`, `updates[*].applied_factor`
- `updates[*].source` (`k2_live_sync`, `print_end_snapshot`, `manual_calibration`)

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
- `remaining_seconds`
- `current_layer`
- `total_layer`
- `print_duration_seconds`
- `estimated_finish_at`
- `cfs_temp`
- `cfs_humidity`

## Jobs

### `GET /api/jobs?limit=30`
Returns recent jobs with per-slot before/after values and total consumed grams.
Also includes:
- `duration_seconds` (`null` for running jobs, numeric for finished/cancelled/error)

## App Config

### `GET /api/app-config`
Returns public app locale configuration derived from `TIMEZONE`.

Response keys:
- `timezone`
- `language` (`de|en|fr|it`)
- `datetime_locale` (`de-DE|en-US|fr-FR|it-IT`)
- `camera_stream_url`

## OCR

### `POST /api/ocr/scan`
Multipart upload (`file`) for label OCR.

Returns:
- `engine` (`tesseract|openai|claude`)
- `duration_ms`
- `raw_text`
- `warnings`
- `provider_used` (`tesseract|openai|claude`)
- `provider_chain` (provider execution order)
- `fallback_reason` (`missing_required_fields|low_confidence|null`)
- `cloud_used` (`true` if final payload comes from cloud provider)
- `fallback_recommended` (`true` when required fields are missing/low confidence)
- `suggestions`:
  - `brand`: top fallback suggestions
  - `material`: top fallback suggestions
  - `color`: top fallback suggestions
- `timing`:
  - `total_ms`
  - `partial_timeout`
  - `stages` (`preprocess_ms`, `ocr_ms`, `parse_ms`, `variants`, `selected_variant`, `selected_config`)
- `result`:
  - `brand`, `material`, `color_name`, `color_hex`
  - `diameter_mm`, `weight_g`
  - `nozzle_min`, `nozzle_max`, `bed_min`, `bed_max`
- `review` per field:
  - `status` (`accepted | low_confidence | missing | rejected`)
  - `confidence`
  - `source_text`
  - `accepted_value`
  - `candidates`

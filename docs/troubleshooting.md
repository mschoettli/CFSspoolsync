# Troubleshooting

This page collects common operational issues and quick diagnostics for CFSspoolsync.

## K2 Slot Data Does Not Update

Symptoms:
- Active slot weight or spool metadata stays unchanged in the web app.
- Some slots show older values until a manual refresh on the printer.

Why it happens:
- The app reads CFS state from the K2/Moonraker side.
- Slot metadata and remaining values are only refreshed after the slot is re-read on the K2 UI.

Fix on the K2:
1. Open the CFS screen.
2. Tap the colored spool.
3. Tap the slot refresh arrow above the slot.
4. Wait for the next backend poll cycle.

<img width="465" height="265" alt="k2_cfs_spool" src="https://github.com/user-attachments/assets/9c26dfe3-c9ac-44d1-bdcf-f393fde96b70" />


Then refresh the browser if needed.

## Moonraker Reachability

Symptoms:
- Dashboard shows stale values.
- Backend cannot fetch live CFS telemetry.

Checks:
1. Verify `.env` contains the correct `CFS_MOONRAKER_HOST` and `CFS_MOONRAKER_PORT`.
2. Confirm the backend container can reach that host/IP from your network.
3. Open API health endpoint:
   - `GET /api/health`
4. Check backend logs for Moonraker polling errors.

If the host is empty, the app intentionally runs in simulator mode.

## OCR Scan Limits

Symptoms:
- OCR scan returns partial or noisy fields.
- Values are missing or ambiguous.

Expected behavior:
- OCR is best-effort prefill.
- Label quality, lighting, angle, and print style affect extraction quality.
- Cloud normalization only runs if enabled and API keys are present in `.env`.

Recommendations:
1. Use a sharp, well-lit, front-facing image.
2. Keep the full label visible.
3. Review and correct fields before saving.
4. Enter measured gross weight manually for highest accuracy.

## Fluidd Dashboard Embed (MIME or WebSocket Errors)

Symptoms:
- Browser console shows `Failed to load module script` with MIME `text/html`.
- Browser console shows repeated WebSocket failures for `/ws`.

Why it happens:
- CFS is opened from an old `/cfs/` path or a mismatched proxy path.
- WebSocket upgrade headers are missing on the CFS proxy endpoint.

Checks:
1. Open the direct compact URL:
   - `http://<fluidd-host>:4409/?view=fluidd`
2. Verify JS asset resolves with `200` and JavaScript MIME:
   - `curl -I http://<fluidd-host>:4409/assets/<asset-name>.js`
3. Verify websocket proxy path exists on port `4409`:
   - `location /ws` with `Upgrade`/`Connection` headers.

Fix:
1. Use a dedicated CFS proxy port (`4409`) rather than `/cfs/` subpath.
2. Add websocket proxy headers for `/ws`.
3. Clear browser cache/site data after proxy changes.
4. Optionally redirect old bookmarks:
   - `/cfs/` -> `http://$host:4409/?view=fluidd...`

## Watchtower API Version Mismatch

Symptoms:
- `cfs-watchtower` restarts in a loop.
- Logs show: `client version 1.25 is too old. Minimum supported API version is 1.44`.

Why it happens:
- An outdated `DOCKER_API_VERSION` value is injected into the watchtower runtime.
- The Docker daemon requires a newer API version (for example `>= 1.44`).

Checks:
1. Inspect current watchtower env:
   - `docker inspect cfs-watchtower --format '{{range .Config.Env}}{{println .}}{{end}}'`
2. Check for old API version:
   - `docker inspect cfs-watchtower --format '{{range .Config.Env}}{{println .}}{{end}}' | grep DOCKER_API_VERSION`
3. Confirm restart-loop/error:
   - `docker logs --tail 100 cfs-watchtower`

Fix:
1. Remove old `DOCKER_API_VERSION` from Portainer stack/env/endpoint injection.
2. Recreate watchtower so it gets clean env:
   - `docker compose pull watchtower`
   - `docker compose up -d --force-recreate watchtower`
3. Verify stable state:
   - `docker ps --filter name=cfs-watchtower`
   - `docker logs --tail 50 cfs-watchtower`

Repo safeguard:
- `docker-compose.yml` pins watchtower `DOCKER_API_VERSION` to `1.44` to avoid old injected defaults.

## Theme and UI

If light/dark appearance looks wrong:
1. Open `Settings`.
2. Toggle theme and reload once.
3. Clear browser cache if styles appear stale after an update.

## Need More Diagnostics

Collect and share:
- Backend log excerpt around the issue time.
- `GET /api/health` response.
- The affected slot IDs.
- Whether the K2 slot refresh action was performed.

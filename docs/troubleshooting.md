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

Related guide:
- [Fluidd Automation Script Guide](fluidd-automation-script.md)

## Moonraker Agent Integration

Symptoms:
- `GET /server/extensions/list` does not show `cfssync`.
- Extension request returns agent not found or backend errors.

Checks:
1. Verify container is running:
   - `docker ps --filter name=cfs-moonraker-agent`
2. Verify logs:
   - `docker logs --tail 100 cfs-moonraker-agent`
3. Verify Moonraker websocket URL and API key in `.env`:
   - `MOONRAKER_WS_URL`
   - `MOONRAKER_API_KEY`
4. Verify backend bridge URL:
   - `CFS_BACKEND_URL` should resolve from agent container.

Related guide:
- [Moonraker Agent Integration Guide](moonraker-agent-integration.md)

## Fluidd Deploy: Empty Web Root

Symptoms:
- `http://<fluidd-host>:4408` returns `403`.
- `/usr/share/fluidd` is empty or missing `assets`.

Checks:
1. `ls -lah /usr/share/fluidd`
2. `ls -lah /usr/share/fluidd/assets`

Fix:
1. Re-copy built files to host.
2. Deploy from the correct source path:
   - `cp -a /tmp/fluidd-new/* /usr/share/fluidd/`
3. Reapply permissions and reload Nginx.

If you intentionally want to remove the custom Fluidd UI patch and return to stock Fluidd:
1. Restore stock files in `/usr/share/fluidd`.
2. Remove temporary deploy assets (`/tmp/fluidd-new`, downloaded archives).
3. Reload nginx and validate `http://<fluidd-host>:4408/` returns `200`.

## Fluidd Deploy: Permission Denied / Redirect Cycle

Symptoms:
- Nginx logs show `Permission denied`.
- Nginx logs show `rewrite or internal redirection cycle`.
- Browser may show `500` for `/favicon.ico`.

Checks:
1. `tail -n 100 /var/log/nginx/fluidd-error.log`
2. `ls -ld /usr /usr/share /usr/share/fluidd`

Fix:
1. `chown -R root:root /usr/share/fluidd`
2. `find /usr/share/fluidd -type d -exec chmod 755 {} \;`
3. `find /usr/share/fluidd -type f -exec chmod 644 {} \;`
4. `nginx -t && nginx -s reload`

## Fluidd Deploy: Stale Hashed Asset URLs

Symptoms:
- Browser console shows module MIME errors for old asset hashes.
- `curl -I /` is `200`, but old `/assets/<hash>.js` fails.

Why it happens:
- Browser cache and service worker still reference previous build hashes.

Fix:
1. Unregister service worker.
2. Clear site data.
3. Hard reload (`Ctrl+F5`).
4. Re-validate with:
   - `curl -I http://<fluidd-host>:4408/assets/<actual-hash>.js`

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

# Fluidd Quick Install (No Local Fluidd Build)

This guide is the fastest path to show CFS slots in Fluidd.

It uses:
- CFS + Moonraker agent from Docker compose
- A prebuilt Fluidd UI package (with CFS card)
- A host deploy script (`scripts/deploy_fluidd_patch.sh`)

## 1) Configure and start CFS stack

In your CFS stack directory:

```bash
cd /opt/stacks/cfsspoolsync
cp .env.example .env
```

Set at least:

```env
MOONRAKER_WS_URL=ws://192.168.0.1:7125/websocket
```

Replace `192.168.0.1` with your real Moonraker host IP.

Start:

```bash
docker compose pull
docker compose up -d
```

## 2) Verify Moonraker agent registration

From Windows PowerShell:

```powershell
curl.exe -s "http://192.168.0.1:7125/server/extensions/list"
```

Expected: `agents` includes `cfssync`.

## 3) Download prebuilt Fluidd UI package

On the Fluidd host:

```bash
mkdir -p /tmp/fluidd-new
curl -L -o /tmp/fluidd-cfs-ui.tar.gz "https://github.com/mschoettli/CFSspoolsync/releases/download/cfs-dashboard-embed-v1/fluidd-cfs-ui-dist.tar.gz"
tar -xzf /tmp/fluidd-cfs-ui.tar.gz -C /tmp/fluidd-new
```

## 4) Deploy with one script

On the Fluidd host:

```bash
curl -L -o /tmp/deploy_fluidd_patch.sh "https://raw.githubusercontent.com/mschoettli/CFSspoolsync/main/scripts/deploy_fluidd_patch.sh"
chmod +x /tmp/deploy_fluidd_patch.sh
/tmp/deploy_fluidd_patch.sh /tmp/fluidd-new
```

## 5) Validate and open Fluidd

```bash
curl -I http://127.0.0.1:4408/
```

Then open:
- `http://192.168.0.1:4408`

In Fluidd dashboard layout, enable/add card:
- `CFS Slots`

## Update Workflow

- CFS app update only:
  - `docker compose pull && docker compose up -d`
  - No Fluidd patch redeploy needed.
- Fluidd firmware/web root replaced:
  - Re-run steps 3 and 4.

## Troubleshooting

- Agent missing in extensions list:
  - `docker logs --tail 100 cfs-moonraker-agent`
- `403` or `500` on `:4408`:
  - Re-run deploy script and check nginx reload output.
- MIME errors (`text/html` for JS files):
  - Clear browser cache + unregister service worker.

# Moonraker Agent Integration (Primary Path)

This is the recommended integration method for CFSspoolsync.

Instead of maintaining a Fluidd fork, CFSspoolsync can run a Moonraker extension
agent (`cfs-moonraker-agent`) that:
- identifies as `agent` on Moonraker's websocket,
- exposes `cfssync.*` extension methods,
- publishes live events to Moonraker clients.

## Why this path

- No mandatory Fluidd fork
- Reusable by any Moonraker client
- Same CFS business logic as the existing backend (agent delegates to `/api/*`)

## Required Environment

Set in `.env`:

```env
MOONRAKER_WS_URL=ws://192.168.0.1:7125/websocket
MOONRAKER_API_KEY=
CFS_BACKEND_URL=http://backend:8000
CFS_REQUEST_TIMEOUT=10
CFS_AGENT_NAME=cfssync
CFS_AGENT_VERSION=1.0.0
CFS_AGENT_URL=https://github.com/mschoettli/CFSspoolsync
CFS_EVENT_NAME=cfssync.state_updated
CFS_POLL_SECONDS=2
```

Replace `192.168.0.1` with your Moonraker host IP.

## Deploy

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Agent container name:
- `cfs-moonraker-agent`

## Verify Registration

Confirm Moonraker sees the agent:

```bash
curl -s http://192.168.0.1:7125/server/extensions/list
```

Expected: `agents` contains `cfssync` (or your configured `CFS_AGENT_NAME`).

## Extension Methods

Call via Moonraker:
- `POST /server/extensions/request`

Available methods:
- `cfssync.slots.list`
- `cfssync.slot.assign`
- `cfssync.slot.unassign`
- `cfssync.spools.list`
- `cfssync.spools.create`
- `cfssync.spools.update`
- `cfssync.spools.delete`
- `cfssync.history.query`
- `cfssync.settings.get`
- `cfssync.settings.set`

### Examples

List slots:

```bash
curl -s -X POST http://192.168.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{"agent":"cfssync","method":"cfssync.slots.list","arguments":{}}'
```

Assign spool:

```bash
curl -s -X POST http://192.168.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{"agent":"cfssync","method":"cfssync.slot.assign","arguments":{"slot_id":1,"spool_id":12}}'
```

Query history:

```bash
curl -s -X POST http://192.168.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{"agent":"cfssync","method":"cfssync.history.query","arguments":{"days":7}}'
```

Read settings:

```bash
curl -s -X POST http://192.168.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{"agent":"cfssync","method":"cfssync.settings.get","arguments":{}}'
```

Set settings:

```bash
curl -s -X POST http://192.168.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{"agent":"cfssync","method":"cfssync.settings.set","arguments":{"language":"en","theme":"dark"}}'
```

## Live Events

The agent emits:
- `cfssync.state_updated`

Event payload:
- `cfs`: current CFS environment snapshot
- `slots`: current slot list with spool assignments

## Failure Handling

- Moonraker unreachable:
  - agent reconnect loop keeps retrying.
- Invalid API key:
  - identify call fails; check `MOONRAKER_API_KEY`.
- Backend unreachable:
  - extension requests return backend error details.

## Optional Dashboard UI Addon

If you still want a dedicated dashboard card inside Fluidd, keep using:
- [Fluidd Dashboard Embed](fluidd-dashboard-embed.md)
- [Fluidd User Integration Guide](fluidd-user-integration.md)

That path is optional and no longer required for core integration.

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    hub = request.app.state.telemetry_hub

    async def event_generator():
      last_version, snapshot = hub.snapshot()
      payload = {"type": "telemetry", "version": last_version, "data": snapshot}
      yield f"event: telemetry\ndata: {json.dumps(payload)}\n\n"

      while True:
          if await request.is_disconnected():
              break
          version, updated = await hub.wait_for_update(last_version, timeout_seconds=12.0)
          if version == last_version:
              yield "event: heartbeat\ndata: {}\n\n"
              continue
          last_version = version
          payload = {"type": "telemetry", "version": last_version, "data": updated}
          yield f"event: telemetry\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

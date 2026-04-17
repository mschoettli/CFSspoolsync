from typing import AsyncGenerator
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import settings

router = APIRouter(prefix="/api/camera", tags=["camera"])


def _camera_candidates(raw_url: str) -> list[str]:
    base = raw_url.strip()
    if not base:
        return []
    candidates = [base]

    parsed = urlparse(base)
    clean_base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme and parsed.netloc else base
    if "action=stream" not in base:
        candidates.append(f"{clean_base}?action=stream")
    if not clean_base.endswith("/stream"):
        candidates.append(f"{clean_base.rstrip('/')}/stream")
    if not clean_base.endswith("/video"):
        candidates.append(f"{clean_base.rstrip('/')}/video")

    deduped: list[str] = []
    seen = set()
    for url in candidates:
        if url in seen:
            continue
        deduped.append(url)
        seen.add(url)
    return deduped


async def _stream_from_url(url: str) -> AsyncGenerator[bytes, None]:
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk


@router.get("/stream")
async def camera_stream() -> StreamingResponse:
    candidates = _camera_candidates(settings.camera_stream_url)
    if not candidates:
        raise HTTPException(status_code=400, detail="CAMERA_STREAM_URL is empty")

    last_error = ""
    for candidate in candidates:
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                probe = await client.get(candidate, headers={"Range": "bytes=0-512"})
                if probe.status_code >= 400:
                    raise HTTPException(status_code=probe.status_code)
                content_type = (probe.headers.get("content-type", "") or "").lower()
                if not any(token in content_type for token in ("multipart", "image", "video", "octet-stream")):
                    raise ValueError(f"non-stream content-type: {content_type}")

            return StreamingResponse(
                _stream_from_url(candidate),
                media_type="multipart/x-mixed-replace",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            last_error = str(exc)
            continue

    return JSONResponse(status_code=502, content={"detail": f"camera stream unavailable: {last_error}"})


@router.post("/webrtc-offer")
async def webrtc_offer(request: Request):
    if not settings.camera_webrtc_signal_url:
        return JSONResponse(status_code=503, content={"detail": "CAMERA_WEBRTC_SIGNAL_URL not configured"})

    body = await request.json()
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(settings.camera_webrtc_signal_url, json=body)
        return JSONResponse(status_code=response.status_code, content=response.json())

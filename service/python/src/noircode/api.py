"""Imaging sidecar: a thin HTTP wrapper around the NoiR Code encode/decode core.

The Go gateway (``service/backend``) owns the public API, rate-limiting and CORS; it
proxies the actual image work here because decode needs the OpenCV pipeline that lives
in this reference implementation. Endpoints:

* ``POST /encode``  JSON ``{text, style, hatch_data, adaptive}`` -> ``image/png`` bytes.
* ``POST /decode``  multipart file ``image`` -> JSON decode result.
* ``GET  /health``  liveness probe.

Run with ``noir-api`` (installs the ``api`` extra) or ``uvicorn noircode.api:app``.
"""

from __future__ import annotations

import dataclasses
import os

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from noircode.config import Config
from noircode.decode.decoder import decode as decode_panel
from noircode.ecc import EccError
from noircode.encode.encoder import encode as encode_text
from noircode.payload import FrameError

app = FastAPI(title="NoiR Code imaging sidecar", version="0.1.0")

# Permissive CORS by default for local dev (the Go gateway also fronts this in prod and
# does not need it). Lock down with NOIRCODE_API_CORS_ORIGINS="https://a,https://b".
_origins = os.environ.get("NOIRCODE_API_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class EncodeRequest(BaseModel):
    """Encode parameters mirroring the CLI flags."""

    text: str = Field(..., description="UTF-8 text payload to encode.")
    style: bool = Field(False, description="Apply the noir styling + halftone artwork.")
    hatch_data: bool = Field(False, description="Hatch the data cells (engraving look).")
    adaptive: bool = Field(True, description="Shrink the grid to the smallest fitting size.")


class DecodeResponse(BaseModel):
    """Structured decode outcome (mirrors ``decode.decoder.DecodeResult``)."""

    ok: bool
    text: str | None
    confidence: float
    rotation: int | None
    grid_erasures: int
    motif_erasures: int
    cross_check: bool | None
    failed_stage: str | None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/encode",
    responses={200: {"content": {"image/png": {}}}},
    response_class=Response,
)
def encode(req: EncodeRequest) -> Response:
    """Encode text to a PNG panel."""
    cfg = dataclasses.replace(Config(), hatched_data=req.hatch_data)
    try:
        panel = encode_text(req.text, cfg, style=req.style, adaptive=req.adaptive)
    except EccError:
        limit = cfg.rs_data_bytes - 7
        raise HTTPException(
            status_code=422,
            detail=f"text too long: {len(req.text.encode())} bytes; capacity is {limit} bytes",
        ) from None
    ok, buf = cv2.imencode(".png", panel)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode PNG")
    return Response(content=buf.tobytes(), media_type="image/png")


@app.post("/decode", response_model=DecodeResponse)
async def decode(image: UploadFile = File(...)) -> DecodeResponse:
    """Decode an uploaded panel image to text + diagnostics."""
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty image upload")
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="cannot decode image bytes")
    try:
        res = decode_panel(img, Config())
    except (EccError, FrameError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"decode error: {exc}") from None
    return DecodeResponse(
        ok=res.ok,
        text=res.text,
        confidence=res.confidence,
        rotation=res.rotation,
        grid_erasures=res.grid_erasures,
        motif_erasures=res.motif_erasures,
        cross_check=res.cross_check,
        failed_stage=res.failed_stage,
    )


def main() -> None:
    """Console-script entry point: run uvicorn from env (NOIRCODE_API_HOST/PORT)."""
    import uvicorn

    host = os.environ.get("NOIRCODE_API_HOST", "0.0.0.0")
    port = int(os.environ.get("NOIRCODE_API_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
